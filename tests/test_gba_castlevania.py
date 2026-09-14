"""Тесты табличной экстракции Castlevania: Aria of Sorrow (CVAS)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.rom import GameBoyROM
from plugins.gba_castlevania import (
    CVAS_LANG_BLOCKS,
    CVAS_POINTER_COUNT,
    CVAS_POINTER_TABLE,
    CastlevaniaGBAPlugin,
)

ROM_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'test_roms',
    'Castlevania - Aria of Sorrow (USA).gba',
)


@pytest.fixture(scope="module")
def cvas_rom() -> GameBoyROM:
    if not os.path.exists(ROM_PATH):
        pytest.skip("Отсутствует test_roms/Castlevania - Aria of Sorrow (USA).gba")
    return GameBoyROM(ROM_PATH)


@pytest.fixture(scope="module")
def plugin() -> CastlevaniaGBAPlugin:
    return CastlevaniaGBAPlugin()


class TestCVASPointerTable:
    def test_table_size_and_block_split(self, cvas_rom):
        rom = cvas_rom
        assert CVAS_POINTER_TABLE + 4 * CVAS_POINTER_COUNT <= len(rom.data)
        assert sum(end - start_ for start_, end, _ in CVAS_LANG_BLOCKS) == CVAS_POINTER_COUNT

    def test_table_targets_valid_and_monotonic(self, cvas_rom):
        rom = cvas_rom
        targets = [
            int.from_bytes(
                rom.data[CVAS_POINTER_TABLE + 4 * i: CVAS_POINTER_TABLE + 4 * i + 4], 'little'
            ) - 0x08000000
            for i in range(CVAS_POINTER_COUNT)
        ]
        assert targets == sorted(targets)
        assert all(0 <= t < len(rom.data) for t in targets)
        # Каждая цель — начало записи: предшествующий байт — паддинг 0x00.
        assert all(t > 0 for t in targets)
        assert all(rom.data[t - 1] == 0x00 for t in targets)
        # Каждая запись — маркер страницы 0x01.
        assert all(rom.data[t] == 0x01 for t in targets)

    def test_plugin_returns_full_segment_set(self, plugin, cvas_rom):
        segments = plugin.get_text_segments(cvas_rom)
        langs: dict[str, int] = {}
        for seg in segments:
            lang = seg['name'].removeprefix('cvas_').rsplit('_', 1)[0]
            langs[lang] = langs.get(lang, 0) + 1
        assert langs == {'en_ui': 40, 'en': 973, 'fr': 1103, 'de': 779}

    def test_segment_names_unique(self, plugin, cvas_rom):
        segments = plugin.get_text_segments(cvas_rom)
        names = [seg['name'] for seg in segments]
        assert len(names) == len(set(names))

    def test_segments_are_extract_only(self, plugin, cvas_rom):
        segments = plugin.get_text_segments(cvas_rom)
        assert segments
        for seg in segments:
            assert seg['injectable'] is False
            assert seg['compression'] is None
            assert isinstance(seg['raw_text'], str) and seg['raw_text']

    def test_injector_refuses_cvas_segment(self, plugin, cvas_rom):
        """extract-only: инжектор отказывается без обращения к decoder.encode"""
        from core.injector import TextInjector

        segment = plugin.get_text_segments(cvas_rom)[0]
        injector = TextInjector(ROM_PATH)
        try:
            assert injector.inject_segment(segment['name'], ['XY'], plugin) is False
            assert injector.modified_data == injector.original_data
        finally:
            del injector

    def test_segments_boundaries(self, plugin, cvas_rom):
        """end целов байтовый, не пересекается, нет декодированного [00] и пустой строки"""
        segments = plugin.get_text_segments(cvas_rom)
        by_zone: dict[str, list[dict]] = {}
        for seg in segments:
            lang = seg['name'].removeprefix('cvas_').rsplit('_', 1)[0]
            by_zone.setdefault(lang, []).append(seg)
        for lang, segs in by_zone.items():
            segs = sorted(segs, key=lambda s: s['start'])
            for i, seg in enumerate(segs):
                assert seg['end'] > seg['start'], f'{lang} seg {i}: end <= start'
                if i + 1 < len(segs):
                    assert seg['end'] <= segs[i + 1]['start'], f'{lang} seg {i}: пересечение'
                assert '[00]' not in seg['raw_text'], f'{lang} seg {i}: 0x00 в тексте'
                assert seg['raw_text'].strip(), f'{lang} seg {i}: пустая запись'

    def test_first_record_shape(self, plugin, cvas_rom):
        segments = plugin.get_text_segments(cvas_rom)
        en = [s for s in segments if not s['name'].startswith('cvas_en_ui_')
              and s['name'].startswith('cvas_en_')]
        first = en[0]
        # Запись начинается с маркера страницы [PAGE] (0x01) — обязательный префикс.
        assert first['raw_text'].startswith('[PAGE]')
        assert first['start'] == 0x0F01C4  # первая цель en-блока
        assert first['end'] > first['start'] + 2

    def test_every_record_has_page_marker(self, plugin, cvas_rom):
        """Каждая запись начинается с [PAGE]"""
        segments = plugin.get_text_segments(cvas_rom)
        non_page = [s for s in segments if not s['raw_text'].startswith('[PAGE]')]
        assert not non_page

    def test_extract_ids_stable(self, plugin, cvas_rom):
        """Детерминированность: два прогона дают те же сегменты"""
        a = plugin.get_text_segments(cvas_rom)
        b = plugin.get_text_segments(cvas_rom)
        assert [(s['name'], s['start'], s['end']) for s in a] == \
               [(s['name'], s['start'], s['end']) for s in b]

    def test_story_dialogue_in_table(self, plugin, cvas_rom):
        """Story-диалог «Welcome back, Soma.» @0x0F1010 извлекается из таблицы
        0x506B38 (en-блок) — отдельного механизма для story нет. Ранний вывод
        «вне таблицы» был следствием проверки неверного оффсета 0x0F1011."""
        segments = plugin.get_text_segments(cvas_rom)
        target = 0x0F1010
        segs = [s for s in segments if s['start'] == target]
        assert segs, 'запись 0x0F1010 отсутствует в сегментах'
        assert segs[0]['name'].startswith('cvas_en_')
        assert 'Welcome back' in segs[0]['raw_text']
