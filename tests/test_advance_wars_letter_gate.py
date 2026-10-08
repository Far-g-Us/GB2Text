"""Регрессионные якоря для снятого порога «>= 2 буквы» в Advance Wars.

Дефект: `_decode_at` отбрасывал запись, если в ней меньше двух букв. Критерий
не инвариантен к переводу: сокращение `'Map11'` -> `'M'` даёт одну букву, и
запись выпадала из манифеста — измерено 31 запись из 186 терялась при
обратном извлечении.

Правило, которое здесь проверяется: любой критерий «это текст / это мусор»
обязан быть инвариантом к переводу. Длина текста и число букв — не инвариант;
байтовая допустимость (печатные байты, 0x0A/0x0D, 0x00-терминатор) — инвариант.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GAME_DIR = ROOT / 'test_game'
AW_ROM = 'Advance Wars (USA).gba'


def _rom() -> Path:
    path = GAME_DIR / AW_ROM
    if not path.is_file():
        pytest.skip(f'нет ROM {AW_ROM} в test_game/')
    return path


class TestAdvanceWarsLetterCountGateRemoved:
    """Порог длины удалён, байтовая проверка сохранена."""

    def test_single_letter_accepted(self):
        from plugins.gba_advance_wars import _decode_at

        assert _decode_at(b'A\x00rest', 0) == 'A'

    def test_letter_plus_digit_accepted(self):
        from plugins.gba_advance_wars import _decode_at

        assert _decode_at(b'A1\x00', 0) == 'A1'

    def test_non_text_bytes_still_rejected(self):
        from plugins.gba_advance_wars import _decode_at

        assert _decode_at(b'A\x01B\x00', 0) is None
        assert _decode_at(b'\x80\x81\x00', 0) is None

    def test_multibyte_and_newlines_still_allowed(self):
        from plugins.gba_advance_wars import _decode_at

        assert _decode_at(b'AB\x00', 0) == 'AB'
        assert _decode_at(b'A\nB\rC\x00', 0) == 'A\nB\rC'

    def test_no_record_lost_after_shortening(self):
        """Ядро дефекта: ни одна запись не должна выпасть из манифеста."""
        from core.extractor import TextExtractor
        from core.injector import TextInjector
        from tests.test_realrom_pipeline import _inject_all, _shorten

        rom = _rom()
        ext = TextExtractor(str(rom))
        results = ext.extract()
        plugin = ext.plugin
        before = {name: len(msgs) for name, msgs in results.items()}

        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / ('w' + rom.suffix)
            shutil.copy(rom, work)
            inj = TextInjector(str(work))
            segmeta = {s['name']: s for s in inj._get_segments(plugin)
                       if isinstance(s, dict)}
            _inject_all(inj, plugin, results, segmeta, _shorten)
            out = Path(td) / ('o' + rom.suffix)
            inj.save(str(out))
            after = {name: len(msgs) for name, msgs
                     in TextExtractor(str(out)).extract().items()}

        lost = {name: (before[name], after.get(name, 0))
                for name in before
                if after.get(name, 0) != before[name]}
        assert not lost, (
            f'после сокращения число записей изменилось: {lost}; прежний порог '
            '«>= 2 буквы» отбрасывал записи вроде \'M\'')
