"""Тайлы шрифта GB/GBA (F3 фаза 1-2, 1.4-1.5).

Декодирование 8x8-тайлов 1bpp (8 байт), 2bpp (16 байт: чётный байт строки —
младшие биты, нечётный — старшие, старший бит байта — левый пиксель) и
GBA 4bpp (32 байта: 4 байта на строку, младший ниббл — левый пиксель пары
по GBATEK), кодирование обратно, ASCII-art превью, импорт/экспорт PNG,
манифест char->tile и in-place запись глифов с гейтами.

Фаза 0 (слепой скан, scripts_roms/ — пользовательская каталог, не версионируется):
поиск шрифта оставлен вызывающей стороне. Модуль зависит только от синтетики.
Relocate шрифта — non-goal: шрифт адресуется кодом загрузки в VRAM, а не
pointer table, свободное место под него через pointer-механику не ищется.
Сжатый шрифт (LZ77 0x10 / Huffman) — отказ, recompress не делается.

Split-раскладка FireRed-latin (FRLG): stored stride 0x40, арт — два 8x8-тайла
halves-порядка (верх +0x10, низ +0x30), пады +0x00/+0x20 нули. halves-тайл:
левые 4 px строки — нечётный байт пары, правые 4 px — чётный (high-byte-first
по DecompressGlyphTile из pokefirered, старший бит байта — левый пиксель).
Мета с halves=[0x10, 0x30] принимает validate_font_meta/_require_layout;
побайтово-контигуальные пути (preview/inject/candidate) для split честно
отказывают — нужна глиф-aware запись (follow-up Фазы 2).
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

from PIL import Image

TILE_SIZE = 8
TILE_BYTES_1BPP = 8
TILE_BYTES_2BPP = 16
TILE_BYTES_4BPP = 32
TILE_BYTES = TILE_BYTES_2BPP

_PIXELS = " .:#"
_VALID_BPP = (1, 2, 4)
_LZ77_MAX_SIZE = 0x200000
_GRAY_LEVELS = 16
_CANDIDATE_MAX_TILES = 65536


def _require_bpp(bpp: int) -> int:
    if isinstance(bpp, bool) or not isinstance(bpp, int) or bpp not in _VALID_BPP:
        raise ValueError(f"unknown bpp: {bpp!r}, expected one of {list(_VALID_BPP)}")
    return bpp


def stride_for_bpp(bpp: int) -> int:
    """Байт на тайл для bpp (1->8, 2->16, 4->32).

    Raises:
        ValueError: неизвестный bpp (строгий отказ, без fallback).
    """
    _require_bpp(bpp)
    if bpp == 1:
        return TILE_BYTES_1BPP
    if bpp == 2:
        return TILE_BYTES_2BPP
    return TILE_BYTES_4BPP


def _require_data(data: bytes | bytearray) -> bytes | bytearray:
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError(f"font data must be bytes, got {type(data).__name__}")
    return data


def _check_grid(grid: Sequence[Sequence[int]], maxval: int) -> Sequence[Sequence[int]]:
    if not isinstance(grid, (list, tuple)) or len(grid) != TILE_SIZE:
        raise ValueError("grid must be 8x8")
    for row in grid:
        if not isinstance(row, (list, tuple)) or len(row) != TILE_SIZE:
            raise ValueError("grid must be 8x8")
        for value in row:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > maxval:
                raise ValueError(f"pixel out of range 0-{maxval}: {value!r}")
    return grid


def decode_1bpp_tile(raw: bytes | bytearray) -> list[list[int]]:
    """8 байт -> матрица 8x8 значений 0-1 (бит 7 — левый пиксель)."""
    _require_data(raw)
    if len(raw) < TILE_BYTES_1BPP:
        raise ValueError(f"tile needs {TILE_BYTES_1BPP} bytes, got {len(raw)}")
    grid: list[list[int]] = []
    for row in range(TILE_SIZE):
        byte = raw[row]
        grid.append([(byte >> (7 - col)) & 1 for col in range(TILE_SIZE)])
    return grid


def encode_1bpp_tile(grid: Sequence[Sequence[int]]) -> bytes:
    """Матрица 8x8 значений 0-1 -> 8 байт."""
    _check_grid(grid, 1)
    raw = bytearray(TILE_BYTES_1BPP)
    for row in range(TILE_SIZE):
        byte = 0
        for col in range(TILE_SIZE):
            byte |= (grid[row][col] & 1) << (7 - col)
        raw[row] = byte
    return bytes(raw)


def decode_2bpp_tile(raw: bytes | bytearray) -> list[list[int]]:
    """16 байт -> матрица 8x8 значений 0-3.

    Raises:
        ValueError: raw короче 16 байт (лишние байты игнорируются).
    """
    _require_data(raw)
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


def encode_2bpp_tile(grid: Sequence[Sequence[int]]) -> bytes:
    """Матрица 8x8 значений 0-3 -> 16 байт (обратное к decode_2bpp_tile)."""
    _check_grid(grid, 3)
    raw = bytearray(TILE_BYTES)
    for row in range(TILE_SIZE):
        low = 0
        high = 0
        for col in range(TILE_SIZE):
            value = grid[row][col]
            low |= (value & 1) << (7 - col)
            high |= ((value >> 1) & 1) << (7 - col)
        raw[row * 2] = low
        raw[row * 2 + 1] = high
    return bytes(raw)


def decode_4bpp_tile(raw: bytes | bytearray) -> list[list[int]]:
    """32 байта -> матрица 8x8 значений 0-15 (младший ниббл — левый)."""
    _require_data(raw)
    if len(raw) < TILE_BYTES_4BPP:
        raise ValueError(f"tile needs {TILE_BYTES_4BPP} bytes, got {len(raw)}")
    grid: list[list[int]] = []
    for row in range(TILE_SIZE):
        line: list[int] = []
        for k in range(4):
            byte = raw[row * 4 + k]
            line.append(byte & 0x0F)
            line.append((byte >> 4) & 0x0F)
        grid.append(line)
    return grid


def encode_4bpp_tile(grid: Sequence[Sequence[int]]) -> bytes:
    """Матрица 8x8 значений 0-15 -> 32 байта."""
    _check_grid(grid, 15)
    raw = bytearray(TILE_BYTES_4BPP)
    for row in range(TILE_SIZE):
        for k in range(4):
            low = grid[row][2 * k] & 0x0F
            high = grid[row][2 * k + 1] & 0x0F
            raw[row * 4 + k] = (high << 4) | low
    return bytes(raw)


def decode_2bpp_halves_tile(raw: bytes | bytearray) -> list[list[int]]:
    """16 байт -> матрица 8x8 значений 0-3 (halves-порядок FireRed).

    Строка r: левые 4 px — байт raw[2r+1], правые 4 px — байт raw[2r],
    в каждом байте старший бит — левый пиксель (high-byte-first по
    DecompressGlyphTile из pokefirered). От planar decode_2bpp_tile
    отличается: там пара — битовые плоскости 8 px, здесь — две упакованные
    половины по 4 px.

    Raises:
        ValueError: raw короче 16 байт (лишние байты игнорируются).
    """
    _require_data(raw)
    if len(raw) < TILE_BYTES:
        raise ValueError(f"tile needs {TILE_BYTES} bytes, got {len(raw)}")
    grid: list[list[int]] = []
    for row in range(TILE_SIZE):
        left = raw[row * 2 + 1]
        right = raw[row * 2]
        line = [((left >> bit) & 3) for bit in (6, 4, 2, 0)]
        line += [((right >> bit) & 3) for bit in (6, 4, 2, 0)]
        grid.append(line)
    return grid


def encode_2bpp_halves_tile(grid: Sequence[Sequence[int]]) -> bytes:
    """Матрица 8x8 значений 0-3 -> 16 байт (обратное к decode_2bpp_halves_tile)."""
    _check_grid(grid, 3)
    raw = bytearray(TILE_BYTES)
    for row in range(TILE_SIZE):
        left = 0
        right = 0
        for k in range(4):
            left |= (grid[row][k] & 3) << (6 - 2 * k)
            right |= (grid[row][4 + k] & 3) << (6 - 2 * k)
        raw[row * 2 + 1] = left
        raw[row * 2] = right
    return bytes(raw)


_FRLG_LATIN_STRIDE = 0x40
_FRLG_LATIN_HALVES = (0x10, 0x30)


def decode_frlg_latin_glyph(slot: bytes | bytearray) -> tuple[list[list[int]], list[list[int]]]:
    """64-байтный слот latin-шрифта FRLG -> (верх 8x8, низ 8x8).

    Арт — halves-тайлы +0x10 (верх) и +0x30 (низ); пады +0x00/+0x20
    игнорируются без валидации (в ROM нули, формат их не требует).

    Raises:
        ValueError: слот короче 64 байт (лишние байты игнорируются).
    """
    _require_data(slot)
    if len(slot) < _FRLG_LATIN_STRIDE:
        raise ValueError(f"frlg glyph needs {_FRLG_LATIN_STRIDE} bytes, got {len(slot)}")
    top = decode_2bpp_halves_tile(bytes(slot[0x10 : 0x10 + TILE_BYTES]))
    bottom = decode_2bpp_halves_tile(bytes(slot[0x30 : 0x30 + TILE_BYTES]))
    return top, bottom


def encode_frlg_latin_glyph(top: Sequence[Sequence[int]], bottom: Sequence[Sequence[int]]) -> bytes:
    """(верх 8x8, низ 8x8) -> 64-байтный слот FRLG с нулевыми падами."""
    raw = bytearray(_FRLG_LATIN_STRIDE)
    raw[0x10 : 0x10 + TILE_BYTES] = encode_2bpp_halves_tile(top)
    raw[0x30 : 0x30 + TILE_BYTES] = encode_2bpp_halves_tile(bottom)
    return bytes(raw)


def decode_tile(raw: bytes | bytearray, bpp: int) -> list[list[int]]:
    """Декодирует тайл указанной глубины (строгий bpp)."""
    _require_bpp(bpp)
    if bpp == 1:
        return decode_1bpp_tile(raw)
    if bpp == 2:
        return decode_2bpp_tile(raw)
    return decode_4bpp_tile(raw)


def encode_tile(grid: Sequence[Sequence[int]], bpp: int) -> bytes:
    """Кодирует матрицу 8x8 в тайл указанной глубины (строгий bpp)."""
    _require_bpp(bpp)
    if bpp == 1:
        return encode_1bpp_tile(grid)
    if bpp == 2:
        return encode_2bpp_tile(grid)
    return encode_4bpp_tile(grid)


def tile_to_ascii(grid: Sequence[Sequence[int]], palette: str = _PIXELS) -> list[str]:
    """Матрица 8x8 значений 0-3 -> 8 строк ASCII-арта (2bpp-превью, non-goal для 4bpp).

    Пиксели валидируются как в encode (0-3, без bool) — превью мусора
    не рисует, а падает явно.
    """
    if not isinstance(palette, str) or len(palette) < 4:
        raise ValueError("palette must be a string of at least 4 characters")
    if not isinstance(grid, (list, tuple)):
        raise ValueError(f"grid must be 8x8, got {type(grid).__name__}")
    art: list[str] = []
    for row in grid:
        line = ""
        for pixel in row:
            if not isinstance(pixel, int) or isinstance(pixel, bool) or pixel < 0 or pixel > 3:
                raise ValueError(f"bad pixel value: {pixel!r}")
            line += palette[pixel]
        art.append(line)
    return art


def _require_halves(halves: object, stride: int, bpp: int) -> list[int]:
    tile = stride_for_bpp(bpp)
    if not isinstance(halves, (list, tuple)) or not halves:
        raise ValueError(f"font halves must be a non-empty list, got {halves!r}")
    offsets: list[int] = []
    for half in halves:
        if isinstance(half, bool) or not isinstance(half, int) or half < 0 or half + tile > stride:
            raise ValueError(f"bad halves offset {half!r} for stride {stride:#x}")
        offsets.append(half)
    if len(set(offsets)) != len(offsets):
        raise ValueError(f"font halves overlap: {offsets!r}")
    ordered = sorted(offsets)
    for first, second in pairwise(ordered):
        if first + tile > second:
            raise ValueError(f"font halves overlap: {offsets!r}")
    return offsets


def validate_font_meta(meta: dict, rom_len: int) -> dict:
    """Нормализует метаданные шрифта из GamePlugin.get_font_meta.

    Дефолты: bpp=2, stride по bpp, count до конца данных. Неизвестный bpp —
    строгий ValueError (fallback на 2 запрещён: молча портит данные).
    Split-раскладка: meta['halves'] — список смещений арт-тайлов внутри
    stride (FRLG latin: [0x10, 0x30] при stride 0x40); порядок значим,
    halves[0] — верх глифа. Без halves stride обязан совпадать с bpp
    (контигуальный блок).

    Raises:
        ValueError: meta не dict, offset/bpp/stride/count/halves вне
            диапазона, блок выходит за rom_len.
    """
    if not isinstance(meta, dict):
        raise ValueError(f"font meta must be a dict, got {type(meta).__name__}")
    if isinstance(rom_len, bool) or not isinstance(rom_len, int) or rom_len < 0:
        raise ValueError(f"bad rom_len: {rom_len!r}")
    if "offset" not in meta:
        raise ValueError("font meta needs 'offset'")
    offset = meta["offset"]
    bpp = meta.get("bpp", 2)
    stride = meta.get("stride", None)
    count = meta.get("count", None)
    halves = meta.get("halves", None)
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or offset >= rom_len:
        raise ValueError(f"bad font offset: {offset!r} for rom size {rom_len}")
    _require_bpp(bpp)
    if stride is None:
        stride = stride_for_bpp(bpp)
    if halves is None:
        if isinstance(stride, bool) or not isinstance(stride, int) or stride != stride_for_bpp(bpp):
            raise ValueError(f"bad stride {stride!r} for bpp={bpp}")
    else:
        if isinstance(stride, bool) or not isinstance(stride, int) or stride <= 0:
            raise ValueError(f"bad stride {stride!r} for split layout")
        halves = _require_halves(halves, stride, bpp)
    if count is None:
        count = (rom_len - offset) // stride
        if count < 1:
            raise ValueError(f"no room for font at offset {offset:#x}")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError(f"bad font count: {count!r}")
    if offset + count * stride > rom_len:
        raise ValueError(f"font [{offset:#x}:{offset + count * stride:#x}] exceeds rom size {rom_len}")
    norm: dict = {"offset": offset, "bpp": bpp, "stride": stride, "count": count}
    if halves is not None:
        norm["halves"] = halves
    return norm


def _require_layout(layout: dict) -> dict:
    if not isinstance(layout, dict):
        raise ValueError(f"font layout must be a dict, got {type(layout).__name__}")
    try:
        offset = layout["offset"]
        bpp = layout["bpp"]
        stride = layout["stride"]
        count = layout["count"]
    except KeyError as exc:
        raise ValueError(f"font layout needs {exc}") from exc
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError(f"bad font offset: {offset!r}")
    _require_bpp(bpp)
    halves = layout.get("halves", None)
    if halves is None:
        if isinstance(stride, bool) or not isinstance(stride, int) or stride != stride_for_bpp(bpp):
            raise ValueError(f"bad stride {stride!r} for bpp={bpp}")
    else:
        if isinstance(stride, bool) or not isinstance(stride, int) or stride <= 0:
            raise ValueError(f"bad stride {stride!r} for split layout")
        halves = _require_halves(halves, stride, bpp)
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError(f"bad font count: {count!r}")
    norm: dict = {"offset": offset, "bpp": bpp, "stride": stride, "count": count}
    if halves is not None:
        norm["halves"] = halves
    return norm


def _reject_split(norm: dict) -> None:
    if "halves" in norm:
        raise ValueError("split halves layout needs a glyph-aware path (follow-up), raw tiles refused")


def is_likely_compressed(data: bytes | bytearray, offset: int) -> bool:
    """Эвристика сжатия шрифта: GBA LZ77-заголовок 0x10 + размер.

    Не авторитетно: положительный ответ означает «писать сырые тайлы нельзя»,
    отрицательный — «сжатия не видно», а не «точно raw».
    """
    _require_data(data)
    if isinstance(offset, bool) or not isinstance(offset, int):
        raise ValueError(f"bad offset: {offset!r}")
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"offset {offset} out of range for data size {len(data)}")
    if data[offset] != 0x10:
        return False
    size = data[offset + 1] | (data[offset + 2] << 8) | (data[offset + 3] << 16)
    if size <= 0 or size > _LZ77_MAX_SIZE:
        return False
    return True


def _glyph_signatures(data: bytes | bytearray, offset: int, stride: int,
                      count: int, bpp: int) -> tuple[int, int, list[int], list[float]]:
    """Собирает признаки тайлов: число пустых, различных, уровней, однородности.

    Однородность — доля пикселей самого частого значения в тайле. У глифа
    фон доминирует (обычно > 0.5), у шума при 4bpp она около 1/16. Именно
    эта пара признаков отличает шрифт от произвольных данных: проверки
    «непусто» и «не один штамп» шум проходит всегда.

    `distinct` — число РАЗЛИЧНЫХ непустых тайлов (не число непустых):
    блок из одного повторяющегося тайла должен отсекаться, и для этого нужны
    именно различные, а не сосчитанные.
    """
    blank = 0
    seen: set[bytes] = set()
    levels: list[int] = []
    uniform: list[float] = []
    for i in range(count):
        raw = bytes(data[offset + i * stride : offset + (i + 1) * stride])
        grid = decode_tile(raw, bpp)
        flat = [pixel for row in grid for pixel in row]
        if all(pixel == 0 for pixel in flat):
            blank += 1
            continue
        seen.add(raw)
        levels.append(len(set(flat)))
        top = max(flat.count(v) for v in set(flat))
        uniform.append(top / len(flat))
    return blank, len(seen), levels, uniform


#: Среднее число уровней на тайл, выше которого блок не шрифт.
#:
#: Измерено на реальных данных (`scripts_roms/out/font_gate_real_roms.txt`):
#: настоящий латинский блок FireRed — 7.07-7.33 уровня на тайл при
#: однородности 0.61-0.67; произвольные данные FF4 Advance при bpp=4 — 12.16,
#: шум — 15.78. Порог 10.0 разделяет их с запасом с обеих сторон.
#:
#: Для 2bpp положительного контроля нет (ни одного подтверждённого 2bpp-шрифта
#: в проекте), значение 3.5 выбрано по устройству формата: глиф использует
#: 2-3 значения из 4, а шум — все 4. Для 1bpp признаки не работают: у
#: 1bpp-глифа и у шума одинаковое число уровней, поэтому порог отключён.
_MAX_MEAN_LEVELS = {1: None, 2: 3.5, 4: 10.0}
#: Средняя однородность, ниже которой блок не шрифт (шум при 4bpp — 0.12).
_MIN_MEAN_UNIFORM = {1: None, 2: 0.35, 4: 0.35}


def validate_font_candidate(
    data: bytes | bytearray,
    layout: dict,
    *,
    empty_ratio_max: float = 0.95,
    min_nonempty: int = 1,
    max_mean_levels: float | None = None,
    min_mean_uniform: float | None = None,
) -> dict:
    """Гейт кандидата шрифта: блок не пуст, не один штамп и не шум.

    Эвристика против позитивной mis-идентификации (см. фазу 0): доля пустых
    тайлов и число различных непустых обязаны пройти пороги. Сложность O(count):
    для огромных блоков layout обязан быть сужен вызывающей стороной, сверх
    _CANDIDATE_MAX_TILES — отказ.

    Одних «непусто» и «не один штамп» НЕДОСТАТОЧНО: на реальном FF4 Advance
    при bpp=4 так проходили первые же смещения (empty_ratio 0.000, 32
    различных тайла из 32), то есть гейт принимал произвольные данные.
    Поэтому добавлены два признака, которые у настоящего шрифта есть, а у
    шума нет: мало уровней на тайл и высокая однородность (фон глифа
    доминирует). После их добавления на том же FF4 Advance принято 0
    смещений из 512, а подтверждённый латинский блок FireRed проходит
    (7.07 уровня, однородность 0.67). Числа и пороги — в
    _MAX_MEAN_LEVELS / _MIN_MEAN_UNIFORM.
    """
    norm = _require_layout(layout)
    _reject_split(norm)
    if norm["count"] > _CANDIDATE_MAX_TILES:
        raise ValueError(f"font too large to scan: {norm['count']} > {_CANDIDATE_MAX_TILES}, narrow layout")
    _require_data(data)
    if isinstance(empty_ratio_max, bool) or not isinstance(empty_ratio_max, (int, float)):
        raise ValueError(f"bad empty_ratio_max: {empty_ratio_max!r}")
    if not 0.0 <= empty_ratio_max <= 1.0:
        raise ValueError(f"bad empty_ratio_max: {empty_ratio_max!r}")
    if isinstance(min_nonempty, bool) or not isinstance(min_nonempty, int) or min_nonempty < 1:
        raise ValueError(f"bad min_nonempty: {min_nonempty!r}")
    offset = norm["offset"]
    bpp = norm["bpp"]
    stride = norm["stride"]
    count = norm["count"]
    if offset + count * stride > len(data):
        raise ValueError(f"font [{offset:#x}:{offset + count * stride:#x}] exceeds data size {len(data)}")
    levels_max = _MAX_MEAN_LEVELS[bpp] if max_mean_levels is None \
        else max_mean_levels
    uniform_min = _MIN_MEAN_UNIFORM[bpp] if min_mean_uniform is None \
        else min_mean_uniform
    for name, value in (('max_mean_levels', levels_max),
                        ('min_mean_uniform', uniform_min)):
        if value is not None and (isinstance(value, bool)
                                  or not isinstance(value, (int, float))):
            raise ValueError(f"bad {name}: {value!r}")
    blank, seen, levels, uniform = _glyph_signatures(data, offset, stride,
                                                 count, bpp)
    empty_ratio = blank / count
    if empty_ratio > empty_ratio_max:
        raise ValueError(f"font candidate too empty: {empty_ratio:.2f} > {empty_ratio_max}")
    if seen < min_nonempty:
        raise ValueError(f"font candidate has {seen} distinct glyphs, need {min_nonempty}")
    mean_levels = sum(levels) / len(levels) if levels else 0.0
    mean_uniform = sum(uniform) / len(uniform) if uniform else 0.0
    if levels_max is not None and mean_levels > levels_max:
        raise ValueError(
            f"not a font: {mean_levels:.2f} levels per tile > {levels_max}")
    if uniform_min is not None and mean_uniform < uniform_min:
        raise ValueError(
            f"not a font: mean uniformity {mean_uniform:.2f} < {uniform_min}")
    return {"blank": blank, "distinct": seen, "empty_ratio": empty_ratio,
            "mean_levels": mean_levels, "mean_uniform": mean_uniform}


def inject_glyphs(
    data: bytearray,
    base_offset: int,
    glyphs: dict[int, bytes | bytearray | list[list[int]]],
    stride: int = TILE_BYTES,
    bpp: int = 2,
) -> list[dict]:
    """Вписывает глифы в буфер ROM in-place (механизм фазы 2).

    Каждый глиф кладётся по адресу base_offset + index * stride.
    Глиф — stride байт (доверенные как есть, ответственность вызывающей
    стороны) либо матрица 8x8 (кодируется под bpp).
    Поиск свободного места — non-goal (relocate шрифта невозможен без
    патча загрузчика): выход за границы — честный отказ.

    Raises:
        ValueError: неизвестный bpp, неверные типы stride/base_offset/
            glyphs/index, отрицательный индекс/stride, выход за границы,
            неверный размер глифа.
    """
    if isinstance(stride, bool) or not isinstance(stride, int) or stride <= 0:
        raise ValueError(f"stride must be a positive int, got {stride!r}")
    if isinstance(base_offset, bool) or not isinstance(base_offset, int) or base_offset < 0:
        raise ValueError(f"negative base_offset: {base_offset!r}")
    _require_bpp(bpp)
    if not isinstance(data, bytearray):
        raise ValueError(f"font buffer must be bytearray for writing, got {type(data).__name__}")
    if not isinstance(glyphs, dict):
        raise ValueError(f"glyphs must be a dict, got {type(glyphs).__name__}")
    try:
        ordered = sorted(glyphs)
    except TypeError as exc:
        raise ValueError(f"glyph indexes must be comparable ints: {exc}") from exc
    prepared: list[tuple[int, int, bytes]] = []
    for index in ordered:
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise ValueError(f"bad tile index: {index!r}")
        glyph = glyphs[index]
        if isinstance(glyph, (bytes, bytearray)):
            raw = bytes(glyph)
            if len(raw) != stride:
                raise ValueError(f"tile {index}: needs {stride} bytes, got {len(raw)}")
        else:
            raw = encode_tile(glyph, bpp)
            if len(raw) != stride:
                raise ValueError(f"tile {index}: encoded {len(raw)} bytes != stride {stride}")
        offset = base_offset + index * stride
        end = offset + stride
        if end > len(data):
            raise ValueError(f"tile {index} [{offset}:{end}] exceeds data size {len(data)}")
        prepared.append((index, offset, raw))
    report: list[dict] = []
    for index, offset, raw in prepared:
        data[offset : offset + stride] = raw
        report.append({"index": index, "offset": offset})
    return report


def preview_font_block(
    data: bytes | bytearray,
    layout: dict,
    glyphs: dict[int, bytes | bytearray | list[list[int]]],
) -> list[dict]:
    """Dry-run записи шрифта: [{index, offset, old_bytes, new_bytes}] без записи."""
    norm = _require_layout(layout)
    _reject_split(norm)
    _require_data(data)
    if norm["offset"] + norm["count"] * norm["stride"] > len(data):
        raise ValueError(
            f"font [{norm['offset']:#x}:{norm['offset'] + norm['count'] * norm['stride']:#x}]"
            f" exceeds data size {len(data)}"
        )
    if not isinstance(glyphs, dict) or not glyphs:
        raise ValueError("glyphs must be a non-empty dict")
    offset = norm["offset"]
    bpp = norm["bpp"]
    stride = norm["stride"]
    count = norm["count"]
    try:
        ordered = sorted(glyphs)
    except TypeError as exc:
        raise ValueError(f"glyph indexes must be comparable ints: {exc}") from exc
    plan: list[dict] = []
    for index in ordered:
        if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= count:
            raise ValueError(f"tile index out of font range 0-{count - 1}: {index!r}")
        glyph = glyphs[index]
        if isinstance(glyph, (bytes, bytearray)):
            raw = bytes(glyph)
            if len(raw) != stride:
                raise ValueError(f"tile {index}: needs {stride} bytes, got {len(raw)}")
        else:
            raw = encode_tile(glyph, bpp)
        at = offset + index * stride
        plan.append({"index": index, "offset": at, "old_bytes": bytes(data[at : at + stride]), "new_bytes": raw})
    return plan


def inject_font_block(
    data: bytearray,
    layout: dict,
    glyphs: dict[int, bytes | bytearray | list[list[int]]],
    *,
    confirm: bool = False,
    allow_compressed: bool = False,
) -> list[dict]:
    """Запись шрифтового блока с гейтами: confirm + compressed-отказ.

    Атомарно: при ошибке позднего тайла буфер нетронут. Backup и checksum —
    задача вызывающей стороны (TextInjector.save пересчитывает checksum'ы,
    исходный файл сохраняется записью в новый путь).
    """
    if confirm is not True:
        raise ValueError("font injection needs explicit confirm=True")
    norm = _require_layout(layout)
    _reject_split(norm)
    if not isinstance(data, bytearray):
        raise ValueError(f"font buffer must be bytearray for writing, got {type(data).__name__}")
    if norm["offset"] + norm["count"] * norm["stride"] > len(data):
        raise ValueError(
            f"font [{norm['offset']:#x}:{norm['offset'] + norm['count'] * norm['stride']:#x}]"
            f" exceeds data size {len(data)}"
        )
    if not allow_compressed and is_likely_compressed(data, norm["offset"]):
        raise ValueError(f"font at {norm['offset']:#x} looks compressed, raw injection refused")
    plan = preview_font_block(data, norm, glyphs)
    report: list[dict] = []
    for item in plan:
        at = item["offset"]
        raw = item["new_bytes"]
        data[at : at + len(raw)] = raw
        report.append({"index": item["index"], "offset": at, "bpp": norm["bpp"]})
    return report


def tiles_from_rom(data: bytes | bytearray, offset: int, count: int, stride: int = TILE_BYTES) -> list[bytes]:
    """Вырезает count тайлов по stride байт из данных с offset.

    Без cap: count, покрывающий мегабайты, материализует огромный список —
    обязанность сужать count на вызывающей стороне.

    Raises:
        ValueError: неверные типы data/offset/count/stride, неположительный
            stride, отрицательные offset/count или выход за границы.
    """
    _require_data(data)
    if isinstance(stride, bool) or not isinstance(stride, int) or stride <= 0:
        raise ValueError(f"stride must be a positive int, got {stride!r}")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError(f"bad offset: {offset!r}")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError(f"bad count: {count!r}")
    end = offset + count * stride
    if end > len(data):
        raise ValueError(f"tiles [{offset}:{end}] exceed data size {len(data)}")
    return [bytes(data[i : i + stride]) for i in range(offset, end, stride)]


def font_grids_to_image(grids: Sequence[Sequence[Sequence[int]]], *, columns: int = 16, scale: int = 1) -> Image.Image:
    """Сетка глифов 8x8 (значения 0-15) -> PIL Image mode P для ревью/импорта.

    Неполный последний ряд добивается чёрными тайлами: после image_to_grids
    результат обрезается вызывающей стороной до исходного count.
    """
    if not isinstance(grids, (list, tuple)) or not grids:
        raise ValueError("grids must be a non-empty list")
    if isinstance(columns, bool) or not isinstance(columns, int) or columns < 1:
        raise ValueError(f"bad columns: {columns!r}")
    if isinstance(scale, bool) or not isinstance(scale, int) or scale < 1:
        raise ValueError(f"bad scale: {scale!r}")
    for grid in grids:
        _check_grid(grid, _GRAY_LEVELS - 1)
    rows = (len(grids) + columns - 1) // columns
    img = Image.new("P", (columns * TILE_SIZE * scale, rows * TILE_SIZE * scale))
    palette: list[int] = []
    for i in range(256):
        level = i * 17 if i < _GRAY_LEVELS else 0
        palette.extend((level, level, level))
    img.putpalette(palette)
    for pos, grid in enumerate(grids):
        base_x = (pos % columns) * TILE_SIZE * scale
        base_y = (pos // columns) * TILE_SIZE * scale
        for r in range(TILE_SIZE):
            for c in range(TILE_SIZE):
                value = grid[r][c]
                for dy in range(scale):
                    for dx in range(scale):
                        img.putpixel((base_x + c * scale + dx, base_y + r * scale + dy), value)
    return img


def image_to_grids(image: Image.Image, *, bpp: int) -> list[list[list[int]]]:
    """PIL Image mode P -> список матриц 8x8 (индексы обязаны влезть в bpp)."""
    _require_bpp(bpp)
    if getattr(image, "mode", None) != "P":
        raise ValueError(f"font image must be mode P, got {getattr(image, 'mode', None)!r}")
    width, height = image.size
    if width < TILE_SIZE or height < TILE_SIZE or width % TILE_SIZE or height % TILE_SIZE:
        raise ValueError(f"bad font image size: {width}x{height}, must be multiples of 8")
    maxval = (1 << bpp) - 1
    grids: list[list[list[int]]] = []
    for ty in range(height // TILE_SIZE):
        for tx in range(width // TILE_SIZE):
            grid: list[list[int]] = []
            for r in range(TILE_SIZE):
                line: list[int] = []
                for c in range(TILE_SIZE):
                    value = image.getpixel((tx * TILE_SIZE + c, ty * TILE_SIZE + r))
                    if not isinstance(value, int) or value < 0 or value > maxval:
                        raise ValueError(f"pixel out of range 0-{maxval}: {value!r}")
                    line.append(value)
                grid.append(line)
            grids.append(grid)
    return grids


def build_font_manifest(chars: list[str] | str, start_index: int = 0) -> dict[str, int]:
    """Манифест char -> tile index с start_index (дубли — отказ)."""
    if isinstance(chars, str):
        items: list[str] = list(chars)
    else:
        try:
            items = list(chars)
        except TypeError as exc:
            raise ValueError(f"chars must be a sequence: {chars!r}") from exc
    if isinstance(start_index, bool) or not isinstance(start_index, int) or start_index < 0:
        raise ValueError(f"bad start_index: {start_index!r}")
    manifest: dict[str, int] = {}
    for pos, char in enumerate(items):
        if not isinstance(char, str) or not char:
            raise ValueError(f"bad char at {pos}: {char!r}")
        if char in manifest:
            raise ValueError(f"duplicate char: {char!r}")
        manifest[char] = start_index + pos
    return manifest


def validate_glyph_widths(widths: list[int], count: int) -> list[int]:
    """Ширины глифов VWF отдельно от тайлов: len == count, каждая 1-8."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError(f"bad count: {count!r}")
    try:
        items = list(widths)
    except TypeError as exc:
        raise ValueError(f"widths must be a sequence: {widths!r}") from exc
    if len(items) != count:
        raise ValueError(f"widths len {len(items)} != font count {count}")
    for value in items:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > TILE_SIZE:
            raise ValueError(f"bad glyph width: {value!r}")
    return items
