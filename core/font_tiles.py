"""Тайлы шрифта GB 2bpp (F3 фаза 1, 1.4).

Чистые функции без зависимости от ROM: декодирование 8x8 2bpp-тайлов
(2 байта на строку: чётный — младшие биты, нечётный — старшие),
кодирование обратно, ASCII-art превью для ревью без эмулятора.

Формат (Game Boy tile data): 16 байт на тайл, строки 0-7, в каждой
младший бит пикселя из байта 2*row, старший — из байта 2*row+1,
старший бит байта — левый пиксель. Значения 0-3 (палитра отдельно,
здесь не хранится).

Фаза 0 (scripts_roms/FONT_RESEARCH.md): слепой поиск шрифта в двух
ROM недостаточен для позитивной идентификации; модуль намеренно
зависит только от синтетики и покрыт на 100% без реальных ROM.

Фаза 2: inject_glyphs (in-place запись глифов; поиск места — задача
вызывающей стороны, напр. pointer_table.find_free_space) + опциональный
хук GamePlugin.get_font_meta (дефолт None).
"""

from __future__ import annotations

TILE_SIZE = 8
TILE_BYTES = 16

_PIXELS = " .:#"


def decode_2bpp_tile(raw: bytes | bytearray) -> list[list[int]]:
    """16 байт -> матрица 8x8 значений 0-3.

    Raises:
        ValueError: raw короче 16 байт (лишние байты игнорируются).
    """
    if len(raw) < TILE_BYTES:
        raise ValueError(f"tile needs {TILE_BYTES} bytes, got {len(raw)}")
    grid: list[list[int]] = []
    for row in range(TILE_SIZE):
        low = raw[row * 2]
        high = raw[row * 2 + 1]
        line = []
        for bit in range(7, -1, -1):
            line.append(((high >> bit) & 1) * 2 + ((low >> bit) & 1))
        grid.append(line)
    return grid


def encode_2bpp_tile(grid: list[list[int]]) -> bytes:
    """Матрица 8x8 значений 0-3 -> 16 байт (обратное к decode_2bpp_tile).

    Raises:
        ValueError: неверный размер или значения вне 0-3.
    """
    if len(grid) != TILE_SIZE or any(len(row) != TILE_SIZE for row in grid):
        raise ValueError("grid must be 8x8")
    raw = bytearray(TILE_BYTES)
    for row in range(TILE_SIZE):
        low = 0
        high = 0
        for col in range(TILE_SIZE):
            value = grid[row][col]
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"bad pixel value at ({row},{col}): {value!r}")
            if value < 0 or value > 3:
                raise ValueError(f"pixel out of range at ({row},{col}): {value!r}")
            low |= (value & 1) << (7 - col)
            high |= ((value >> 1) & 1) << (7 - col)
        raw[row * 2] = low
        raw[row * 2 + 1] = high
    return bytes(raw)


def tile_to_ascii(grid: list[list[int]], palette: str = _PIXELS) -> list[str]:
    """Матрица 8x8 -> 8 строк ASCII-арта (превью для ревью без эмулятора).

    Пиксели валидируются как в encode (0-3, без bool) — превью мусора
    не рисует, а падает явно.
    """
    if len(palette) < 4:
        raise ValueError("palette needs at least 4 characters")
    art: list[str] = []
    for row in grid:
        line = ""
        for pixel in row:
            if not isinstance(pixel, int) or isinstance(pixel, bool) or pixel < 0 or pixel > 3:
                raise ValueError(f"bad pixel value: {pixel!r}")
            line += palette[pixel]
        art.append(line)
    return art


def inject_glyphs(
    data: bytearray,
    base_offset: int,
    glyphs: dict[int, bytes | bytearray | list[list[int]]],
    stride: int = TILE_BYTES,
) -> list[dict]:
    """Вписывает глифы в буфер ROM in-place (механизм фазы 2).

    Каждый глиф кладётся по адресу base_offset + index * stride.
    Глиф — 16 байт (2bpp) либо матрица 8x8 (кодируется через
    encode_2bpp_tile). Поиск свободного места — задача вызывающей
    стороны (напр. core.pointer_table.find_free_space для 0x00-run);
    сюда передаются готовые индексы/смещения.

    Args:
        data: изменяемый буфер ROM (bytearray).
        base_offset: база блока шрифта.
        glyphs: {индекс тайла: 16 байт | матрица 8x8}.
        stride: байт на тайл (по умолчанию 16).

    Returns:
        Отчёт [{index, offset}] в порядке сортировки индексов.

    Raises:
        ValueError: отрицательный индекс/stride, выход за границы,
            неверный размер глифа.
    """
    if stride <= 0:
        raise ValueError(f"stride must be positive, got {stride}")
    if base_offset < 0:
        raise ValueError(f"negative base_offset: {base_offset}")
    # Фаза 1 — валидация ВСЕГО (атомарность: при ошибке позднего тайла
    # буфер остаётся нетронутым, частично записанного нет).
    prepared: list[tuple[int, int, bytes]] = []
    for index in sorted(glyphs):
        if index < 0:
            raise ValueError(f"negative tile index: {index}")
        glyph = glyphs[index]
        if isinstance(glyph, (bytes, bytearray)):
            raw = bytes(glyph)
            if len(raw) != stride:
                raise ValueError(f"tile {index}: needs {stride} bytes, got {len(raw)}")
        else:
            raw = encode_2bpp_tile(glyph)
            if len(raw) != stride:
                raise ValueError(f"tile {index}: encoded {len(raw)} bytes != stride {stride}")
        offset = base_offset + index * stride
        end = offset + stride
        if end > len(data):
            raise ValueError(f"tile {index} [{offset}:{end}] exceeds data size {len(data)}")
        prepared.append((index, offset, raw))
    # Фаза 2 — запись (после этой точки ошибок быть не должно).
    report: list[dict] = []
    for index, offset, raw in prepared:
        data[offset : offset + stride] = raw
        report.append({"index": index, "offset": offset})
    return report


def tiles_from_rom(data: bytes | bytearray, offset: int, count: int) -> list[bytes]:
    """Вырезает count 16-байтных тайлов из данных с offset.

    Raises:
        ValueError: отрицательные offset/count или выход за границы.
    """
    if offset < 0 or count < 0:
        raise ValueError(f"negative offset/count: {offset}/{count}")
    end = offset + count * TILE_BYTES
    if end > len(data):
        raise ValueError(f"tiles [{offset}:{end}] exceed data size {len(data)}")
    return [bytes(data[i : i + TILE_BYTES]) for i in range(offset, end, TILE_BYTES)]
