"""
Тесты для плагина Golden Sun: The Lost Age (GBA) - контекстный Хаффман.

Проверяются детерминированность декодера, токен-маппинг (в т.ч. двухбайтовые
контрольные коды), структура сегментов и, при наличии легального ROM,
интеграция с реальными данными (адреса/счётчики — только факты, не тексты).
"""

import os
import re
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rom import GameBoyROM
from plugins.gba_golden_sun_tla import (
    GoldenSunTLAPlugin,
    GoldenSunTLATextDecoder,
)

# SHA1 golden sun tla rom not exposed; game code AGFE
TLA_ROM = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'test_roms', 'Golden Sun - The Lost Age (USA, Europe).gba',
)


def _has_tla_rom() -> bool:
    return os.path.exists(TLA_ROM)


def _fits_segment(plugin, segment, translation, rom) -> bool:
    try:
        compressed = segment['encoder'](translation)
    except (ValueError, KeyError, IndexError):
        return False
    return bool(len(compressed) <= segment['compressed_length'])


@pytest.fixture(scope='module')
def tla_plugin():
    return GoldenSunTLAPlugin()


@pytest.fixture(scope='module')
def tla_rom():
    if not _has_tla_rom():
        pytest.skip("Golden Sun TLA ROM не найден (легально-owned только)")
    return GameBoyROM(TLA_ROM)


@pytest.fixture(scope='module')
def tla_segments(tla_rom, tla_plugin):
    return tla_plugin.get_text_segments(tla_rom)


class TestTLAPluginContract:
    def test_plugin_matches_agfe(self, tla_plugin):
        match = re.search(tla_plugin.game_id_pattern, 'GBA_AGFE')
        assert match is not None

    def test_plugin_rejects_agse(self, tla_plugin):
        match = re.search(tla_plugin.game_id_pattern, 'GBA_AGSE')
        assert match is None

    def test_game_codes(self, tla_plugin, tla_rom):
        match = re.fullmatch(tla_plugin.game_id_pattern, tla_rom.get_game_id())
        assert match is not None
        assert match.group(1) == 'AGFE'

    def test_terminators(self, tla_plugin):
        assert tla_plugin.get_terminators('gs_dialogue_f00_000') == [0x00]


class TestTLATokenMapping:
    def test_nl_end_cont(self):
        dec = GoldenSunTLATextDecoder()
        assert dec.decode(b'\x01') == '{NL}'
        assert dec.decode(b'\x02') == '{END}'
        assert dec.decode(b'\x03') == '{CONT}'

    def test_two_byte_token(self):
        """0x08 0x05 (цвет) — двухбайтовый токен, bi-directional."""
        dec = GoldenSunTLATextDecoder()
        text = dec.decode(b'\x08\x05Hello\x02')
        assert text == '{08 05}Hello{END}'
        assert dec.encode(text) == b'\x08\x05Hello\x02'

    def test_two_byte_token_reverse(self):
        dec = GoldenSunTLATextDecoder()
        assert dec.encode('{12 01}') == b'\x12\x01'
        assert dec.encode('{1D 02}') == b'\x1d\x02'

    def test_tokens_avoid_split_patterns(self):
        """Токены не должны ломать _split_messages: без '[', '\n', '[XX]'."""
        dec = GoldenSunTLATextDecoder()
        for b in range(0x01, 0x20):
            token = dec.decode(bytes([b]))
            assert '[' not in token
            assert '\n' not in token
            assert not re.fullmatch(r'\[[0-9A-Fa-f]{2}\]', token)
            assert token != '[END]'


class TestTLASegments:
    def test_segment_count(self, tla_segments):
        dialogue = [s for s in tla_segments if s['name'].startswith('gs_dialogue_')]
        assert len(dialogue) >= 12000

    def test_segment_bounds_in_rom(self, tla_rom, tla_segments):
        for segment in tla_segments:
            assert 0 <= segment['start'] < segment['end'] <= len(tla_rom.data)

    def test_segment_raw_text_not_empty(self, tla_segments):
        for segment in tla_segments:
            assert isinstance(segment['raw_text'], str)
            assert len(segment['raw_text']) > 0

    def test_all_dialogue_named_consistently(self, tla_segments):
        names = [s['name'] for s in tla_segments
                 if s['name'].startswith('gs_dialogue_')]
        assert all(re.fullmatch(r'gs_dialogue_f\d{2}_\d{3}', n) for n in names)
        assert len(set(names)) == len(names)


class TestTLAHuffman:
    def test_decoder_deterministic(self, tla_rom):
        from plugins.gba_golden_sun import GoldenSunHuffmanDecoder
        dec = GoldenSunHuffmanDecoder(
            tla_rom.data, offsets_base=0x060A4C, trees_base=0x05F914)
        sample = bytes(tla_rom.data[0x060C38:0x060C38 + 64])
        a = dec.decode_string(sample)
        b = dec.decode_string(sample)
        assert a == b


class TestTLAEncoder:
    def test_encode_length_never_exceeds_slot(self, tla_rom, tla_segments):
        for segment in tla_segments:
            if 'encoder' not in segment:
                continue
            compressed = segment['encoder'](segment['raw_text'])
            assert (
                len(compressed) <= segment['compressed_length']
            ), segment['name']

    def test_segment_encoder_contract(self, tla_segments):
        dialogue = [s for s in tla_segments if s['name'].startswith('gs_dialogue_')]
        for segment in dialogue[:200]:
            assert callable(segment['encoder'])
            assert segment['compression'] == 'huffman'
            assert segment['compressed_length'] > 0
            assert segment['compressed_length'] == segment['end'] - segment['start']
            assert segment['pad_byte'] == 0xFF


class TestTLAInjector:
    def test_inject_single_message(self, tla_rom, tla_plugin, tla_segments, tmp_path):
        from core.injector import TextInjector

        translation = 'Hello World!'
        seg = next(
            (s for s in tla_segments
             if s['name'].startswith('gs_dialogue_')
             and _fits_segment(tla_plugin, s, translation, tla_rom)),
            None,
        )
        assert seg is not None, 'нет сегмента, подходящего под тестовый перевод'
        name = seg['name']

        injector = TextInjector(tla_rom.path)
        ok = injector.inject_segment(name, [translation], tla_plugin,
                                     segments=tla_segments)
        assert ok

        out_rom = tmp_path / 'patched.gba'
        injector.save(str(out_rom))
        assert out_rom.exists()
        assert len(out_rom.read_bytes()) == len(tla_rom.data)

        from core.rom import GameBoyROM
        patched = GameBoyROM(str(out_rom))
        patched_seg = next(
            s for s in tla_plugin.get_text_segments(patched)
            if s['name'] == name)
        assert patched_seg['raw_text'] == translation

    def test_inject_no_translation_is_noop(self, tla_rom):
        from core.injector import TextInjector
        plugin = GoldenSunTLAPlugin()
        injector = TextInjector(tla_rom.path)
        assert injector.inject_segment('gs_dialogue_f00_005', [], plugin) is True


@pytest.mark.rom_required
@pytest.mark.slow
def test_real_rom_roundtrip():
    """extract → inject (те же тексты) → extract: идентичные тексты."""
    if not _has_tla_rom():
        pytest.skip('Golden Sun TLA ROM не найден (легально-owned только)')
    from core.extractor import TextExtractor
    from core.injector import TextInjector

    plugin = GoldenSunTLAPlugin()
    with tempfile.TemporaryDirectory() as td:
        work = os.path.join(td, 'roundtrip.gba')
        shutil.copyfile(TLA_ROM, work)
        rom = GameBoyROM(TLA_ROM)
        segments = plugin.get_text_segments(rom)
        before = TextExtractor(TLA_ROM, rom=rom).extract()
        injector = TextInjector(work)
        injected = 0
        for seg in segments:
            texts = [m['text'] for m in before.get(seg['name'], [])]
            if injector.inject_segment(seg['name'], texts, plugin,
                                       segments=segments):
                injected += 1
        injector.save(work)
        assert injected == len(segments)

        after = TextExtractor(work, rom=GameBoyROM(work)).extract()
        for seg in segments:
            before_texts = [m['text'] for m in before.get(seg['name'], [])]
            after_texts = [m['text'] for m in after.get(seg['name'], [])]
            assert before_texts == after_texts, seg['name']
