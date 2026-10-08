"""CLI-интерфейс GB2Text для агентов: python -m api.cli <command> [--json].

Команды: plugins, detect, extract, inject, fixsum, audit, picture, serve.
Коды выхода: 0 — ok, 1 — runtime/validation (contract-ошибка на stdout при --json),
2 — ошибка парсинга argparse. JSON-ответы только на stdout, utf-8.
"""

import argparse
import csv
import json
import logging
import sys

from api import _core
from api._core import SDKError, get_version
from core import tile_picture

logger = logging.getLogger("gb2text.api.cli")

# Код возврата «ROM сломан». Отдельный от 1 (операционная ошибка): CI, читающий
# только `$?`, обязан отличить «ROM не прошёл проверку» от «не тот путь / нет
# прав» — иначе битый ROM выглядит как сломанный инструмент.
C_BROKEN_CHECKSUM = 3


def _reconfigure_stdout():
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def _emit(data, as_json: bool):
    if as_json:
        sys.stdout.write(json.dumps({"ok": True, "data": data}, ensure_ascii=False) + "\n")
    else:
        return data


def _fail(exc: SDKError, as_json: bool) -> int:
    if as_json:
        sys.stdout.write(
            json.dumps(
                {"ok": False, "error": {"code": exc.code, "message": exc.message}},
                ensure_ascii=False,
            )
            + "\n"
        )
    else:
        print(f"Ошибка ({exc.code}): {exc.message}", file=sys.stderr)
    return 1


def _print_plugins(data, as_json: bool):
    if as_json:
        _emit(data, True)
        return
    for p in data:
        kind = "config" if p["kind"] == "config" else "python"
        sig = " [hack]" if p["signature"] else ""
        print(f"{p['name']}: {p['game_id_pattern']} ({kind}){sig}")


def _print_extract_text(result, lang: str):
    for seg_name, messages in result["segments"].items():
        print(f"\n== {seg_name.upper()} ==")
        for msg in messages:
            print(f"0x{msg['offset']:04X}: {msg['text']}")


def _print_extract_csv(result, out_path=None):
    writer_holder = None if out_path is None else open(out_path, "w", newline="", encoding="utf-8")
    try:
        writer = csv.writer(sys.stdout if writer_holder is None else writer_holder)
        writer.writerow(["segment", "offset", "text"])
        for seg_name, messages in result["segments"].items():
            for msg in messages:
                writer.writerow([seg_name, msg["offset"], msg["text"]])
    finally:
        if writer_holder is not None:
            writer_holder.close()


def _cmd_plugins(args):
    data = _core.list_plugins(args.plugin_dir)
    _print_plugins(data, args.json)
    return 0


def _cmd_detect(args):
    data = _core.detect(args.rom, plugin_dir=args.plugin_dir)
    if args.json:
        _emit(data, True)
    else:
        print(f"game_id: {data['game_id']}")
        print(f"system:  {data['system']}")
        print(f"title:   {data['title']}")
        print(f"size:    {data['size']} bytes")
        print(f"plugin:  {data['plugin']}")
    return 0


def _cmd_extract(args):
    result = _core.extract(
        args.rom,
        plugin_dir=args.plugin_dir,
        max_segments=args.max_segments,
        language=args.lang,
    )
    if args.json:
        _emit(result, True)
        return 0
    if args.format == "json":
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    elif args.format == "csv":
        _print_extract_csv(result, args.output)
    else:
        _print_extract_text(result, args.lang)
    return 0


def _cmd_inject(args):
    translations = _core.load_json_file(args.translations)
    result = _core.inject(
        args.rom,
        translations,
        output_path=args.output_rom,
        plugin_dir=args.plugin_dir,
    )
    if args.json:
        _emit(result, True)
    else:
        print(f"Сохранено: {result['output_path']}")
        print(f"Checksum:  0x{result['checksum']:04X}")
        for seg_name, ok in result["segments"].items():
            status = "ok" if ok else "FAIL"
            print(f"  {seg_name}: {status}")
    return 0


def _cmd_serve(args):
    from api import serve

    serve(
        args.host,
        args.port,
        plugin_dir=args.plugin_dir,
        max_workers=args.max_workers,
        api_token=args.api_token,
    )
    return 0


def _cmd_fixsum(args):
    """CRC/checksum fixer: `--check` для CI, `--fix` для починки.

    Коды возврата: 0 — checksum сошёлся, 1 — операционная ошибка (через `_fail`),
    3 — «ROM сломан». Тройка отдельна от единицы намеренно: CI, читающий только
    `$?`, должен отличить «ROM не прошёл проверку» от «не тот путь / нет прав».
    """
    data = _core.fixsum(args.rom, fix=bool(args.fix))
    if args.json:
        _emit(data, True)
        return 0 if data["valid"] else C_BROKEN_CHECKSUM
    state = "ok" if data["valid"] else "СЛОМАНО"
    print(f"{data['path']}: {data['system']}, {state}")
    if not data["valid"]:
        for name, stored in data["stored"].items():
            expected = data["expected"][name]
            if stored != expected:
                print(f"  {name}: 0x{stored:04X} != 0x{expected:04X}")
        if data["wrong_offsets"]:
            print("  битые байты: "
                  + ", ".join(f"0x{off:X}" for off in data["wrong_offsets"]))
        if not data["global_ok"]:
            print("  глобальная сумма не сходится")
    elif args.fix:
        print("  починено" if data["repaired"] else "чинить нечего, файл не тронут")
    return 0 if data["valid"] else C_BROKEN_CHECKSUM


def _cmd_audit(args):
    """Аудит fixed-слотов: где плагину нужен `has_mid_alias`."""
    data = _core.audit_fixed_slots(args.rom, plugin_dir=args.plugin_dir)
    if args.json:
        _emit(data, True)
        return 0
    segments = data["segments"]
    if not segments:
        print(f"{data['path']}: fixed-слотов нет")
        return 0
    print(f"{data['path']}: fixed-сегментов {len(segments)}")
    for seg in segments:
        flag = "НУЖЕН has_mid_alias" if seg["needs_mid_alias"] else "не нужен"
        print(f"  {seg['name']}: слотов {seg['slots']}, {flag}")
        for hit in seg["mid_pointers"][:4]:
            print(f"      указатель {hit['pointer_at']:#x} -> "
                  f"{hit['target']:#x} (хвост слота)")
    return 0


def _cmd_picture(args):
    """Превью и замена картинки из тайлов (запечённые в графику заголовки)."""
    data = _core.picture(args.rom, action=args.action, offset=args.offset,
                         bpp=args.bpp, count=args.count, png=args.png,
                         output=args.output, force=args.force)
    if args.json:
        _emit(data, True)
        return 0
    for line in data["messages"]:
        print(line)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="api.cli",
        description="GB2Text agent CLI. Версия " + get_version(),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_plugins = sub.add_parser("plugins", help="Список плагинов")
    p_plugins.add_argument("--plugin-dir", default="plugins")
    p_plugins.add_argument("--json", action="store_true")
    p_plugins.set_defaults(func=_cmd_plugins)

    p_detect = sub.add_parser("detect", help="Определить игру/плагин для ROM")
    p_detect.add_argument("rom")
    p_detect.add_argument("--plugin-dir", default="plugins")
    p_detect.add_argument("--json", action="store_true")
    p_detect.set_defaults(func=_cmd_detect)

    p_extract = sub.add_parser("extract", help="Извлечь текст")
    p_extract.add_argument("rom")
    p_extract.add_argument("-o", "--output", help="Файл для csv (для text/json — stdout)")
    p_extract.add_argument("--format", default="text", choices=["text", "json", "csv"])
    p_extract.add_argument("--plugin-dir", default="plugins")
    p_extract.add_argument("--max-segments", type=int)
    p_extract.add_argument("--lang", default="en", choices=["en", "ru", "ja", "zh"])
    p_extract.add_argument("--json", action="store_true")
    p_extract.set_defaults(func=_cmd_extract)

    p_inject = sub.add_parser("inject", help="Внедрить переводы (формат main.py)")
    p_inject.add_argument("rom")
    p_inject.add_argument("--translations", required=True)
    p_inject.add_argument("--output-rom", help="Выходной ROM (по умолчанию *_translated рядом)")
    p_inject.add_argument("--plugin-dir", default="plugins")
    p_inject.add_argument("--json", action="store_true")
    p_inject.set_defaults(func=_cmd_inject)

    p_serve = sub.add_parser("serve", help="HTTP/JSON-сервис")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--plugin-dir", default="plugins")
    p_serve.add_argument("--max-workers", type=int, default=4)
    p_serve.add_argument(
        "--api-token",
        default=None,
        help="Bearer-токен для авторизации (приоритет у env GB2TEXT_API_TOKEN). "
             "Обязателен для non-loopback хоста.",
    )
    p_serve.set_defaults(func=_cmd_serve)

    p_fixsum = sub.add_parser(
        "fixsum",
        help="Проверить/починить checksum'ы ROM (--check без записи)",
    )
    p_fixsum.add_argument("rom")
    group = p_fixsum.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="Только проверить; код 3, если checksum сломан")
    group.add_argument("--fix", action="store_true",
                       help="Починить на месте (атомарно)")
    p_fixsum.add_argument("--json", action="store_true")
    p_fixsum.set_defaults(func=_cmd_fixsum)

    p_audit = sub.add_parser(
        "audit",
        help="Аудит fixed-слотов: где нужен has_mid_alias",
    )
    p_audit.add_argument("rom")
    p_audit.add_argument("--plugin-dir", default="plugins")
    p_audit.add_argument("--json", action="store_true")
    p_audit.set_defaults(func=_cmd_audit)

    p_picture = sub.add_parser(
        "picture",
        help="Превью/замена картинки из тайлов (запечённый в графику текст)",
    )
    p_picture.add_argument("rom")
    p_picture.add_argument("action", choices=("preview", "apply"))
    p_picture.add_argument("--offset", type=lambda v: int(v, 0), required=True,
                           help="смещение блока тайлов в ROM (hex или dec)")
    p_picture.add_argument("--bpp", type=int, default=4,
                           choices=tile_picture.SUPPORTED_BPP)
    p_picture.add_argument("--count", type=int, required=True,
                           help="сколько тайлов в блоке")
    p_picture.add_argument("--png", help="PNG с новой картинкой (для apply)")
    p_picture.add_argument(
        "--force", action="store_true",
        help="записать даже если блок не похож на графику (знаете лучше гейта)")
    p_picture.add_argument("-o", "--output",
                           help="куда сохранить PNG (preview) или ROM (apply)")
    p_picture.add_argument("--json", action="store_true")
    p_picture.set_defaults(func=_cmd_picture)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Безусловно, а не только под --json: ветки без JSON печатают по-русски, и
    # на stdout в не-UTF-8 (cp1251, ascii) `print` падал UnicodeEncodeError —
    # для `fixsum --fix` это означало «INTERNAL» уже ПОСЛЕ того, как ROM
    # перезаписан. Раньше это было латентно (падал и `inject`), но на
    # разрушающей команде ошибка недопустима.
    _reconfigure_stdout()
    if getattr(args, "command", None) == "extract" and getattr(args, "json", False) and getattr(args, "format", None) == "json":
        parser.error("--json и --format json взаимоисключающие (первый оборачивает, второй — формат данных)")
    try:
        status = args.func(args)
        return status if isinstance(status, int) else 1
    except SDKError as exc:
        return _fail(exc, getattr(args, "json", False))
    except Exception as exc:
        logger.exception("Необработанная ошибка CLI")
        if getattr(args, "json", False):
            sys.stdout.write(
                json.dumps(
                    {"ok": False, "error": {"code": "INTERNAL", "message": "Внутренняя ошибка"}},
                    ensure_ascii=False,
                )
                + "\n"
            )
        else:
            print(f"Ошибка (INTERNAL): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
