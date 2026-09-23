"""Логика вкладки шрифта без tkinter (F2 MR1).

Весь GUI-таб (gui/font_tab.py) — тонкая обвязка над этими чистыми функциями:
resolve для баннеров/превью, snapshot/restore для одноуровневого undo,
map для строгого импорта. Запись — только через inject_font_block вызывающей
стороны (TextInjector.modified_data + save), модуль ROM не трогает.
"""

from __future__ import annotations

from core.font_tiles import (
    decode_tile,
    encode_tile,
    is_likely_compressed,
    tiles_from_rom,
    validate_font_meta,
)

_PREVIEW_MAX_TILES = 4096


def resolve_font_view(data: bytes | bytearray | None, raw_meta: dict | None) -> dict:
    """Состояние шрифта для таба: ok / no_rom / unknown_meta / invalid / compressed.

    ok -> {status, layout, grids}; compressed -> {status, layout};
    invalid -> {status, error}; остальные — только {status}.
    Превью декодирует не более _PREVIEW_MAX_TILES (защита от OOM на
    злонамеренном meta); сверх — invalid с явной ошибкой.
    Неавторитетные эвристики (сжатие) — как в font_tiles.
    """
    if data is None:
        return {"status": "no_rom"}
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError(f"font data must be bytes, got {type(data).__name__}")
    if raw_meta is None:
        return {"status": "unknown_meta"}
    try:
        layout = validate_font_meta(raw_meta, len(data))
    except ValueError as exc:
        return {"status": "invalid", "error": str(exc)}
    if layout["count"] > _PREVIEW_MAX_TILES:
        return {"status": "invalid", "error": f"font too large to preview: {layout['count']} > {_PREVIEW_MAX_TILES}"}
    if is_likely_compressed(data, layout["offset"]):
        return {"status": "compressed", "layout": layout}
    grids = [decode_tile(raw, layout["bpp"]) for raw in tiles_from_rom(data, layout["offset"], layout["count"], layout["stride"])]
    return {"status": "ok", "layout": layout, "grids": grids}


def snapshot_zone(data: bytes | bytearray, raw_meta: dict) -> dict:
    """Снапшот шрифтовой зоны для undo: {offset, bytes}."""
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError(f"font data must be bytes, got {type(data).__name__}")
    layout = validate_font_meta(raw_meta, len(data))
    start = layout["offset"]
    size = layout["count"] * layout["stride"]
    return {"offset": start, "bytes": bytes(data[start : start + size])}


def restore_zone(buf: bytearray, snapshot: dict) -> None:
    """Возвращает зону из снапшота (undo до save)."""
    if not isinstance(buf, bytearray):
        raise ValueError(f"font buffer must be bytearray, got {type(buf).__name__}")
    if not isinstance(snapshot, dict):
        raise ValueError(f"snapshot must be a dict, got {type(snapshot).__name__}")
    try:
        offset = snapshot["offset"]
        raw = snapshot["bytes"]
    except KeyError as exc:
        raise ValueError(f"snapshot needs {exc}") from exc
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError(f"bad snapshot offset: {offset!r}")
    if not isinstance(raw, (bytes, bytearray)):
        raise ValueError(f"bad snapshot bytes: {type(raw).__name__}")
    if offset + len(raw) > len(buf):
        raise ValueError(f"snapshot [{offset}:{offset + len(raw)}] exceeds data size {len(buf)}")
    buf[offset : offset + len(raw)] = raw


def map_imported_grids(raw_meta: dict, rom_len: int, imported: list) -> dict[int, list]:
    """Строгое отображение импорта: len(imported) == count, гриды под bpp.

    MR1: полная замена блока (индексы 0..count-1 от layout.offset);
    частичный префикс-N — follow-up. Каждый гриф валидируется кодированием
    под bpp (ValueError наружу).
    """
    layout = validate_font_meta(raw_meta, rom_len)
    if not isinstance(imported, (list, tuple)):
        raise ValueError(f"imported must be a list, got {type(imported).__name__}")
    if len(imported) != layout["count"]:
        raise ValueError(f"imported {len(imported)} glyphs != font count {layout['count']}")
    mapped: dict[int, list] = {}
    for index, grid in enumerate(imported):
        encode_tile(grid, layout["bpp"])
        mapped[index] = grid
    return mapped
