"""Манифесты диалогов Pokemon GBA: адреса строк (target/free_after/slots).

Манифест — чисто числовой список адресов в core/manifests/<game_code>.json:
никаких текстовых данных ROM (легально: аналогично уже закоммиченным
FIXED_TABLES). Генерируется scripts_roms/generate_manifest.py.

Загрузка кешируется по (game_code, guard): guard = CRC32 первых 0x100 байт
заголовка — инвариант под in-place инъекцию текста (наш инжектор пишет только
в pointer-окна дальше 0x1E0000), но различает ревизии. Чей-то проход не
совпал → адреса относятся к другой ревизии → entries вернуть нельзя
(вернётся None — плагин просто без dialogue-сегмента).
"""
import json
import logging
import os
import zlib

logger = logging.getLogger('gb2text.dialogue_manifest')

_MANIFESTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'manifests')

KNOWN_CODES: tuple[str, ...] = ('BPEE', 'BPRE', 'BPGE', 'AXVE', 'AXPE')

_cache: dict[tuple[str, int], list[dict] | None] = {}


def manifest_path(game_code: str) -> str | None:
    """Путь JSON-манифеста game_code, если файл существует."""
    path = os.path.join(_MANIFESTS_DIR, f'{game_code}.json')
    return path if os.path.exists(path) else None


def _entries_from_file(game_code: str) -> list[dict] | None:
    path = manifest_path(game_code)
    if path is None:
        return None
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        logger.warning(f'Манифест {path}: не читается ({exc})')
        return None
    entries = data.get('entries')
    if not isinstance(entries, list):
        logger.warning(f'Манифест {path}: нет списка entries')
        return None
    return entries


def entries_for_rom(rom) -> list[dict] | None:
    """Записи манифеста для ROM с проверкой guard.

    None — игры нет в манифестах ИЛИ ROM другой ревизии (guard не совпал).
    """
    code = rom.header.get('game_code', '')
    path = manifest_path(code)
    if path is None:
        return None
    guard = zlib.crc32(rom.data[:0x100])
    key = (code, guard)
    if key in _cache:
        return _cache[key]
    entries = _entries_from_file(code)
    if entries is None:
        _cache[key] = None
        return None
    try:
        with open(path, encoding='utf-8') as f:
            manifest_guard = json.load(f).get('guard')
    except (OSError, ValueError):  # pragma: no cover
        manifest_guard = None  # pragma: no cover
    if manifest_guard != guard:
        logger.warning(
            f'Манифест {code} для другой ревизии '
            f'(guard {manifest_guard!r} != {guard:08X}) — dialogue-сегмент отключён')
        _cache[key] = None
        return None
    safe = [e for e in entries if _valid_entry(e, len(rom.data))]
    sorted_ = sorted(safe, key=lambda e: e['target'])
    _cache[key] = sorted_
    return sorted_


def _valid_entry(entry: dict, rom_size: int) -> bool:
    target = entry.get('target')
    free_after = entry.get('free_after')
    slots = entry.get('slots')
    if not isinstance(target, int) or not isinstance(free_after, int):
        return False
    if not (0 <= target < rom_size and free_after >= 3 and target + free_after <= rom_size):
        return False
    if not isinstance(slots, list) or not all(isinstance(s, int) for s in slots):
        return False
    return True
