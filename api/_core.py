"""Тонкие обёртки над core для api/ — маппинг ошибок и безопасные пути."""

import json
import logging
import os
import tempfile
from pathlib import Path

from core.diff_text import text_segments_compare
from core.injector import TextInjector
from core.plugin_manager import ConfigurablePlugin, get_safe_plugin_manager
from core.rom import GameBoyROM, validate_rom_file

logger = logging.getLogger("gb2text.api")


class SDKError(Exception):
    """Ошибка api-слоя с кодом контракта."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


C_PLUGIN_NOT_FOUND = "PLUGIN_NOT_FOUND"
C_UNSUPPORTED_SYSTEM = "UNSUPPORTED_SYSTEM"
C_ROM_ERROR = "ROM_ERROR"
C_IO_ERROR = "IO_ERROR"
C_VALIDATION_ERROR = "VALIDATION_ERROR"
C_INTERNAL = "INTERNAL"

# Максимальный размер файла переводов, принимаемый load_json_file (1 MB).
_MAX_TRANSLATIONS_SIZE = 1 << 20


def resolve_rom(rom_path) -> str:
    """Валидирует и нормализует путь к ROM (P0: symlink/размер/расширение)."""
    if not isinstance(rom_path, str) and not isinstance(rom_path, Path):
        raise SDKError(C_VALIDATION_ERROR, f"rom_path должен быть str/Path, получен {type(rom_path).__name__}")
    path = Path(rom_path)
    if path.is_symlink():
        raise SDKError(C_IO_ERROR, f"Путь к ROM является символической ссылкой: {rom_path}")
    resolved = path.resolve()
    if resolved.is_symlink():
        raise SDKError(C_IO_ERROR, f"Разрешённый путь к ROM является символической ссылкой: {resolved}")
    error = validate_rom_file(str(resolved))
    if error is not None:
        if "неверное расширение" in error.lower() or "ожидалось" in error.lower():
            raise SDKError(C_UNSUPPORTED_SYSTEM, error)
        raise SDKError(C_IO_ERROR, error)
    if not resolved.is_file():
        raise SDKError(C_IO_ERROR, f"Нет доступа к файлу ROM: {resolved}")
    return str(resolved)


def resolve_output(rom_path: str, output_path=None) -> str:
    """Определяет и валидирует output для inject рядом с ROM, без симлинков."""
    rom = Path(rom_path).resolve()
    parent = rom.parent
    if output_path is None:
        candidate = parent / (rom.stem + "_translated" + rom.suffix)
    else:
        if not isinstance(output_path, str) and not isinstance(output_path, Path):
            raise SDKError(C_VALIDATION_ERROR, "output_path должен быть str/Path")
        out = Path(output_path)
        if out.is_symlink():
            raise SDKError(C_IO_ERROR, f"Путь output является символической ссылкой: {output_path}")
        candidate = out.resolve()
        if candidate.is_symlink():
            raise SDKError(C_IO_ERROR, f"Разрешённый путь output является символической ссылкой: {out}")
    if candidate.parent != parent:
        raise SDKError(C_IO_ERROR, f"output должен находиться в том же каталоге, что и ROM: {candidate.parent}")
    if candidate == rom:
        raise SDKError(C_VALIDATION_ERROR, "output не может совпадать с исходным ROM")
    return str(candidate)


def ensure_not_source(rom_path: str, output_path) -> str:
    """Запрещает писать результат поверх исходного ROM.

    Для `inject` это уже делает `resolve_output` (там ещё и правило «тот же
    каталог»). Здесь правило другое: PNG-превью пользователь вправе положить
    куда угодно, поэтому проверяется ровно одно — что выходной путь не является
    исходным файлом. Без этой проверки `picture apply -o <тот же .gba>` тихо
    перезаписывал бы ROM, что прямо противоречит обещанию «исходник не меняется».
    """
    out = Path(output_path)
    if out.is_symlink():
        raise SDKError(C_IO_ERROR,
                       f"Путь output является символической ссылкой: {output_path}")
    resolved_out = out.resolve()
    if resolved_out.is_symlink():
        raise SDKError(C_IO_ERROR,
                       f"Разрешённый путь output является символической ссылкой: {out}")
    rom = Path(rom_path).resolve()
    # `os.path.samefile` ловит hardlink: путь другой, а файл тот же самый.
    try:
        if resolved_out.exists() and os.path.samefile(resolved_out, rom):
            raise SDKError(C_VALIDATION_ERROR,
                           "output не может совпадать с исходным ROM — исходник "
                           "никогда не перезаписывается")
    except OSError:  # pragma: no cover — не на всех FS доступен stat
        pass
    if resolved_out == rom:
        raise SDKError(C_VALIDATION_ERROR,
                       "output не может совпадать с исходным ROM — исходник "
                       "никогда не перезаписывается")
    return str(resolved_out)


def _build_manager(plugin_dir, allowlist=None):
    try:
        manager = get_safe_plugin_manager(
            plugin_dir if plugin_dir is not None else "plugins",
            allowlist=allowlist,
        )
    except Exception as exc:
        logger.exception("Не удалось создать PluginManager")
        raise SDKError(C_INTERNAL, f"Ошибка создания PluginManager: {exc}") from exc
    return manager


def _plugin_info(plugin) -> dict:
    """Собирает метаданные плагина, безопасно к любому типу."""
    is_config = isinstance(plugin, ConfigurablePlugin)
    signature = bool(plugin.config.get("rom_signature")) if is_config else False
    config = plugin.config if is_config else {}
    name = (config.get("game") or {}).get("name") if isinstance(config.get("game"), dict) else None
    return {
        "name": name or getattr(plugin, "__class__", type(plugin)).__name__,
        "game_id_pattern": getattr(plugin, "game_id_pattern", None),
        "kind": "config" if is_config else "python",
        "signature": signature,
    }


def list_plugins(plugin_dir=None) -> list[dict]:
    """Read-only список плагинов; НЕ создаёт каталог/example.json."""
    path = plugin_dir if plugin_dir is not None else "plugins"
    resolved = Path(path).resolve()
    if not resolved.is_dir():
        return []
    manager = _build_manager(str(resolved))
    return [_plugin_info(p) for p in manager.plugins]


def detect(rom_path, plugin_dir=None) -> dict:
    """Определяет игровой плагин для ROM (game_id/system/plugin/сигнатура)."""
    resolved = resolve_rom(rom_path)
    try:
        rom = GameBoyROM(resolved)
        game_id = rom.get_game_id()
        system = rom.system
    except Exception as exc:
        logger.exception("Не удалось загрузить ROM для detect")
        raise SDKError(C_ROM_ERROR, f"Ошибка загрузки ROM: {exc}") from exc
    manager = _build_manager(plugin_dir)
    try:
        plugin = manager.get_plugin(game_id, system, rom=rom)
    except Exception:
        logger.exception("Ошибка определения плагина")
        plugin = None
    return {
        "game_id": game_id,
        "system": system,
        "title": rom.title,
        "size": len(rom.data),
        "plugin": _plugin_info(plugin) if plugin is not None else None,
    }


def _decoder_names(extractor, segments_result: dict) -> dict[str, str | None]:
    """Маппинг имя сегмента → имя класса декодера (отказоустойчиво)."""
    mapping: dict[str, str | None] = {}
    try:
        rom = extractor.rom
        segments = extractor.plugin.get_text_segments(rom)
        for seg in segments:
            decoder = seg.get("decoder")
            mapping[seg.get("name")] = (
                decoder.__class__.__name__ if decoder is not None else None
            )
    except Exception:
        logger.warning("Не удалось получить декодеры сегментов; decoder_name=None", exc_info=True)
        for seg_name in segments_result:
            mapping[seg_name] = None
    return mapping


def extract(rom_path, plugin_dir=None, max_segments=None, language="en", progress=None) -> dict:
    """Извлекает текст: segments + stats. language — фильтр, no-op без пометок."""
    resolved = resolve_rom(rom_path)
    manager = _build_manager(plugin_dir)
    try:
        from core.extractor import TextExtractor

        extractor = TextExtractor(
            resolved,
            plugin_manager=manager,
            max_segments=max_segments,
            progress_callback=progress,
        )
        results = extractor.extract()
    except SDKError:
        raise
    except Exception as exc:
        logger.exception("Ошибка извлечения текста")
        raise SDKError(C_ROM_ERROR, f"Ошибка извлечения: {exc}") from exc

    decoders = _decoder_names(extractor, results)
    segments: dict[str, list[dict]] = {}
    message_count = 0
    for seg_name, messages in results.items():
        out = []
        for msg in messages:
            entry = {
                "text": msg.get("text", ""),
                "offset": msg.get("offset", 0),
                "decoder_name": decoders.get(seg_name),
            }
            for key in ("target_addr", "length", "slots"):
                if key in msg:
                    entry[key] = msg[key]
            out.append(entry)
        segments[seg_name] = out
        message_count += len(out)
    return {
        "segments": segments,
        "stats": {
            "segment_count": len(segments),
            "message_count": message_count,
            "language": language,
            "max_segments": max_segments,
        },
    }


def _translate_items(entries) -> list[str]:
    """Принимает list[str] или list[dict] с ключом 'translation' (main.py-совместимо)."""
    if not isinstance(entries, list):
        raise SDKError(C_VALIDATION_ERROR, "Каждый сегмент переводов должен быть списком")
    texts = []
    for item in entries:
        if isinstance(item, str):
            texts.append(item)
        elif isinstance(item, dict) and "translation" in item:
            texts.append(item["translation"])
        else:
            raise SDKError(
                C_VALIDATION_ERROR,
                "Элемент перевода должен быть строкой или dict с ключом 'translation'",
            )
    return texts


def picture(rom_path, *, action, offset, bpp, count, png=None, output=None,
            plugin_dir=None, force: bool = False) -> dict:
    """Превью или замена блока тайлов (запечённый в графику текст).

    `preview` читает ROM и пишет только PNG рядом (или в `--output`); `apply`
    берёт новую картинку из PNG и пишет НОВЫЙ ROM — исходный не трогается,
    потому что замена графики необратима и обязана быть повторяемой.
    """
    from core.tile_picture import (
        PictureError as _PictureError,
        apply_picture as _apply,
        preview_to_png as _preview,
        read_png as _read,
        save_atomic as _save,
    )

    resolved = resolve_rom(rom_path)
    messages: list[str] = []
    try:
        source = bytes(GameBoyROM(resolved).data)
        if action == 'preview':
            if output is None:
                raise _PictureError(
                    'Для preview нужен -o/--output: путь для PNG')
            _preview(source, offset, bpp, count, path=output)
            messages.append(f'PNG: {output} ({count} тайлов, {bpp}bpp, '
                            f'{offset:#x})')
            return {'path': resolved, 'action': action, 'output': output,
                    'messages': messages}
        if png is None:
            raise _PictureError('Для apply нужен --png с новой картинкой')
        if output is None:
            raise _PictureError('Для apply нужен -o/--output: путь нового ROM')
        grids = _read(png, bpp, count)
        patched, stats = _apply(source, offset, bpp, count, grids, force=force)
        dest = ensure_not_source(resolved, output)
        _save(dest, patched)
        messages.append(
            f'ROM: {dest} (тайлов изменено: {stats["changed_tiles"]} из '
            f'{stats["total_tiles"]}, без изменений: {stats["unchanged_tiles"]}, '
            f'байт: {stats["changed_bytes"]})')
        return {'path': resolved, 'action': action, 'output': output,
                **stats, 'messages': messages}
    except _PictureError as exc:
        raise SDKError(C_VALIDATION_ERROR, str(exc)) from exc
    except ValueError as exc:
        # PIL и encode_tile бросают ValueError на битых входных данных; по
        # контракту `api/__init__.py` наружу должен уйти SDKError, а на сервере
        # — VALIDATION_ERROR, а не HTTP 500.
        raise SDKError(C_VALIDATION_ERROR, f'Некорректные входные данные: {exc}') \
            from exc
    except OSError as exc:
        raise SDKError(C_IO_ERROR, f'Ошибка ввода-вывода: {exc}') from exc


def audit_fixed_slots(rom_path, plugin_dir=None) -> dict:
    """Отчёт по fixed-сегментам: нужен ли где-то `has_mid_alias`.

    Закрывает договорённость из `plugins/config/README.md` со стороны автора
    плагина: он получает ответ по своей игре, а не полагается на общий вывод по
    корпусу. Идёт через `resolve_rom`, как и остальные команды.
    """
    from core.segment_audit import audit_fixed_slots as _audit

    resolved = resolve_rom(rom_path)
    report = _audit(resolved, manager=_build_manager(plugin_dir))
    return {
        'path': resolved,
        'segments': [a.as_dict() for a in report],
        'needs_mid_alias': [a.name for a in report if a.needs_mid_alias],
    }


def fixsum(rom_path, *, fix: bool = False) -> dict:
    """Проверить (`fix=False`) или починить (`fix=True`) checksum'ы ROM.

    Идёт через `resolve_rom`, а не прямо в `core.checksum_fix`: без него
    `--fix` перезаписывал бы ЛЮБОЙ файл длиннее 0x150 байт, включая `.sav`
    (байт 0x14D затирает данные сейва) и `.txt`. Расширение, symlink и размер
    проверяются здесь — тем же кодом, что и для extract/inject.

    `repaired` означает «файл был сломан И починен», а не «стало валидно»:
    состояние ДО снимается отдельно, потому что `repair()` возвращает отчёт
    ПОСЛЕ починки.
    """
    from core.checksum_fix import (
        FixError as _FixError,
        inspect as _inspect,
        repair as _repair,
    )

    resolved = resolve_rom(rom_path)
    try:
        was_broken = not _inspect(resolved).valid
        report = _repair(resolved) if fix else _inspect(resolved)
    except _FixError as exc:
        raise SDKError(C_ROM_ERROR, str(exc)) from exc
    data = report.as_dict()
    data["repaired"] = bool(fix and was_broken and report.valid)
    return data


def inject(rom_path, translations, output_path=None, plugin_dir=None) -> dict:
    """Внедряет переводы, атомарно пишет рядом с ROM, сообщает checksum."""
    resolved_rom = resolve_rom(rom_path)
    target = resolve_output(resolved_rom, output_path)
    if not isinstance(translations, dict):
        raise SDKError(C_VALIDATION_ERROR, "translations должен быть dict[segment, list]")

    manager = _build_manager(plugin_dir)
    injector = None
    tmp_path: str | None = None
    try:
        injector = TextInjector(resolved_rom)
        rom = injector.rom
        game_id = rom.get_game_id()
        plugin = manager.get_plugin(game_id, rom.system, rom=rom)
        if plugin is None:
            raise SDKError(C_PLUGIN_NOT_FOUND, f"Не найден плагин для {game_id} ({rom.system})")

        report: dict[str, bool] = {}
        for seg_name, entries in translations.items():
            texts = _translate_items(entries)
            ok = injector.inject_segment(seg_name, texts, plugin)
            report[seg_name] = bool(ok)

        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(target), suffix=".tmp", prefix=os.path.basename(target) + "_"
        )
        os.close(fd)
        injector.save(tmp_path)
        data = bytes(injector.modified_data)
        checksum = injector.rom.calculate_global_checksum(data)
        os.replace(tmp_path, target)
        tmp_path = None
        return {
            "output_path": target,
            "segments": report,
            "checksum": checksum,
        }
    except SDKError:
        raise
    except Exception as exc:
        logger.exception("Ошибка внедрения текста")
        raise SDKError(C_ROM_ERROR, f"Ошибка внедрения: {exc}") from exc
    finally:
        if injector is not None:
            del injector
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _summarize_text(text: str, limit: int = 40) -> str:
    one_line = " ".join(text.split())
    if len(one_line) > limit:
        return one_line[:limit] + "..."
    return one_line


def _segment_texts(segments: dict) -> dict[str, str]:
    texts: dict[str, str] = {}
    for seg_name, messages in segments.items():
        texts[str(seg_name)] = " ".join(str(msg.get("text", "")) for msg in messages)
    return texts


def diff_roms(rom1, rom2, plugin_dir=None) -> dict:
    resolved1 = resolve_rom(rom1)
    resolved2 = resolve_rom(rom2)
    first = extract(resolved1, plugin_dir=plugin_dir)
    texts1 = _segment_texts(first["segments"])
    del first
    second = extract(resolved2, plugin_dir=plugin_dir)
    texts2 = _segment_texts(second["segments"])
    del second
    report = text_segments_compare(texts1, texts2)
    return {
        "segments": {
            "added": list(report.added),
            "removed": list(report.removed),
            "changed": [
                {
                    "seg": pair.key,
                    "old_summary": _summarize_text(pair.old_text),
                    "new_summary": _summarize_text(pair.new_text),
                }
                for pair in report.changed
            ],
        },
        "stats": {
            "added": len(report.added),
            "removed": len(report.removed),
            "changed": len(report.changed),
        },
    }


def get_version() -> str:
    """Версия из VERSION-файла с fallback."""
    for candidate in ("VERSION", os.path.join("..", "VERSION")):
        try:
            with open(candidate, encoding="utf-8") as fh:
                version = fh.read().strip()
            if version:
                return version
        except OSError:
            continue
    return "1.0.0"


def load_json_file(path, limit: int = _MAX_TRANSLATIONS_SIZE) -> dict:
    """Загружает JSON-файл переводов с ограничением размера."""
    try:
        size = os.path.getsize(path)
    except OSError:
        raise SDKError(C_IO_ERROR, f"Файл не найден: {path}") from None
    if size > limit:
        raise SDKError(
            C_VALIDATION_ERROR,
            f"Файл переводов слишком большой: {size} байт (лимит {limit})",
        )
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)  # type: ignore[no-any-return]
    except FileNotFoundError:
        raise SDKError(C_IO_ERROR, f"Файл не найден: {path}") from None
    except json.JSONDecodeError as exc:
        raise SDKError(C_VALIDATION_ERROR, f"Некорректный JSON: {exc}") from exc
