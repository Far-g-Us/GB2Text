"""`core/tile_picture.py` (замена картинки из тайлов) и `core/segment_audit.py`.

Фикстуры тайлов намеренно ПОХОЖИ НА ГРАФИКУ (плоские участки, горизонтальные
штрихи): гард «похоже ли на графику» отличает плоское от шума по соседним
одинаковым пикселям, и «шумная» фикстура падала бы не по своей причине.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core import segment_audit as _sa
from core.font_tiles import decode_tile, encode_tile, stride_for_bpp
from core.segment_audit import SegmentAudit, _monotonic_run, audit_fixed_slots
from core.tile_picture import (
    PictureError,
    apply_picture,
    looks_like_graphics,
    preview_to_png,
    read_png,
)

BASE = 0x2000
STRIDE = stride_for_bpp(4)


def _glyph(seed: int, bpp: int = 4):
    """Тайл-буква: стойка + перекладины, много плоских участков."""
    grid = [[0] * 8 for _ in range(8)]
    ink = 1 + (seed % max(1, (2 ** bpp) - 1))       # в пределах палитры bpp
    for r in range(1, 7):
        grid[r][1] = ink
        grid[r][2] = ink
    for r in (1, 3, 5):
        for c in range(1, 7):
            grid[r][c] = ink
    return grid


def _noise(seed: int):
    """Тайл-шум: значение меняется на каждом пикселе (код/данные)."""
    return [[(r * 5 + c * 3 + seed) % 16 for c in range(8)] for r in range(8)]


def _glyph_tiles(count: int) -> list[bytes]:
    return [bytes(encode_tile(_glyph(i), 4)) for i in range(count)]


def _rom(tiles: list[bytes], room: int = 32) -> bytearray:
    """ROM с тайлами по BASE; `room` — сколько тайлов влезает (с запасом)."""
    blob = bytearray(BASE + room * STRIDE + 16)
    for i, tile in enumerate(tiles):
        blob[BASE + i * STRIDE:BASE + (i + 1) * STRIDE] = tile
    return blob


def _tags(tiles: int, bpp: int, scale: int):
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text('gb2text_tiles', str(tiles))
    info.add_text('gb2text_bpp', str(bpp))
    info.add_text('gb2text_scale', str(scale))
    return info

def _preview(rom: bytes, count: int, tmp_path, name='p.png', bpp: int = 4):
    png = tmp_path / name
    preview_to_png(rom, BASE, bpp, count, path=png)
    return png


# ── графика: круговой путь без потерь ─────────────────────────────────────


def test_unchanged_picture_comes_back_byte_exact(tmp_path):
    """Неизменённая картинка обязана вернуться байт в байт.

    Раньше сэмплер пикселей был необратим (игнорировал масштаб превью и
    возвращал 60 чужих пикселей из 64), и круговой путь менял до 196 байт из 512.
    Теперь сэмплер сверяется с палитрой PNG, поэтому изменить байты может только
    реальная правка картинки.
    """
    rom = bytes(_rom(_glyph_tiles(16)))
    grids = read_png(_preview(rom, 16, tmp_path), 4, 16)
    patched, stats = apply_picture(rom, BASE, 4, 16, grids)
    assert patched == rom
    assert stats['changed_bytes'] == 0
    assert stats['unchanged_tiles'] == 16


@pytest.mark.parametrize('bpp', [1, 2, 4])
def test_roundtrip_works_for_every_bpp(tmp_path, bpp):
    tiles = [bytes(encode_tile(_glyph(i, bpp), bpp)) for i in range(8)]
    rom = bytes(_rom(tiles))
    png = tmp_path / f'p{bpp}.png'
    preview_to_png(rom, BASE, bpp, 8, path=png)
    grids = read_png(png, bpp, 8)
    patched, stats = apply_picture(rom, BASE, bpp, 8, grids)
    assert stats['identical_pixels'] is True
    again, second = apply_picture(patched, BASE, bpp, 8, grids)
    assert second['changed_bytes'] == 0
    assert again == patched


def test_edited_tile_is_stored_and_others_keep_their_picture(tmp_path):
    rom = bytes(_rom(_glyph_tiles(4)))
    grids = [decode_tile(rom[BASE + i * STRIDE:BASE + (i + 1) * STRIDE], 4)
             for i in range(4)]
    grids[2] = [[7] * 8 for _ in range(8)]
    patched, _stats = apply_picture(rom, BASE, 4, 4, grids)
    for i, grid in enumerate(grids):
        got = decode_tile(patched[BASE + i * STRIDE:BASE + (i + 1) * STRIDE], 4)
        assert got == grid, f'тайл {i} не совпал с запрошенным'
    assert patched[:BASE] == rom[:BASE]


def test_apply_is_idempotent(tmp_path):
    rom = bytes(_rom(_glyph_tiles(8)))
    grids = read_png(_preview(rom, 8, tmp_path), 4, 8)
    first, _ = apply_picture(rom, BASE, 4, 8, grids)
    second, stats = apply_picture(first, BASE, 4, 8, grids)
    assert stats['changed_bytes'] == 0
    assert second == first


# ── гард «графика или код» ────────────────────────────────────────────────


def test_graphics_gate_accepts_letter_like_block(tmp_path):
    rom = bytes(_rom(_glyph_tiles(8)))
    grids = read_png(_preview(rom, 8, tmp_path), 4, 8)
    _patched, stats = apply_picture(rom, BASE, 4, 8, grids)
    assert stats['looks_like_graphics'] is True
    assert stats['graphics_score']['median'] >= \
        stats['graphics_score']['threshold']


def test_graphics_gate_refuses_code_like_block(tmp_path):
    """Round-trip безупречен для ЛЮБЫХ 32 байт, поэтому отличает гейт по виду."""
    rom = bytes(_rom([bytes(encode_tile(_noise(i), 4)) for i in range(8)]))
    grids = read_png(_preview(rom, 8, tmp_path, 'code.png'), 4, 8)
    with pytest.raises(PictureError, match='не похож на графику'):
        apply_picture(rom, BASE, 4, 8, grids)


def test_force_overrides_graphics_gate(tmp_path):
    rom = bytes(_rom([bytes(encode_tile(_noise(i), 4)) for i in range(8)]))
    grids = read_png(_preview(rom, 8, tmp_path, 'c.png'), 4, 8)
    patched, stats = apply_picture(rom, BASE, 4, 8, grids, force=True)
    assert stats['looks_like_graphics'] is False
    assert patched == rom


def test_graphics_score_separates_letters_from_noise():
    """Порог откалиброван замером; тест фиксирует, что зазор реально есть."""
    letters = b''.join(_glyph_tiles(24))
    noise = b''.join(bytes(encode_tile(_noise(i), 4)) for i in range(24))
    ok_letters, score_letters = looks_like_graphics(letters, 0, 4, 24, STRIDE)
    ok_noise, score_noise = looks_like_graphics(noise, 0, 4, 24, STRIDE)
    assert ok_letters is True
    assert ok_noise is False
    assert score_letters['median'] > score_noise['median']


def test_any_bytes_decode_as_4bpp_tile():
    """Свойство формата, а не защита: 4bpp читает любые 32 байта как тайл.

    Отсюда и нужен гард по виду пикселей, а не проверкой «читается ли».
    """
    blob = bytes(range(32))
    assert bytes(encode_tile(decode_tile(blob, 4), 4)) == blob


# ── отказы по границам ────────────────────────────────────────────────────


def test_block_outside_rom_is_refused():
    rom = bytes(_rom(_glyph_tiles(1)))
    grids = [decode_tile(rom[BASE:BASE + STRIDE], 4)] * 4
    with pytest.raises(PictureError, match='не помещается'):
        apply_picture(rom, len(rom) - 8, 4, 4, grids)


def test_wrong_tile_count_is_refused():
    rom = bytes(_rom(_glyph_tiles(4)))
    grids = [decode_tile(rom[BASE + i * STRIDE:BASE + (i + 1) * STRIDE], 4)
             for i in range(4)]
    with pytest.raises(PictureError, match='Тайлов в картинке'):
        apply_picture(rom, BASE, 4, 2, grids)


def test_png_from_another_block_is_refused(tmp_path):
    rom = bytes(_rom(_glyph_tiles(24)))
    png = _preview(rom, 20, tmp_path, 'other.png')
    with pytest.raises(PictureError, match='другого участка'):
        read_png(png, 4, 8)


def test_missing_png_is_reported():
    with pytest.raises(PictureError, match='не найден'):
        read_png('нет-такого.png', 4, 4)



# ── регрессии из ревью ─────────────────────────────────────────────────────


def test_output_cannot_overwrite_source_rom(tmp_path):
    """pply -o <тот же файл> обязан отказать: исходник не перезаписывается.

    Обещание «исходный ROM не изменяется никогда» проверяется не декстрингом,
    а кодом — иначе picture apply был единственной командой без такого гарда.
    """
    from api._core import SDKError, ensure_not_source

    rom = tmp_path / 'src.gba'
    rom.write_bytes(bytes(_rom(_glyph_tiles(2))))
    with pytest.raises(SDKError) as excinfo:
        ensure_not_source(str(rom), str(rom))
    assert excinfo.value.code == 'VALIDATION_ERROR'
    assert rom.read_bytes() == bytes(_rom(_glyph_tiles(2)))


def test_png_without_metadata_is_refused(tmp_path):
    """Редактор срезает tEXt при пересохранении — это должно быть отказом.

    Раньше такой PNG принимался как «любая картинка», и apply заливал им
    произвольный участок ROM.
    """
    from PIL import Image

    png = tmp_path / 'stripped.png'
    Image.new('P', (32, 8)).save(png)
    assert Image.open(png).text.get('gb2text_tiles') is None
    with pytest.raises(PictureError, match='gb2text_tiles'):
        read_png(png, 4, 1)


def test_png_from_different_bpp_is_refused(tmp_path):
    """Превью 4bpp, применённое как 2bpp, испортило бы картинку — нужен отказ."""
    rom = bytes(_rom(_glyph_tiles(4)))
    png = _preview(rom, 4, tmp_path, 'p4.png')
    with pytest.raises(PictureError, match='4 bpp'):
        read_png(png, 2, 4)


def test_bpp_8_is_refused_as_unsupported(tmp_path):
    """stride_for_bpp не знает 8: обещать его в CLI было неправдой."""
    rom = bytes(_rom(_glyph_tiles(1)))
    with pytest.raises(PictureError, match='bpp=8'):
        preview_to_png(rom, BASE, 8, 1, path=tmp_path / 'p.png')


def test_random_tiles_roundtrip_byte_exact(tmp_path):
    """Сильнейшая доступная проверка: случайные байты как графика.

    Фикстуры-буквы лежат по одну сторону гарда от настоящего шрифта, поэтому
    сам по себе тест на них ничего не доказывает. 64 случайных тайла на каждой
    глубине проверяют и сэмплер, и кодер на данных, которых никто не рисовал.
    """
    import random

    rng = random.Random(20241006)
    for bpp in (1, 2, 4):
        tiles = [bytes(rng.randrange(256) for _ in range(32)) for _ in range(64)]
        rom = bytes(_rom(tiles))
        grids = read_png(_preview(rom, 64, tmp_path, f'r{bpp}.png', bpp), bpp, 64)
        patched, stats = apply_picture(rom, BASE, bpp, 64, grids, force=True)
        assert patched == rom, f'bpp={bpp} потерял байты'
        assert stats['changed_bytes'] == 0
        assert stats['unchanged_tiles'] == 64
        assert apply_picture(patched, BASE, bpp, 64, grids, force=True)[0] == patched


def test_preview_rejects_absurd_tile_count(tmp_path):
    """Потолок нужен: рендер всего 32-МеБ ROM — это десятки минут и ~1 ГБ."""
    rom = bytes(_rom(_glyph_tiles(1), room=0))
    with pytest.raises(PictureError, match='максимум'):
        preview_to_png(rom, BASE, 4, 5000, path=tmp_path / 'big.png')


@pytest.mark.parametrize('mode', ['RGB', 'RGBA', 'L'])
def test_non_palette_png_survives_roundtrip(tmp_path, mode):
    """Правка в обычном редакторе (RGB/RGBA/L) обязана остаться пиксель в пиксель.

    Раньше рампа была i * (255 // (levels - 1)), что для 1bpp давало {0,255}
    вместо {0,17}: вся картинка молча схлопывалась в ноль и apply писал это как
    обычную правку.
    """
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    rom = bytes(_rom(_glyph_tiles(8)))
    png = _preview(rom, 8, tmp_path, 'p.png')
    # Редактор сохранил в другом режиме, сохранив картинку один в один.
    with Image.open(png) as src:
        info = PngInfo()
        for key, value in (src.text or {}).items():
            info.add_text(key, value)
        flat = src.convert(mode)
    flat.save(png, pnginfo=info)
    with Image.open(png) as check:
        assert check.mode == mode
        assert check.text.get('gb2text_tiles') is not None
    patched, stats = apply_picture(rom, BASE, 4, 8, read_png(png, 4, 8))
    assert stats['identical_pixels'] is True
    assert patched == rom, f'режим {mode} потерял пиксели'


def test_save_atomic_leaves_no_temp_file(tmp_path):
    """Запись должна быть атомарной, а tmp — не оставаться на диске."""
    from core.tile_picture import save_atomic

    dest = tmp_path / 'out.gba'
    save_atomic(dest, b'hello')
    assert dest.read_bytes() == b'hello'
    assert list(tmp_path.iterdir()) == [dest]



def test_missing_scale_metadata_is_refused(tmp_path):
    """Потерянный масштаб = мусор в ROM при «успешном» отчёте (191 байт из 512).

    Сэмплер при scale=1 читал левый верхний угол каждого тайла как отдельный
    тайл, поэтому проверка identical_pixels подтверждала только то, что записано
    то, что подали.
    """
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    rom = bytes(_rom(_glyph_tiles(8)))
    png = _preview(rom, 8, tmp_path, 'p.png')
    with Image.open(png) as src:
        info = PngInfo()
        info.add_text('gb2text_tiles', '8')
        info.add_text('gb2text_bpp', '4')
        src.copy().save(png, pnginfo=info)
    with Image.open(png) as check:
        assert check.text.get('gb2text_scale') is None
    with pytest.raises(PictureError, match='gb2text_scale'):
        read_png(png, 4, 8)


def test_resized_preview_is_refused(tmp_path):
    """Обрезанное/отмасштабированное превью ловится проверкой геометрии."""
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    rom = bytes(_rom(_glyph_tiles(8)))
    png = _preview(rom, 8, tmp_path, 'p.png')
    with Image.open(png) as src:
        text = dict(src.text or {})
        half = src.resize((src.size[0] // 2, src.size[1] // 2))
    info = PngInfo()
    for key, value in text.items():
        info.add_text(key, value)
    half.save(png, pnginfo=info)
    with pytest.raises(PictureError, match='Геометрия'):
        read_png(png, 4, 8)


def test_repaletted_png_is_refused(tmp_path):
    """Не-серая палитра mode P раньше роняла наружу сырое ValueError -> INTERNAL."""
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    rom = bytes(_rom(_glyph_tiles(4)))
    png = _preview(rom, 4, tmp_path, 'p.png')
    with Image.open(png) as src:
        text = dict(src.text or {})
        recoloured = src.convert('RGB').convert('P', palette=Image.ADAPTIVE,
                                                colors=8)
    info = PngInfo()
    for key, value in text.items():
        info.add_text(key, value)
    recoloured.save(png, pnginfo=info)
    with pytest.raises(PictureError, match='серая рамка'):
        read_png(png, 4, 4)


def test_cli_parser_rejects_bpp_8():
    """argparse сам отвергает 8: --bpp {1,2,4}, а не «1,2,4,8» с рантайм-ошибкой."""
    from api import cli

    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(
            ['picture', 'rom.gba', 'preview', '--offset', '0x100',
             '--count', '4', '--bpp', '8'])


def test_preview_output_must_be_png(tmp_path):
    """preview в .gba раньше падал сырым ValueError от PIL."""
    from api import _core

    rom = tmp_path / 'game.gba'
    rom.write_bytes(bytes(_rom(_glyph_tiles(4))))
    with pytest.raises(Exception) as excinfo:
        _core.picture(str(rom), action='preview', offset=BASE, bpp=4, count=4,
                      output=str(tmp_path / 'out.gba'))
    assert excinfo.value.__class__.__name__ == 'SDKError'


def test_hardlink_to_source_is_refused(tmp_path):
    """Hardlink: путь другой, файл тот же — ловит os.path.samefile."""
    import os

    from api._core import SDKError, ensure_not_source

    rom = tmp_path / 'src.gba'
    rom.write_bytes(bytes(_rom(_glyph_tiles(2))))
    hard = tmp_path / 'hard.gba'
    os.link(rom, hard)
    before = rom.read_bytes()
    with pytest.raises(SDKError):
        ensure_not_source(str(rom), str(hard))
    assert rom.read_bytes() == before



@pytest.mark.parametrize('count', [17, 24, 33])
def test_partial_last_row_roundtrip_is_byte_exact(tmp_path, count):
    """Частично заполненный последний ряд — отдельный случай геометрии.

    Именно count, не кратный 16, задействует rows = ceil(count / columns) и
    усечение grids[:count]. Регрессия в формуле проверки геометрии прошла бы
    при зелёном суите, если бы не этот тест.
    """
    import random

    rng = random.Random(count)
    tiles = [bytes(rng.randrange(256) for _ in range(32)) for _ in range(count)]
    rom = bytes(_rom(tiles, room=0))
    grids = read_png(_preview(rom, count, tmp_path, f'c{count}.png'), 4, count)
    patched, stats = apply_picture(rom, BASE, 4, count, grids, force=True)
    assert patched == rom
    assert stats['unchanged_tiles'] == count


def test_zero_tiles_metadata_is_refused(tmp_path):
    """Подделанный gb2text_tiles=0 раньше давал ZeroDivisionError наружу."""
    from PIL import Image

    png = tmp_path / 'zero.png'
    Image.new('P', (32, 32)).save(png, pnginfo=_tags(0, 4, 4))
    with pytest.raises(PictureError, match='gb2text_tiles'):
        read_png(png, 4, 0)


def test_save_atomic_uses_unpredictable_tmp_name(tmp_path):
    """Предсказуемый dest + '.tmp' позволял симлинк увести запись в чужой файл."""
    from core.tile_picture import save_atomic

    dest = tmp_path / 'rom.gba'
    save_atomic(dest, b'payload')
    assert dest.read_bytes() == b'payload'
    # Предсказуемого хвоста не осталось: mkstemp даёт случайное имя.
    assert not (tmp_path / 'rom.gba.picture.tmp').exists()
    assert [p.name for p in tmp_path.iterdir()] == ['rom.gba']



# ── долги из ревью: TOCTOU, один проход по ROM, симлинк ──────────────────────


def test_png_is_opened_only_once(tmp_path):
    """Двойное открытие = TOCTOU: между проверкой и чтением файл подменяют."""
    import PIL.Image
    from PIL.Image import open as pil_open

    rom = bytes(_rom(_glyph_tiles(8)))
    png = _preview(rom, 8, tmp_path, 'p.png')
    calls = []

    def counting(fp, *a, **kw):
        calls.append(fp)
        return pil_open(fp, *a, **kw)

    PIL.Image.open = counting
    try:
        read_png(png, 4, 8)
    finally:
        PIL.Image.open = pil_open
    assert len(calls) == 1, f'PNG открыт {len(calls)} раз(а)'


def test_run_length_through_matches_bruteforce():
    """Прогон «через окно» обязан совпадать с перебором по всем подотрезкам."""
    import random

    rng = random.Random(4242)
    for _ in range(300):
        targets = [rng.randrange(6) for _ in range(rng.randrange(1, 14))]
        got = {off: length for off, _t, length
               in _sa._run_length_through(
                   [(i, t) for i, t in enumerate(targets)])}
        for index in range(len(targets)):
            want = 1
            for lo in range(len(targets)):
                for hi in range(lo, len(targets)):
                    if lo <= index <= hi and all(
                            targets[k] < targets[k + 1] for k in range(lo, hi)):
                        want = max(want, hi - lo + 1)
            assert got.get(index) == want, (targets, index, got, want)


def test_confirmed_pointers_ignore_foreign_run():
    """Одиночный указатель НЕ подтверждается чужой серией из того же участка.

    Старая версия брала максимум по всему непрерывному участку, поэтому указатель
    в начале шумного блока получал подтверждение от монотонной серии в его конце.
    """
    rom = bytearray(0x40000)
    width = SLOT_WIDTH
    start = SLOT_START
    for i in range(SLOT_COUNT):
        tile = bytes(encode_tile(_glyph(i), 4))
        at = start + i * width
        rom[at:at + width] = tile
    data = bytearray(rom)
    # Сначала одинокий «указатель» на хвост слота, затем серия из 4 монотонных.
    lonely = 0x30000
    data[lonely:lonely + 4] = (0x08000000 + start + 5).to_bytes(4, 'little')
    series = 0x31000
    for i in range(4):
        # Цель ВНУТРИ слота (+4, не на начале): иначе сработало бы исключение
        # `target in slot_starts`, и проверялась бы не монотонность.
        data[series + i * 4:series + i * 4 + 4] = (
            0x08000000 + start + i * width + 4).to_bytes(4, 'little')
    confirmed = {}
    index = _sa._SegmentIndex([(start, start + SLOT_COUNT * width)])
    slot_starts = {start + i * width for i in range(SLOT_COUNT)}
    for run_start, run_len in _sa._iter_run_bounds(bytes(data), len(data)):
        _sa._collect_run(bytes(data), run_start, run_len, len(data),
                         confirmed, slot_starts, index)
    span_bounds = (start, start + SLOT_COUNT * width)
    confirmed = confirmed.get(span_bounds, [])
    assert lonely not in {item['pointer_at'] for item in confirmed}
    assert any(item['pointer_at'] == series for item in confirmed)


def test_run_bounds_cuts_on_gap_and_on_non_increase():
    """Пропуск окна и убывание цели ОБА разрывают прогон.

    Без разрезания по убыванию указатель в начале шумного блока получил бы длину
    чужой серии из его конца; без разрезания по пропуску — серию из другой
    таблицы, стоящей рядом.
    """
    data = bytearray(0x1000)

    def put(off, target):
        data[off:off + 4] = (0x08000000 + target).to_bytes(4, 'little')

    # Таблица A: 4 монотонных окна подряд.
    for i in range(4):
        put(0x100 + i * 4, 0x900 + i)
    # Таблица B: через 8 байт, цели УБЫВАЮТ — каждый её блок длины 1.
    for i in range(4):
        put(0x120 + i * 4, 0x800 - i)
    bounds = list(_sa._iter_run_bounds(bytes(data), len(data)))
    assert bounds[0] == (0x100, 4)
    # Остаток ROM забит нулями и мусором, часть слов случайно попадает в
    # диапазон указателей, поэтому точный состав не фиксируем: важно, что после
    # таблиц идут только блоки длины 1 — ни одна серия не «протянулась».
    assert all(length == 1 for _start, length in bounds[1:])

def test_audit_scans_rom_exactly_once():
    """Считаются ВЫЗОВЫ сканера, а не элементы: один проход, а не «меньше двух»."""
    calls = []
    original = _sa._iter_targets

    def counting(data, rom_len):
        calls.append(rom_len)
        return original(data, rom_len)

    data = _rom_with_slots()
    # Таблица, которая точно должна быть найдена: иначе проходов будет 0
    # и проверка «ровно один вызов» окажется вакуумной.
    width = SLOT_WIDTH
    for i in range(4):
        at = 0x30000 + i * 4
        data[at:at + 4] = (0x08000000 + SLOT_START + i * width + 4).to_bytes(
            4, 'little')
    segments = [{'name': 'fixed_table', 'start': SLOT_START,
                 'end': SLOT_START + SLOT_COUNT * width,
                 'fixed_width': width, 'record_count': SLOT_COUNT},
                {'name': 'second', 'start': SLOT_START + 0x1000,
                 'end': SLOT_START + 0x1000 + SLOT_COUNT * width,
                 'fixed_width': width, 'record_count': SLOT_COUNT}]
    _sa._iter_targets = counting
    try:
        report = _audit_at(data, segments)
    finally:
        _sa._iter_targets = original
    assert calls == [len(data)], f'скан вызван {len(calls)} раз(а)'
    assert report[0].needs_mid_alias is True


def test_symlink_output_is_refused(tmp_path):
    """Ветка симлинка в ensure_not_source обязана быть покрыта тестом.

    На Windows создание симлинка требует привилегий (WinError 1314 проверен),
    поэтому проверка идёт через подмену Path.is_symlink — иначе ветка осталась бы
    непроверенной. Цель — это сам выходной путь, до resolve: это и есть ветка,
    достижимая в жизни.
    """
    from pathlib import Path

    from api._core import SDKError, ensure_not_source

    rom = tmp_path / 'src.gba'
    rom.write_bytes(bytes(_rom(_glyph_tiles(2))))
    out = tmp_path / 'link.gba'
    out.write_bytes(b'other')
    real_is_symlink = Path.is_symlink
    Path.is_symlink = lambda self: self == out          # type: ignore[assignment]
    try:
        with pytest.raises(SDKError) as excinfo:
            ensure_not_source(str(rom), str(out))
        assert 'символической ссылкой' in excinfo.value.message
    finally:
        Path.is_symlink = real_is_symlink                # type: ignore[assignment]
    assert rom.read_bytes() == bytes(_rom(_glyph_tiles(2)))
    assert out.read_bytes() == b'other'



# ── api/CLI-слой аудита (его не было вовсе) ─────────────────────────────────


def test_api_audit_returns_contract_keys(tmp_path, monkeypatch):
    """Контракт pi.audit_fixed_slots проверяется, а не подразумевается."""
    import api
    from core import segment_audit

    rom = tmp_path / 'game.gba'
    rom.write_bytes(bytes(_rom_with_slots()))
    monkeypatch.setattr(segment_audit, 'GameBoyROM',
                        lambda path: _MemROM(bytes(_rom_with_slots())))
    report = api.audit_fixed_slots(str(rom))
    assert set(report) == {'path', 'segments', 'needs_mid_alias'}
    assert isinstance(report['segments'], list)


def test_api_audit_rejects_non_rom(tmp_path):
    # `audit` идёт через `resolve_rom`, поэтому .txt не перезаписывается.
    import api

    fake = tmp_path / 'notes.txt'
    fake.write_bytes(b'not a rom')
    with pytest.raises(api.SDKError):
        api.audit_fixed_slots(str(fake))
    assert fake.read_bytes() == b'not a rom'


def test_cli_audit_json_contract(tmp_path, capsys):
    """JSON-вывод pi.cli audit обязан держать форму ok/data."""
    import json

    from api import cli
    from core import segment_audit

    rom = tmp_path / 'game.gba'
    rom.write_bytes(bytes(_rom_with_slots()))
    monkey = segment_audit.GameBoyROM
    segment_audit.GameBoyROM = lambda path: _MemROM(bytes(_rom_with_slots()))
    try:
        code = cli.main(['audit', str(rom), '--json'])
    finally:
        segment_audit.GameBoyROM = monkey
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['ok'] is True
    assert 'segments' in payload['data']


# ── segment_audit ──────────────────────────────────────────────────────────

SLOT_START, SLOT_WIDTH, SLOT_COUNT = 0x20000, 16, 8


class _MemROM:
    def __init__(self, data: bytes):
        self.data = data
        self.system = 'gba'

    def get_game_id(self) -> str:
        return 'TEST'


class _FakePlugin:
    is_stub = False
    game_id_pattern = '.*'

    def __init__(self, segments):
        self._segments = segments

    def get_text_segments(self, rom):
        return self._segments


def _audit_at(rom: bytearray, segments):
    """Аудит с явным списком сегментов (для проверки числа проходов)."""
    original = _sa.GameBoyROM
    _sa.GameBoyROM = lambda path: _MemROM(bytes(rom))   # type: ignore[assignment]
    try:
        return audit_fixed_slots('ignored', plugin=_FakePlugin(segments))
    finally:
        _sa.GameBoyROM = original                        # type: ignore[assignment]


def _audit(rom: bytearray):
    """Аудит по буферу: ROM-файл не нужен, GameBoyROM подменяется заглушкой."""
    segments = [{'name': 'fixed_table', 'start': SLOT_START,
                 'end': SLOT_START + SLOT_WIDTH * SLOT_COUNT,
                 'fixed_width': SLOT_WIDTH, 'record_count': SLOT_COUNT}]
    original = _sa.GameBoyROM
    _sa.GameBoyROM = lambda path: _MemROM(bytes(rom))   # type: ignore[assignment]
    try:
        return audit_fixed_slots('ignored', plugin=_FakePlugin(segments))
    finally:
        _sa.GameBoyROM = original                        # type: ignore[assignment]


def _pointer_table(rom: bytearray, offset: int, targets) -> None:
    for i, target in enumerate(targets):
        rom[offset + i * 4:offset + i * 4 + 4] = \
            (0x08000000 + target).to_bytes(4, 'little')


def _rom_with_slots() -> bytearray:
    rom = bytearray(0x40000)
    for i in range(SLOT_COUNT):
        tile = bytes(encode_tile(_glyph(i), 4))
        at = SLOT_START + i * SLOT_WIDTH
        rom[at:at + SLOT_WIDTH] = tile
    return rom


def test_audit_flags_mid_slot_pointer():
    """Настоящая монотонная таблица, чья цель — в хвост слота, найдена."""
    rom = _rom_with_slots()
    targets = [SLOT_START, SLOT_START + SLOT_WIDTH,
               SLOT_START + 2 * SLOT_WIDTH, SLOT_START + 2 * SLOT_WIDTH + 8,
               SLOT_START + 3 * SLOT_WIDTH, SLOT_START + 4 * SLOT_WIDTH]
    _pointer_table(rom, 0x30000, targets)
    report = _audit(rom)
    assert report[0].needs_mid_alias is True
    assert report[0].mid_pointers[0]['target'] == \
        SLOT_START + 2 * SLOT_WIDTH + 8


def test_audit_clean_when_pointers_land_on_slots():
    rom = _rom_with_slots()
    _pointer_table(rom, 0x30000,
                   [SLOT_START + i * SLOT_WIDTH for i in range(SLOT_COUNT)])
    assert _audit(rom)[0].needs_mid_alias is False


def test_audit_ignores_non_monotonic_run():
    """Переплетённые данные — главный источник ложных срабатываний."""
    rom = _rom_with_slots()
    _pointer_table(rom, 0x30000, [
        SLOT_START, 0x10000, SLOT_START + 3 * SLOT_WIDTH, 0x11000,
        SLOT_START + 5 * SLOT_WIDTH, 0x12000])
    assert _audit(rom)[0].needs_mid_alias is False


def test_audit_reports_slot_count():
    audit = _audit(_rom_with_slots())[0]
    assert audit.slots == SLOT_COUNT
    assert audit.as_dict()['fixed_width'] == SLOT_WIDTH
    assert audit.as_dict()['needs_mid_alias'] is False


def test_monotonic_run_is_one_for_single_window():
    data = (0x08000000 + 0x20000).to_bytes(4, 'little')
    assert _monotonic_run(data, 0, 0x40000) == 1


def test_segment_audit_needs_mid_alias_property():
    audit = SegmentAudit(name='s', system='gba', start=0, end=16, width=16)
    assert audit.needs_mid_alias is False
    audit.mid_pointers.append({'pointer_at': 4, 'target': 8, 'slot': 8})
    assert audit.needs_mid_alias is True


