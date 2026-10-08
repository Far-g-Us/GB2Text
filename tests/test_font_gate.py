"""Гейт кандидата шрифта должен отличать глифы от шума.

Мотивация — измерение: до добавления уровней и однородности гейт на реальном
FF4 Advance при bpp=4 пропускал первые же смещения (empty_ratio 0.000,
32 различных тайла из 32), то есть принимал произвольные данные.
"""
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.font_tiles import (
    TILE_BYTES_2BPP,
    TILE_BYTES_4BPP,
    encode_tile,
    validate_font_candidate,
)


def _glyph(seed: int, ink: int = 1) -> list[list[int]]:
    """Правдоподобный глиф: фон плюс рамка и вертикаль — 1-2 уровня."""
    grid = [[0] * 8 for _ in range(8)]
    for x in range(8):
        grid[0][x] = ink
        grid[7][x] = ink
    for y in range(8):
        grid[y][0] = ink
        grid[y][7] = ink
    if seed % 3 == 0:
        grid[3][4] = ink
    if seed % 3 == 1:
        grid[4][4] = ink
    return grid


def _font_block(count: int, bpp: int, stride: int) -> bytearray:
    out = bytearray()
    for i in range(count):
        if i % 11 == 0:
            out += bytes(stride)          # пустой глиф (пробел)
        else:
            out += bytes(encode_tile(_glyph(i), bpp))
    return out


def test_synthetic_font_passes_gate():
    for bpp, stride in ((2, TILE_BYTES_2BPP), (4, TILE_BYTES_4BPP)):
        data = _font_block(64, bpp, stride)
        report = validate_font_candidate(
            data, {'offset': 0, 'bpp': bpp, 'stride': stride, 'count': 64})
        assert report['mean_levels'] <= 3.0
        assert report['mean_uniform'] >= 0.45


def test_random_noise_rejected_4bpp():
    """Шум при 4bpp использует почти все 16 уровней и не бывает однородным."""
    rng = random.Random(20240117)
    data = bytearray(rng.randrange(256) for _ in range(64 * TILE_BYTES_4BPP))
    with pytest.raises(ValueError) as exc:
        validate_font_candidate(
            data, {'offset': 0, 'bpp': 4, 'stride': TILE_BYTES_4BPP,
                   'count': 64})
    assert 'not a font' in str(exc.value)


def test_random_noise_rejected_2bpp():
    rng = random.Random(7)
    data = bytearray(rng.randrange(256) for _ in range(64 * TILE_BYTES_2BPP))
    with pytest.raises(ValueError):
        validate_font_candidate(
            data, {'offset': 0, 'bpp': 2, 'stride': TILE_BYTES_2BPP,
                   'count': 64})


def test_one_stamp_block_rejected():
    """Блок из одного повторяющегося тайла — не шрифт."""
    data = bytes(encode_tile(_glyph(1), 2)) * 32
    with pytest.raises(ValueError) as exc:
        validate_font_candidate(
            data, {'offset': 0, 'bpp': 2, 'stride': TILE_BYTES_2BPP,
                   'count': 32}, min_nonempty=4)
    assert 'distinct glyphs' in str(exc.value)


def test_blank_block_rejected():
    data = bytes(32 * TILE_BYTES_2BPP)
    with pytest.raises(ValueError) as exc:
        validate_font_candidate(
            data, {'offset': 0, 'bpp': 2, 'stride': TILE_BYTES_2BPP,
                   'count': 32}, empty_ratio_max=0.5)
    assert 'too empty' in str(exc.value)


def test_1bpp_thresholds_disabled():
    """Для 1bpp пороги уровней/однородности отключены: шум неотличим."""
    rng = random.Random(1)
    data = bytearray(rng.randrange(256) for _ in range(32 * 8))
    report = validate_font_candidate(
        data, {'offset': 0, 'bpp': 1, 'stride': 8, 'count': 32})
    assert 'mean_levels' in report
    assert 'mean_uniform' in report


def test_gate_rejects_bad_threshold_types():
    data = _font_block(16, 2, TILE_BYTES_2BPP)
    layout = {'offset': 0, 'bpp': 2, 'stride': TILE_BYTES_2BPP, 'count': 16}
    for kwargs in ({'max_mean_levels': 'x'}, {'min_mean_uniform': True}):
        with pytest.raises(ValueError):
            validate_font_candidate(data, layout, **kwargs)


def test_gate_keeps_working_on_real_rom_offset():
    """Проверка на реальном файле: мусорные смещения FF4 отвергаются.

    Тест условный: без копии ROM он пропускается, чтобы не врать в CI.
    """
    rom = (r'C:\Users\EndY\AppData\Local\Temp\opencode\rom_work'
           r'\Final Fantasy IV Advance (USA).gba')
    if not os.path.exists(rom):
        pytest.skip('нет копии ROM')
    data = open(rom, 'rb').read()
    layout = {'offset': 0, 'bpp': 4, 'stride': TILE_BYTES_4BPP, 'count': 32}
    with pytest.raises(ValueError) as exc:
        validate_font_candidate(data, layout)
    assert 'not a font' in str(exc.value)
