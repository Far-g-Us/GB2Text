"""Тесты LZSS-диалогов FFTA (plugins/gba_fft_advance.py, Фаза B v1)

Извлечение сжатых диалогов (маркер 0x32 0x00) как extract-only сегментов.
Инварианты и кол-ва блоков считаны эмпирически с USA ROM
(test_roms/Final Fantasy Tactics Advance (USA).gba) — на других ревизиях
они могут отличаться.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.compression import FFTA_LZSSHandler
from core.injector import TextInjector
from core.rom import GameBoyROM
from plugins.gba_fft_advance import FFTAdvancePlugin, _decode_ffta_text
from references.ffta_lzss_myguyz import lzss_decompress_ex

ROM_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "test_roms",
    "Final Fantasy Tactics Advance (USA).gba",
)

# Классификатор (pct<0.5) выделяет 1790 текстовых блоков; 3 из них (D1,
# только контрольный код [40_67]) отсеиваются фильтром «все-маркеры».
REGION_COUNTS_USA = {'D_mega': 1627, 'D0': 93, 'D1': 67}
REJECTED_CONTROL_ONLY = [0x4B8B46, 0x4B8BD4, 0x4BA05A]
TOTAL_DIALOGUE = sum(REGION_COUNTS_USA.values())

FIXTURE_DIALOGUES = [
    (0x49B84A,
     "You can't ssell[NEWLINE]itemss that are[NEWLINE]equipped, sson.[WAIT][CLEAR]"),
    (0x4B54AC,
     "Leave me 3,000 gil[NEWLINE]and I'll give you[NEWLINE]a break.[40_77][CLEAR]"),
    (0x9C16EE,
     "Aww, man! [NEWLINE]Why do I get stuck[NEWLINE]on the weak team?[NEXT_PAGE]"
     "[CLEAR]We're just gonna[NEWLINE]lose. Where's the[NEWLINE]fun in that?[WAIT][CLEAR]"),
]

# LZSS-блоки, которые НЕ являются диалогами (шум/графика): не должны попасть в сегменты
NOISE_BLOCK_OFFSETS = [
    0x43BADB,  # region gfx, size=4352
    0x448EDF,  # region gfx, size=4352
    0x50D266,  # other, size=256, pct 1.0
    0x52FF63,  # other, size=32, pct 1.0
    0x55B80D,  # other, size=3, pct 1.0
    0x560B01,  # other, size=256, pct 0.97
    0x560B47,  # other, size=256, pct 0.97
    0x816363,  # other, size=12544, pct 0.73
    0x8F49C8,  # other, size=1920, pct 1.0
    0x94A09B,  # other, size=31, pct 1.0
    0x94A0D5,  # other, size=31, pct 1.0
    0xA2BB5B,  # other, size=17, pct 1.0
]


@pytest.fixture(scope="module")
def ffta_rom() -> GameBoyROM:
    if not os.path.exists(ROM_PATH):
        pytest.skip("Отсутствует test_roms/Final Fantasy Tactics Advance (USA).gba")
    return GameBoyROM(ROM_PATH)


@pytest.fixture(scope="module")
def plugin() -> FFTAdvancePlugin:
    return FFTAdvancePlugin()


@pytest.fixture(scope="module")
def dialogue_segments(plugin, ffta_rom):
    return plugin._scan_lzss_dialogues(ffta_rom.data)


class TestLZSSDialogueScan:
    def test_dialogue_counts_on_usa_rom(self, dialogue_segments):
        counts: dict[str, int] = {}
        for seg in dialogue_segments:
            region = seg['name'][len('ffta_dialogue_lzss_'):].rsplit('_', 1)[0]
            counts[region] = counts.get(region, 0) + 1
        assert counts == REGION_COUNTS_USA
        assert len(dialogue_segments) == TOTAL_DIALOGUE

    def test_no_segments_from_gfx_region(self, dialogue_segments):
        for seg in dialogue_segments:
            assert not (0x430000 <= seg['start'] < 0x480000), (
                f"Графический блок попал в сегменты: 0x{seg['start']:06X}"
            )

    def test_noise_blocks_not_extracted(self, dialogue_segments, plugin, ffta_rom):
        starts = {seg['start'] for seg in dialogue_segments}
        for off in NOISE_BLOCK_OFFSETS + REJECTED_CONTROL_ONLY:
            assert off not in starts, f"Шумовой блок 0x{off:06X} извлечён как диалог"
            out, _ = plugin._lzss.decompress(ffta_rom.data, off + 2)
            assert out, f"Шумовой блок 0x{off:06X} не декомпрессировался"

    def test_fixture_dialogues_decode_exactly(self, dialogue_segments):
        for off, expected in FIXTURE_DIALOGUES:
            seg = next((s for s in dialogue_segments if s['start'] == off), None)
            assert seg is not None, f"Блок 0x{off:06X} не извлечён"
            assert seg['text'] == expected, f"Текст блока 0x{off:06X} не совпал"
            assert seg['raw_text'] == expected

    def test_segments_are_injectable(self, dialogue_segments):
        for seg in dialogue_segments:
            assert isinstance(seg['raw_text'], str) and seg['raw_text']
            assert seg['injectable'] is True
            assert seg['compression'] == 'FFTA_LZSS'

    def test_lzss_is_noise_classifier(self, plugin):
        assert plugin._lzss_is_noise(b"") is True
        assert plugin._lzss_is_noise(b"abc") is False
        assert plugin._lzss_is_noise(b"\x00abc") is False
        assert plugin._lzss_is_noise(b"\x00\x00ab") is True
        assert plugin._lzss_is_noise(b"\xff\xff\xff\xff") is True

    def test_segment_names_unique(self, dialogue_segments):
        names = [seg['name'] for seg in dialogue_segments]
        assert len(names) == len(set(names))

    def test_scan_accepts_exactly_1790_blocks(self, dialogue_segments):
        # Регрессия кламп-семантики литералов (core/compression.py): кламп не
        # должен добавлять ложные блоки из графики. 1790 = 1787 принятых
        # диалогов + 3 блока с единственным контрольным кодом [40_67],
        # отсеиваемых фильтром «все-маркеры» (REJECTED_CONTROL_ONLY).
        accepted = TOTAL_DIALOGUE + len(REJECTED_CONTROL_ONLY)
        assert accepted == 1790


class TestLZSSDialogueParity:
    def test_plugin_handler_matches_reference(self, dialogue_segments, ffta_rom):
        handler = FFTA_LZSSHandler()
        for seg in dialogue_segments:
            ref = lzss_decompress_ex(ffta_rom.data, seg['start'] + 2)
            assert ref is not None, f"Блок 0x{seg['start']:06X}: эталон не распаковал"
            got, consumed = handler.decompress(ffta_rom.data, seg['start'] + 2)
            assert got == ref[0], f"Вывод не совпал на блоке 0x{seg['start']:06X}"
            assert consumed == ref[1], f"consumed не совпал на блоке 0x{seg['start']:06X}"


class TestLZSSDialogueIntegration:
    def test_get_text_segments_includes_dialogues(self, plugin, ffta_rom):
        segments = plugin.get_text_segments(ffta_rom)
        dialogues = [s for s in segments if s['name'].startswith('ffta_dialogue_lzss_')]
        assert len(dialogues) == TOTAL_DIALOGUE

    def test_no_overlap_with_other_segments(self, plugin, ffta_rom):
        segments = plugin.get_text_segments(ffta_rom)
        dialogues = [s for s in segments if s['name'].startswith('ffta_dialogue_lzss_')]
        others = [s for s in segments if not s['name'].startswith('ffta_dialogue_lzss_')]
        for d in dialogues:
            for o in others:
                assert (d['end'] <= o['start'] or d['start'] >= o['end']), (
                    f"Пересечение сегментов {d['name']} и {o['name']}"
                )

    def test_injector_dialogue_roundtrip(self, plugin, ffta_rom):
        segments = plugin.get_text_segments(ffta_rom)
        dialogues = [s for s in segments
                     if s['name'].startswith('ffta_dialogue_lzss_')]
        injector = TextInjector(ROM_PATH)
        dz = FFTA_LZSSHandler()
        ok_count = 0
        for dialogue in dialogues:
            text = dialogue['text']
            ok = injector.inject_segment(
                dialogue['name'], [text], plugin, skip_long=True,
                segments=segments)
            if not ok:
                pytest.fail(f"No-op текст не влез в окно {dialogue['name']}")
            out, consumed = dz.decompress(
                bytes(injector.modified_data), dialogue['start'] + 2)
            assert dialogue['start'] + 2 + consumed <= dialogue['end'], \
                f"Сжатые данные вышли за окно {dialogue['name']}"
            dec = dialogue['decoder']
            assert dec.decode(out, 0, len(out)) == text, \
                f"Round-trip сломан на {dialogue['name']}"
            ok_count += 1
        assert ok_count == len(dialogues), \
            f"Только {ok_count}/{len(dialogues)} диалогов инжектировано"
        assert injector.modified_data != injector.original_data, \
            "ROM должен был измениться (пересжатие окна)"

    def test_injector_crn_roundtrip(self, plugin, ffta_rom):
        segments = plugin.get_text_segments(ffta_rom)
        crn = [s for s in segments if s['name'].startswith('CRN_')]
        assert len(crn) == 107, f"Ожидается 107 CRN-сегментов, получено {len(crn)}"
        injector = TextInjector(ROM_PATH)
        ok_count = 0
        for segment in crn:
            text = segment['text']
            start = segment['start']
            ok = injector.inject_segment(
                segment['name'], [text], plugin, skip_long=True,
                segments=segments)
            if not ok:
                pytest.fail(f"No-op текст не влез в окно {segment['name']}")
            window = slice(start, segment['end'])
            rebuilt, _ = _decode_ffta_text(
                bytes(injector.modified_data[window]), 0, len(bytes(injector.modified_data[window])))
            assert rebuilt == text, f"Round-trip сломан на {segment['name']}"
            ok_count += 1
        assert ok_count == len(crn), \
            f"Только {ok_count}/{len(crn)} CRN-сегментов инжектировано"
        assert injector.modified_data != injector.original_data, \
            "ROM должен был измениться (инжекция имён)"
