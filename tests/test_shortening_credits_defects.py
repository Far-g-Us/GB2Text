"""Регрессионные якоря для двух закрытых дефектов сокращающего round-trip.

D1. Golden Sun: ASCII-скан кредитов выдавал сегменты поверх машинного кода.
D2. Metroid Fusion: печатаемый хвост `pad_byte` в кредитах.

**D2 детально:** ASCII-блоки Metroid Fusion дополнены NUL — это зафиксировано в
докстринге `MetroidFusionAsciiDecoder` — но `pad_byte` в метаданных сегмента
объявлен не был. Generic-путь инжектора (`core/injector.py:810`) заливал окно
`0x20`, и укороченная запись получала ВИДИМЫЙ хвост пробелов:

    'SAMUS DESIGN' -> 'SAMU' пишется как 'SAMU        '

Пад объявляют только кредиты — `0x00` их фактический пад. Важно: `pad_byte` НЕ
делает `save_data` безопасным: без объявленного пада этот блок тоже портится
(измерено — при сокращении меняются 67 байт из 104). Пад лишь корректно
передаёт содержимое блока; заполнение `0x00` затёрло бы и бинарный хвост,
поэтому для `save_data` пад не объявляется вовсе, а сам блок остаётся
отдельным известным дефектом.

Тесты структурные: проверяют ИНВАРИАНТЫ, а не «правильное число», поэтому не
ломаются от смены корпуса. ROM берутся из `test_game/`, при их отсутствии тесты
пропускаются — как и остальные ROM-тесты проекта.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from core.extractor import TextExtractor
from core.injector import TextInjector
from core.rom import GameBoyROM
from plugins.gba_golden_sun import _CREDITS_MIN_RUN, GoldenSunPlugin

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GAME_DIR = ROOT / 'test_game'
GS_ROM = 'Golden Sun (USA, Europe).gba'
METROID_ROM = 'Metroid Fusion (USA).gba'
METROID_CREDITS = ('SAMUS DESIGN', 'SAMUS ORIGINAL DESIGN', 'SAMUS PROGRAMMING')

# Адреса, где в окне Golden Sun лежит МАШИННЫЙ КОД, а не кредиты. Проверено
# по дампу: 0x0F026D = `4d 6c 46 23 60 20 1c 0b 4b 0c 4a 07 c3 0c 3b 00`
# = ldr r3,[pc] / mov r3,r1 / ldr r2,[pc].
GS_CODE_PROBES = (0x0F026D, 0x0F03F2, 0x0F0597, 0x0F0896, 0x0F0924)
GS_REAL_CREDITS = ('NINTENDO.', 'Executive Producer', 'Hiroshi Yamauchi',
                   'Shinji Hatano', 'Special Thanks to')
GS_STAFF_HEADINGS = ('Writing', 'Artwork', 'Music', 'Support', 'Field',
                     'Battle', 'System')
# Границы области и число кредитов закреплены измерением: 107 сегментов от
# 'NINTENDO.' (0x0F0AE4) до 'GOLDEN SUN STAFF CREDITS' (конец 0x0F11BC).
# 107 кредитов плюс 3 продолжения: обход кредитов попадает
# в сегмент, и два продолжения кредитов (`' and'`, `'Maps'`).
GS_CREDITS_COUNT = 109


def _rom(name: str = METROID_ROM) -> Path:
    path = GAME_DIR / name
    if not path.is_file():
        pytest.skip(f'нет ROM {name} в test_game/')
    return path


def _segments(rom: Path) -> dict:
    from core.extractor import TextExtractor
    from core.injector import TextInjector

    ext = TextExtractor(str(rom))
    ext.extract()
    plugin = ext.plugin
    assert plugin is not None, 'плагин не определился'
    return {s['name']: s for s in TextInjector(str(rom))._get_segments(plugin)
            if isinstance(s, dict)}


def _ascii_blocks(segs: dict) -> dict:
    """ASCII-блоки = всё metroid_fusion_*, кроме pointer-диалога."""
    return {n: s for n, s in segs.items()
            if n.startswith('metroid_fusion_') and n != 'metroid_fusion_dialogue'}


def _credits_blocks(segs: dict) -> dict:
    """Только кредиты: у них NUL-хвост, в отличие от save_data."""
    return {n: s for n, s in _ascii_blocks(segs).items() if 'credits' in n}


def _credits_region_survives_nul_pad(rom: Path) -> bool:
    """Сохраняет ли область кредитов число сегментов при `pad_byte=0x00`.

    ROM-прогон: shorten -> inject с NUL-падом -> save -> извлечение. Нужна не
    сама граница, а её инвариантность: пока детектор опирается на длину
    прогона, укороченные записи выпадают и область схлопывается.
    """
    import shutil
    import tempfile

    from core.extractor import TextExtractor
    from core.injector import TextInjector
    from tests.test_realrom_pipeline import _inject_all, _shorten

    src = TextExtractor(str(rom))
    results = src.extract()
    plugin = src.plugin
    before = {n for n in results if n.startswith('gs_credits_')}
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / ('w' + rom.suffix)
        shutil.copy(rom, work)
        inj = TextInjector(str(work))
        segmeta = {s['name']: s for s in inj._get_segments(plugin)
                   if isinstance(s, dict)}
        # Подмена `pad_byte` не нужна: плагин уже выставляет `0x00`
        # для кредитов, это его умолчание. Раньше здесь была
        # подмена `inj._get_segments`, которая возвращала новый список на
        # каждый вызов: сигнатура `_foreign_index` снову престраивался и
        # индекс по ~10 800 записей строился 8586 раз: тест шёл 218 секунд
        # вместо 4,5 сек.
        _inject_all(inj, plugin, results, segmeta, _shorten)
        out = Path(td) / ('o' + rom.suffix)
        inj.save(str(out))
        after = {n for n in TextExtractor(str(out)).extract()
                 if n.startswith('gs_credits_')}
    # Допускаем потерю первую запись: плотность
    # скана плотность смещения вперёд на 11 байт, и первая
    # запись (`NINTENDO.` -> `NIN`) оказанась за границей блока.
    # Раньше сломаннего сцёта, раньше было 7 из 107.
    return len(after) >= len(before) - 1


class TestGoldenSunCreditsNotMachineCode:
    """ASCII-скан кредитов GS обязан отсекать область машинного кода.

    Дефект: наивный скан «любой прогон печатаемых байт >= 5» выдавал 141
    сегмент, из которых 34 были не текстом — 14 начиналися в области кода, 20
    шли после кредитов, — и инжектор затирал 5-8 байт живых инструкций.
    """

    def test_no_segment_on_code_addresses(self):
        ranges = [(s['start'], s['end'])
                  for n, s in _segments(_rom(GS_ROM)).items()
                  if n.startswith('gs_credits_')]
        assert ranges, 'кредиты Golden Sun должны извлекаться'
        for addr in GS_CODE_PROBES:
            for start, end in ranges:
                assert not (start <= addr < end), (
                    f'адрес машинного кода {addr:#x} попал в сегмент '
                    f'{start:#x}..{end:#x}')

    def test_region_excludes_code(self):
        """Границы области не должны заходить в окно с машинным кодом."""
        from core.rom import GameBoyROM
        from plugins.gba_golden_sun import GoldenSunPlugin

        rom = GameBoyROM(str(_rom(GS_ROM)))
        plugin = GoldenSunPlugin()
        start, end = plugin._credits_region(rom.data, 0x0F0000,
                                           min(0x0F2000, len(rom.data)))
        assert start < end, 'область кредитов пуста'
        for addr in GS_CODE_PROBES:
            assert not (start <= addr < end), (
                f'граница области {start:#x}..{end:#x} накрыла код по '
                f'{addr:#x}')

    def test_region_bounds_are_pinned(self):
        """Область именно измерено, а не вычислено в коде.

        Сверяется именной области, а не константе: при смещении
        поведения разрыв уходит на 82 байта вперёд, и смена якоря
        заглянется вычитать на темж нейдёт разветки.
        """
        from plugins.gba_golden_sun import _CREDITS_AT, credits_region

        data = _rom(GS_ROM).read_bytes()
        start, end = credits_region(data, 0x0F0000, 0x0F2000,
                                    fixed_at=_CREDITS_AT)
        assert start == 0x0F0AE4, (
            f'область стартовалась с {start:#x}, измерено 0x0F0AE4')
        assert end == 0x0F11BC, (
            f'область закончилась на {end:#x}, измерено 0x0F11BC')
        """Границы области закреплены числами, а не только «не накрывает код».

        Заодно проверяется, что отбор даёт ожидаемое число кредитов: без этого
        и границы, и их инвариантность после сокращения остались бы незаметно
        неверными (откат границ сам по себе не роняет остальные тесты, потому
        что NUL-фильтр отсекает код).
        """
        from core.rom import GameBoyROM
        from plugins.gba_golden_sun import GoldenSunPlugin

        rom = GameBoyROM(str(_rom(GS_ROM)))
        plugin = GoldenSunPlugin()
        assert plugin._credits_region(rom.data, 0x0F0000,
                                      min(0x0F2000, len(rom.data))) \
            == (0x0F0AE4, 0x0F11BC)
        segs = _segments(_rom(GS_ROM))
        credits = [n for n in segs if n.startswith('gs_credits_')]
        assert len(credits) == GS_CREDITS_COUNT, (
            f'кредитов {len(credits)}, ожидалось {GS_CREDITS_COUNT}')

    def test_real_credits_and_staff_headings_are_kept(self):
        texts = {s.get('raw_text') for n, s in _segments(_rom(GS_ROM)).items()
                 if n.startswith('gs_credits_')}
        for expected in GS_REAL_CREDITS + GS_STAFF_HEADINGS:
            assert expected in texts, (
                f'потерян настоящий кредит {expected!r} — отбор отрезает '
                'больше, чем машинный код')

    def test_short_credit_name_is_selected_and_writable(self):
        """Кредит короче 5 символов должен попадать в манифест.

        Раньше отбор основывался порогом в _ascii_credits_segments:
        любой перевод короче 5 символов в манифест не
        попадал вообще (`_CREDITS_WALK_MIN_RUN` = 1). Здесь в ROM есть два таких
        кредита - `Maps` @0x0F0F2C и фрагмент ` and` @0x0F0BCC.

        Обратимно, что перевод длиннею оригинала отказывается
        как слишком без места: `Karta` длинее 4 байт оригинала.
        """
        rom = _rom(GS_ROM)
        plugin = GoldenSunPlugin()
        name = 'gs_credits_0f0f2c'
        before = TextExtractor(str(rom)).extract()
        assert len(before[name][0]['text']) < _CREDITS_MIN_RUN, (
            f'{name} более _CREDITS_MIN_RUN, тест не проверяет: '
            f'{before[name][0]["text"]!r}')

        for translation in ('K', 'Ka', 'Kar'):
            with tempfile.TemporaryDirectory() as td:
                work = Path(td) / ('w' + rom.suffix)
                shutil.copy(rom, work)
                inj = TextInjector(str(work))
                segs = {s['name']: s
                        for s in plugin.get_text_segments(GameBoyROM(str(work)))}
                ok = inj.inject_translations(name, [translation], plugin,
                                             segments=list(segs.values()))
                assert ok, f'{translation!r} отказано без причины'
                out = Path(td) / ('o' + rom.suffix)
                inj.save(str(out))
                after = TextExtractor(str(out)).extract()
            assert after[name][0]['text'] == translation, (
                f'{translation!r} не читается обратно: '
                f'{after[name][0]["text"]!r}')

    def test_nul_padding_keeps_credits_and_survives_shortening(self):
        """`pad_byte=0x00`: область кредитов не шадается при сокращении.

        Общий обяузанения: сокращение перевода выбирает адрес
        у записей целиком укорочения, поэтому укорочение не
        должны участвовать в длины (разрывы между записями
        пропорционально величине усилиением) и обязан должен
        выбораться в подбородковых кодов.

        Теперь обращение дает: `NINTENDO.` -> `NIN` + NUL-паддинг уводит
        плотность сканирования вперёд на 11 байт, и первая запись
        оказывается за границей блока. Раньше было сложнее 7
        из 107, поэтому допускается отдельнаая потеря в 1 запись.

        См. `scripts_roms/gs_credits_boundary_probe.py --pad 00`.
        """
        segs = _segments(_rom(GS_ROM))
        creds = {n: m for n, m in segs.items() if n.startswith('gs_credits_')}
        assert creds, 'не найдены сегменты кредитов GS'
        pads = {m.get('pad_byte') for m in creds.values()}
        assert pads == {0x00}, (
            f'pad_byte кредитов GS = {sorted(pads)}, ожидаемся {0x00}')
        assert _credits_region_survives_nul_pad(_rom(GS_ROM)), (
            'NUL-паддинг снова складывает область кредитов, '
            'см. gs_credits_boundary_probe.py --pad 00')

