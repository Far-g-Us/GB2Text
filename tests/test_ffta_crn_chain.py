"""FFTA: регрессионные якоря для цепочечного CRN-скана.

Дефект: записи CRN идут вплотную, разделённые ровно одним `0x00`, и скан
пропускал разделитель через `offset += 1`. Инжектор дописывает `pad_byte=0x00`
до прежней длины, поэтому после сокращения записи остаётся НЕСКОЛЬКО нулей
подряд, и каждый ноль серии тратил отдельную итерацию жёсткого цикла в 107
шагов. Скан исчерпывал итерации, не доходя до конца области.

Измерено до правки: из 107 имён находились только первые 21. После правки:
107 из 107, потерь 0. Проверено откатом правки: синтетический тест находит
12 из 20 заложенных записей, и содержимое найденных по адресам записей
корректно — терялись не они, просто не доходили до конца.

Оба теста ROM-gated: при отсутствии ROM пропускаются, как и остальные
ROM-тесты проекта.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GAME_DIR = ROOT / 'test_game'
FFTA_ROM = 'Final Fantasy Tactics Advance (USA).gba'


def _rom() -> Path:
    path = GAME_DIR / FFTA_ROM
    if not path.is_file():
        pytest.skip(f'нет ROM {FFTA_ROM} в test_game/')
    return path


def _crn_segment_names(rom: Path) -> list[str]:
    from core.extractor import TextExtractor

    ext = TextExtractor(str(rom))
    results = ext.extract()
    return [name for name in results if name.startswith('CRN_')]


def _shorten_all_and_reextract(rom: Path) -> tuple[int, int, int]:
    """Возвращает (CRN до, CRN после, потери)."""
    from core.extractor import TextExtractor
    from core.injector import TextInjector
    from tests.test_realrom_pipeline import _inject_all, _shorten

    ext = TextExtractor(str(rom))
    results = ext.extract()
    plugin = ext.plugin
    before = len([n for n in results if n.startswith('CRN_')])

    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / ('w' + rom.suffix)
        shutil.copy(rom, work)
        inj = TextInjector(str(work))
        segmeta = {s['name']: s for s in inj._get_segments(plugin)
                   if isinstance(s, dict)}
        _inject_all(inj, plugin, results, segmeta, _shorten)
        out = Path(td) / ('o' + rom.suffix)
        inj.save(str(out))
        after_results = TextExtractor(str(out)).extract()

    after = len([n for n in after_results if n.startswith('CRN_')])
    return before, after, before - after


class TestFftaCrnChainedScan:
    """Цепочечный скан CRN обязан переживать сокращение записи."""

    def test_all_crn_names_extracted_on_clean_rom(self):
        names = _crn_segment_names(_rom())
        assert len(names) >= 100, (
            f'в чистом ROM ожидалось >=100 имён CRN, получено {len(names)}')

    def test_no_crn_names_lost_after_shortening(self):
        before, after, lost = _shorten_all_and_reextract(_rom())
        assert before >= 100
        assert lost == 0, (
            f'после сокращения не найдено {lost} имён CRN из {before} '
            f'(осталось {after}); прежний `offset += 1` тратил по итерации '
            'на каждый ноль паддинга, и скан исчерпывал лимит, не дойдя до '
            'конца области')

    def test_names_survive_as_set(self):
        """Не только количество, но и сами имена: потеря недопустима."""
        from core.extractor import TextExtractor
        from core.injector import TextInjector
        from tests.test_realrom_pipeline import _inject_all, _shorten

        rom = _rom()
        ext = TextExtractor(str(rom))
        results = ext.extract()
        plugin = ext.plugin
        names_before = {n for n in results if n.startswith('CRN_')}

        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / ('w' + rom.suffix)
            shutil.copy(rom, work)
            inj = TextInjector(str(work))
            segmeta = {s['name']: s for s in inj._get_segments(plugin)
                       if isinstance(s, dict)}
            _inject_all(inj, plugin, results, segmeta, _shorten)
            out = Path(td) / ('o' + rom.suffix)
            inj.save(str(out))
            after = TextExtractor(str(out)).extract()

        names_after = {n for n in after if n.startswith('CRN_')}
        missing = sorted(names_before - names_after)
        assert not missing, f'пропали имена: {missing[:10]}'

    def test_scan_skips_whole_zero_run(self):
        """ROM-free якорь: скан не исчерпывает итерации на сериях нулей.

        Скан читает ровно `CRN_COUNT` итераций, поэтому дефект здесь не
        «потеря записи поимённо», а ИСЧЕРПАНИЕ: каждый ноль серии съедал
        отдельную итерацию, и до конца области скан не доходил. Чтобы поймать
        это без ROM, закладываем больше записей, чем итераций: 20 записей,
        разделённых девятью нулями, дают 20 + 20*9 ≈ 200 шагов при 107
        доступных. Прежний `offset += 1` доходит примерно до 12-й записи,
        текущий код — до всех 20.
        """
        from plugins.gba_fft_advance import (
            CRN_COUNT,
            FFTA_CRN_OFFSET,
            FFTAdvancePlugin,
        )

        gap = 9
        records = 20
        base = FFTA_CRN_OFFSET
        needed = records * (3 + gap) + 16
        data = bytearray(b'\x00' * (base + needed))

        offset = 0
        for k in range(records):
            # Тело записи: 0x01-префикс + два байта, различимых по k.
            data[base + offset] = 0x01
            data[base + offset + 1] = 0x30 + (k % 10)
            data[base + offset + 2] = 0x41 + (k % 26)
            offset += 3 + gap

        plugin = FFTAdvancePlugin()
        segs = plugin._read_crn_data(bytes(data))
        found = [s['start'] - base for s in segs]

        assert records <= CRN_COUNT, (
            f'синтетика требует {records} записей, а скан читает {CRN_COUNT}; '
            'уменьши число записей или измени тест')
        assert len(found) == records, (
            f'скан нашёл {len(found)} из {records} записей; прежний '
            '`offset += 1` тратил по итерации на каждый ноль серии и исчерпывал '
            f'лимит {CRN_COUNT} задолго до конца области')
        assert found == sorted(found), f'порядок записей нарушен: {found}'
