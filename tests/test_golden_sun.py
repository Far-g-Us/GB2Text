"""
Тесты для плагина Golden Sun (GBA) - контекстный Хаффман.

Проверяются детерминированность декодера, token-маппинг, структура
сегментов и, при наличии легального пользовательского ROM, интеграция
с реальными данными (адреса/счётчики — только факты, не тексты).
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rom import GameBoyROM
from plugins.gba_golden_sun import (
    GS_CONTROL_TOKENS,
    GoldenSunHuffmanDecoder,
    GoldenSunHuffmanEncoder,
    GoldenSunPlugin,
)

# SHA1 Golden Sun (USA, Europe), совместим с goldensun-decomp
GS1_ROM = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'test_roms', 'Golden Sun (USA, Europe).gba',
)


def _has_gs_rom() -> bool:
    return os.path.exists(GS1_ROM)


def _fits_segment(plugin, segment, translation, rom) -> bool:
    """True, если перевод кодируется деревьями GS и помещается в окно сегмента."""
    try:
        compressed = segment['encoder'](translation)
    except (ValueError, KeyError, IndexError):
        return False
    return bool(len(compressed) <= segment['compressed_length'])


@pytest.fixture(scope='module')
def gs_plugin():
    return GoldenSunPlugin()


@pytest.fixture(scope='module')
def gs_rom():
    if not _has_gs_rom():
        pytest.skip("Golden Sun ROM не найден (легально-owned только)")
    return GameBoyROM(GS1_ROM)


@pytest.fixture(scope='module')
def gs_segments(gs_rom, gs_plugin):
    """Сегменты декодируются один раз на весь модуль."""
    return gs_plugin.get_text_segments(gs_rom)


class TestGoldenSunPluginContract:
    """Контракт плагина (core.plugin.GamePlugin)."""

    def test_plugin_matches_agse(self, gs_plugin):
        match = re.search(gs_plugin.game_id_pattern, 'GBA_AGSE')
        assert match is not None

    def test_plugin_rejects_agfe(self, gs_plugin):
        """AGFE принадлежит Golden Sun 2 (TLA) — отдельный плагин."""
        match = re.search(gs_plugin.game_id_pattern, 'GBA_AGFE')
        assert match is None

    def test_game_codes(self, gs_plugin, gs_rom):
        """Идентификация только AGSE (Golden Sun 1)."""
        match = re.fullmatch(gs_plugin.game_id_pattern, gs_rom.get_game_id())
        assert match is not None
        assert match.group(1) == 'AGSE'

    def test_terminators(self, gs_plugin):
        assert gs_plugin.get_terminators('gs_dialogue_f00_000') == [0x00]

    def test_compression_handler_none(self, gs_plugin):
        assert gs_plugin.get_compression_handler('gs_dialogue_f00_000') is None


class TestGoldenSunTokenMapping:
    """Контрольные коды и их обратный маппинг."""

    def test_nl_token(self):
        assert GS_CONTROL_TOKENS[0x01] == '{NL}'

    def test_end_token(self):
        assert GS_CONTROL_TOKENS[0x02] == '{END}'

    def test_tokens_avoid_split_patterns(self):
        """Токены не должны ломать _split_messages: без '[', '\n', '[XX]'."""
        for token in GS_CONTROL_TOKENS.values():
            assert '[' not in token
            assert '\n' not in token
            assert not re.fullmatch(r'\[[0-9A-Fa-f]{2}\]', token)
            assert token != '[END]'


class TestGoldenSunSegments:
    """Структура сегментов на реальном ROM."""

    def test_segment_count(self, gs_segments):
        # 42 файла x 256 строк (последний файл короче) + credits
        dialogue = [s for s in gs_segments if s['name'].startswith('gs_dialogue_')]
        assert len(dialogue) >= 10700

    def test_segment_bounds_in_rom(self, gs_rom, gs_segments):
        for segment in gs_segments:
            assert 0 <= segment['start'] < segment['end'] <= len(gs_rom.data)

    def test_segment_raw_text_not_empty(self, gs_segments):
        for segment in gs_segments:
            assert isinstance(segment['raw_text'], str)
            assert len(segment['raw_text']) > 0

    def test_all_dialogue_named_consistently(self, gs_segments):
        names = [s['name'] for s in gs_segments
                 if s['name'].startswith('gs_dialogue_')]
        assert all(re.fullmatch(r'gs_dialogue_f\d{2}_\d{3}', n) for n in names)
        assert len(set(names)) == len(names)


class TestGoldenSunHuffman:
    """Детерминированность и целостность декодера."""

    def test_decoder_deterministic(self, gs_rom):
        dec = GoldenSunHuffmanDecoder(gs_rom.data)
        sample = bytes(gs_rom.data[0x038434:0x038434 + 64])
        a = dec.decode_string(sample)
        b = dec.decode_string(sample)
        assert a == b

    def test_decode_terminates(self, gs_rom):
        dec = GoldenSunHuffmanDecoder(gs_rom.data)
        sample = bytes(gs_rom.data[0x038434:0x038434 + 2003])
        for length in (1, 3, 8, 32):
            out = dec.decode_string(sample[:length])
            assert isinstance(out, bytes)


class TestGoldenSunIntegration:
    """Integration: extractor прогоняет плагин end-to-end."""

    def test_extractor_runs(self, gs_rom, gs_plugin):
        from core.extractor import TextExtractor
        extractor = TextExtractor(gs_rom.path, rom=gs_rom)
        results = extractor.extract()
        dialogue_count = sum(
            1 for key in results if key.startswith('gs_dialogue_')
        )
        assert dialogue_count >= 10700

    def test_extraction_roundtrip_segments(self, gs_rom, gs_plugin):
        """Отдельные строки остаются отдельными сообщениями (без [END])."""
        from core.extractor import TextExtractor
        extractor = TextExtractor(gs_rom.path, rom=gs_rom)
        results = extractor.extract()
        key = 'gs_dialogue_f00_005'
        assert key in results
        messages = results[key]
        assert len(messages) == 1
        assert len(messages[0]['text']) > 0


class TestGoldenSunEncoder:
    """Рекомпрессия: энкодер обязан воспроизводить формат игры бит-в-бит."""

    def test_encode_matches_original_compressed(self, gs_rom, gs_segments):
        """encode(decode_string(compressed)) == исходные сжатые байты."""
        import struct

        from plugins.gba_golden_sun import (
            GS_DATA_FILES,
            GS_STRINGS_PER_FILE,
            GS_STRINGS_PTR_BASE,
        )

        dec = GoldenSunHuffmanDecoder(gs_rom.data)
        enc = GoldenSunHuffmanEncoder(gs_rom.data)

        checked = 0
        for fid in range(GS_DATA_FILES):
            strings_addr, lens_addr = struct.unpack_from(
                '<II', gs_rom.data, GS_STRINGS_PTR_BASE + fid * 8)
            strings_addr -= 0x08000000
            lens_addr -= 0x08000000
            pos = 0
            for sid in range(GS_STRINGS_PER_FILE):
                length = gs_rom.data[lens_addr + sid]
                if length == 0:
                    break
                compressed = bytes(gs_rom.data[strings_addr + pos:strings_addr + pos + length])
                raw = dec.decode_string(compressed)
                assert enc.compress_string(raw) == compressed
                checked += 1
                pos += length
        assert checked >= 10700

    def test_decode_after_encode_identity(self, gs_rom, gs_segments):
        """round-trip: decode(encode(raw)) == raw (строка с контрольным кодом)."""
        dec = GoldenSunHuffmanDecoder(gs_rom.data)
        enc = GoldenSunHuffmanEncoder(gs_rom.data)

        raw1 = b'Hello, World!'
        recompressed = enc.compress_string(raw1)
        assert dec.decode_string(recompressed) == raw1

        # строка с {END}: находим реальную строку из ROM, кодируемую деревьями
        raw2 = None
        for s in gs_segments:
            if 'encoder' not in s or '{END}' not in s['raw_text']:
                continue
            try:
                compressed = s['encoder'](s['raw_text'])
            except ValueError:
                continue
            raw2 = dec.decode_string(compressed)
            if raw2:
                break
        assert raw2 is not None and raw2 != raw1
        assert dec.decode_string(enc.compress_string(raw2)) == raw2

    def test_encode_length_never_exceeds_slot(self, gs_rom, gs_segments):
        """Любая закодированная строка не длиннее исходного окна — иначе пропуск."""
        for segment in gs_segments:
            if 'encoder' not in segment:
                continue
            compressed = segment['encoder'](segment['raw_text'])
            assert (
                len(compressed) <= segment['compressed_length']
            ), segment['name']

    def test_segment_encoder_contract(self, gs_segments):
        """Сегменты диалога предоставляют encoder + pad_byte + сжатую длину."""
        dialogue = [s for s in gs_segments if s['name'].startswith('gs_dialogue_')]
        assert len(dialogue) >= 10700
        for segment in dialogue:
            assert callable(segment['encoder'])
            assert segment['compression'] == 'huffman'
            assert segment['compressed_length'] > 0
            assert segment['compressed_length'] == segment['end'] - segment['start']
            assert segment['pad_byte'] == 0xFF


class TestGoldenSunInjector:
    """Вставка переведённых строк через core.injector.TextInjector."""

    def test_inject_single_message(self, gs_rom, gs_plugin, gs_segments, tmp_path):
        from core.injector import TextInjector

        translation = 'Hello World!'
        # не все строки кодируются (деревья GS построены по оригиналу):
        # ищем сегмент, где перевод укладывается в деревья и в окно
        seg = next(
            (s for s in gs_segments
             if s['name'].startswith('gs_dialogue_')
             and _fits_segment(gs_plugin, s, translation, gs_rom)),
            None,
        )
        assert seg is not None, 'нет сегмента, подходящего под тестовый перевод'
        name = seg['name']

        injector = TextInjector(gs_rom.path)
        # готовые сегменты передаются вставщику: повторный полный скан не нужен
        ok = injector.inject_segment(name, [translation], gs_plugin,
                                     segments=gs_segments)
        assert ok

        out_rom = tmp_path / 'patched.gba'
        injector.save(str(out_rom))
        assert out_rom.exists()
        assert len(out_rom.read_bytes()) == len(gs_rom.data)

        from core.rom import GameBoyROM
        patched = GameBoyROM(str(out_rom))
        patched_seg = next(
            s for s in gs_plugin.get_text_segments(patched)
            if s['name'] == name)
        assert patched_seg['raw_text'] == translation

    def test_inject_skips_unencodable_or_too_long(self, gs_rom, gs_plugin):
        from core.injector import TextInjector

        # строка, заведомо не кодируемая деревьями GS или не помещающаяся в окно
        # (символ '7' после '7' отсутствует в оригинальных деревьях)
        bad_text = '77 is not encodable 77'
        injector = TextInjector(gs_rom.path)
        ok = injector.inject_segment('gs_dialogue_f00_005', [bad_text], gs_plugin,
                                     skip_long=True)
        assert ok is False

    def test_inject_no_translation_is_noop(self, gs_rom):
        from core.injector import TextInjector
        plugin = GoldenSunPlugin()
        injector = TextInjector(gs_rom.path)
        assert injector.inject_segment('gs_dialogue_f00_005', [], plugin) is True
