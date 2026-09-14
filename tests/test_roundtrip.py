"""Round-trip тесты: extract → inject → extract для core/ модулей"""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.decoder import CharMapDecoder
from core.extractor import TextExtractor
from core.injector import TextInjector
from core.rom import GameBoyROM


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

SIMPLE_CHARMAP: dict[int, str] = {
    0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E',
    0x46: 'F', 0x47: 'G', 0x48: 'H', 0x49: 'I', 0x4A: 'J',
    0x4B: 'K', 0x4C: 'L', 0x4D: 'M', 0x4E: 'N', 0x4F: 'O',
    0x50: 'P', 0x51: 'Q', 0x52: 'R', 0x53: 'S', 0x54: 'T',
    0x55: 'U', 0x56: 'V', 0x57: 'W', 0x58: 'X', 0x59: 'Y',
    0x5A: 'Z', 0x20: ' ',
}

# Текст без 0x00 (терминатор) — используется в byte-level тестах
SAFE_TEXT = b'HELLO WORLD'


def _build_gb_rom(
    text_segments: dict[int, bytes] | None = None,
    size: int = 0x8000,
) -> bytes:
    """Строит минимальный валидный GB ROM."""
    data = bytearray(size)

    # Nintendo logo (0x104-0x133)
    nintendo_logo = bytes([
        0xCE, 0xED, 0x66, 0x66, 0xCC, 0x0D, 0x00, 0x0B,
        0x03, 0x73, 0x00, 0x83, 0x00, 0x0C, 0x00, 0x0D,
        0x00, 0x08, 0x19, 0x16, 0x83, 0x00, 0x73, 0x00,
        0x8B, 0x00, 0xD6, 0x00, 0xDC, 0x00, 0x2E, 0x00,
        0xE1, 0x00, 0x47, 0x18, 0x1F, 0x88, 0x89, 0x00,
        0x0E, 0xDC, 0xCC, 0x6E, 0xE6, 0xDD, 0xDD, 0xD9,
        0x99, 0xBB, 0xBB, 0x67, 0x63, 0x6E, 0x0E, 0xEC,
        0xCC, 0xDD, 0xDC, 0x99, 0x9F, 0xBB, 0xB9, 0x33,
        0x3E, 0x3C, 0x42, 0x79, 0xAB, 0x60, 0x3B, 0x89,
        0x43, 0x4E, 0x98, 0x56, 0x53, 0x4E, 0x4E, 0x7F,
        0x01, 0x2C, 0x58, 0x3A, 0x56, 0xC2, 0x49, 0x86,
        0x34, 0x50, 0x71, 0x62, 0x4F, 0x56, 0x6F, 0x41,
        0x4F, 0x29, 0x4C, 0x6F, 0x52, 0x53, 0x44, 0x53,
        0x47, 0x4D, 0x3A, 0x44, 0x5A, 0x47, 0x43, 0x20,
        0x01, 0x2C, 0x58, 0x3A, 0x56, 0xC2, 0x49, 0x86,
    ])
    data[0x104:0x104 + len(nintendo_logo)] = nintendo_logo

    data[0x147] = 0x00  # Cartridge type = ROM ONLY
    data[0x149] = 0x00  # RAM size = None

    if text_segments:
        for offset, text_bytes in text_segments.items():
            end = min(offset + len(text_bytes), size)
            data[offset:end] = text_bytes[:end - offset]

    # Header checksum (канонический: 0x134-0x14C, с title)
    checksum = 0
    for addr in range(0x0134, 0x014D):
        checksum = (checksum - data[addr] - 1) & 0xFF
    data[0x14D] = checksum

    # Global checksum
    global_checksum = 0
    for i in range(len(data)):
        if i not in (0x14E, 0x14F):
            global_checksum = (global_checksum + data[i]) & 0xFFFF
    data[0x14E] = (global_checksum >> 8) & 0xFF
    data[0x14F] = global_checksum & 0xFF

    return bytes(data)


def _make_temp_rom(data: bytes, suffix: str = ".gb") -> str:
    """Записывает ROM во временный файл, возвращает путь."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, data)
    os.close(fd)
    return path


def _simple_plugin():
    """Мок-плагин, возвращающий один сегмент 0x4000-0x4040."""

    class _Plugin:
        game_id_pattern = r'^TEST'

        def get_text_segments(self, rom):
            return [{
                'name': 'main_text',
                'start': 0x4000,
                'end': 0x4040,
                'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                'compression': None,
            }]

    return _Plugin()


def _mock_plugin_manager(plugin):
    """Создаёт PluginManager, который всегда возвращает нужный плагин."""

    class _PM:
        def get_plugin(self, game_id, system=None, cancellation_token=None, rom=None):
            return plugin

    return _PM()


# ─────────────────────────────────────────────────────────────
# P0: Basic round-trip
# ─────────────────────────────────────────────────────────────

class TestBasicRoundtrip:
    """Extract → inject → extract: текст должен сохраниться."""

    def test_roundtrip_preserves_text(self):
        """Текст после inject эквивалентен оригиналу при повторном extract."""
        rom_data = _build_gb_rom({0x4000: SAFE_TEXT})
        rom_path = _make_temp_rom(rom_data)
        output_path = rom_path + ".out.gbc"

        try:
            plugin = _simple_plugin()
            pm = _mock_plugin_manager(plugin)

            # 1. Extract
            ext = TextExtractor(rom_path, plugin_manager=pm)
            results = ext.extract()

            assert 'main_text' in results
            messages = results['main_text']
            assert len(messages) > 0

            original_text = messages[0]['text']
            assert 'HELLO' in original_text

            # 2. Inject — вставляем тот же текст
            injector = TextInjector(rom_path)
            translations = [original_text]
            ok = injector.inject_segment('main_text', translations, plugin)
            assert ok, "inject_segment должен вернуть True"
            injector.save(output_path)

            # 3. Re-extract из изменённого ROM
            ext2 = TextExtractor(output_path, plugin_manager=pm)
            results2 = ext2.extract()

            messages2 = results2['main_text']
            reextracted_text = messages2[0]['text']

            # Текст должен содержать те же ключевые слова
            for word in original_text.split():
                if word.isalpha():
                    assert word in reextracted_text, (
                        f"Слово '{word}' потеряно после round-trip: "
                        f"'{original_text}' → '{reextracted_text}'"
                    )
            # Дополнительно проверяем порядок слов
            orig_words = [w for w in original_text.split() if w.isalpha()]
            reext_words = [w for w in reextracted_text.split() if w.isalpha()]
            assert orig_words == reext_words, (
                f"Порядок слов изменился: {orig_words} → {reext_words}"
            )
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)

    def test_roundtrip_preserves_non_text_bytes(self):
        """Байты за пределами текстового сегмента не должны изменяться."""
        rom_data = _build_gb_rom({0x4000: SAFE_TEXT})
        marker_byte = rom_data[0x5000]
        rom_path = _make_temp_rom(rom_data)
        output_path = rom_path + ".out.gbc"

        try:
            plugin = _simple_plugin()
            injector = TextInjector(rom_path)
            injector.inject_segment('main_text', [SAFE_TEXT.decode()], plugin)
            injector.save(output_path)

            modified = bytearray(open(output_path, 'rb').read())
            assert modified[0x5000] == marker_byte
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)


# ─────────────────────────────────────────────────────────────
# P0: Checksum preservation
# ─────────────────────────────────────────────────────────────

class TestChecksumPreservation:
    """Глобальный и header checksum должны быть валидны после inject."""

    def test_header_checksum_valid_after_inject(self):
        """validate_header() должен вернуть True после inject изменённого текста."""
        rom_data = _build_gb_rom({0x4000: b'ABC'})
        rom_path = _make_temp_rom(rom_data)

        try:
            rom_before = GameBoyROM(rom_path)
            assert rom_before.validate_header(), "Header checksum невалиден ДО inject"

            injector = TextInjector(rom_path)
            # Вставляем ДРУГОЙ текст — байты сегмента реально меняются
            ok = injector.inject_segment('main_text', ['ZZ'], _simple_plugin())
            assert ok
            output_path = rom_path + ".out.gbc"
            injector.save(output_path)

            rom_after = GameBoyROM(output_path)
            assert rom_after.validate_header(), "Header checksum невалиден ПОСЛЕ inject"
            assert b'ZZ' in rom_after.data[0x4000:0x4010]
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)

    def test_global_checksum_matches_after_inject(self):
        """calculate_global_checksum() должен совпадать с хранимым после inject."""
        rom_data = _build_gb_rom({0x4000: b'XYZ'})
        rom_path = _make_temp_rom(rom_data)

        try:
            injector = TextInjector(rom_path)
            # Вставляем текст, который РЕАЛЬНО меняет байты сегмента
            ok = injector.inject_segment('main_text', ['AB'], _simple_plugin())
            assert ok
            output_path = rom_path + ".out.gbc"
            injector.save(output_path)

            rom_after = GameBoyROM(output_path)
            calculated = rom_after.calculate_global_checksum()
            stored = (rom_after.data[0x14E] << 8) | rom_after.data[0x14F]
            assert calculated == stored, (
                f"Global checksum mismatch: calculated=0x{calculated:04X}, "
                f"stored=0x{stored:04X}"
            )
            # Проверяем, что это не ложный тест: сегмент действительно изменился
            segment_bytes = bytes(rom_after.data[0x4000:0x4010])
            assert b'AB' in segment_bytes and b'XYZ' not in segment_bytes
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)

    def test_global_checksum_differs_from_original_after_change(self):
        """После изменения байтов global checksum обязан пересчитаться.

        Без пересчёта in-place инъекция оставила бы устаревшее значение,
        и calculated != stored — тест ловит именно эту регрессию.
        """
        rom_data = _build_gb_rom({0x4000: b'ABCD'})
        rom_path = _make_temp_rom(rom_data)
        rom_before = GameBoyROM(rom_path)
        original_stored = (rom_before.data[0x14E] << 8) | rom_before.data[0x14F]

        try:
            injector = TextInjector(rom_path)
            ok = injector.inject_segment('main_text', ['AB'], _simple_plugin())
            assert ok
            output_path = rom_path + ".out.gbc"
            injector.save(output_path)

            rom_after = GameBoyROM(output_path)
            new_stored = (rom_after.data[0x14E] << 8) | rom_after.data[0x14F]
            assert new_stored != original_stored, (
                "Global checksum не изменился после замены текста — пересчёт не работает"
            )
            calculated = rom_after.calculate_global_checksum()
            assert calculated == new_stored
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)


# ─────────────────────────────────────────────────────────────
# P0: Byte-level injection correctness
# ─────────────────────────────────────────────────────────────

class TestByteLevelCorrectness:
    """Проверка что байты записаны точно по预期."""

    def test_inject_writes_exact_bytes(self):
        """Байты перевода записываются точно в указанный offset."""
        # original_messages ищет непрерывные байты до терминатора (0x00)
        # Поэтому кладём данные + terminating 0x00
        original = b'AAAA' + b'\x00'
        rom_data = _build_gb_rom({0x4000: original})
        rom_path = _make_temp_rom(rom_data)

        try:
            injector = TextInjector(rom_path)
            segment = {
                'name': 'test',
                'start': 0x4000,
                'end': 0x4010,
                'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                'compression': None,
            }
            plugin = _simple_plugin()
            plugin.get_text_segments = lambda rom: [segment]

            ok = injector.inject_segment('test', ['AB'], plugin)
            assert ok, "inject_segment должен вернуть True"

            # 'A' = 0x41, 'B' = 0x42
            assert injector.modified_data[0x4000] == 0x41
            assert injector.modified_data[0x4001] == 0x42
        finally:
            os.unlink(rom_path)

    def test_inject_pads_shorter_translation(self):
        """Короткий перевод дополняется pad-байтами."""
        # 4 байта текста + terminator
        original = b'ABCD' + b'\x00'
        rom_data = _build_gb_rom({0x4000: original})
        rom_path = _make_temp_rom(rom_data)

        try:
            injector = TextInjector(rom_path)
            segment = {
                'name': 'test',
                'start': 0x4000,
                'end': 0x4010,
                'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                'compression': None,
            }
            plugin = _simple_plugin()
            plugin.get_text_segments = lambda rom: [segment]

            # Оригинал 4 байта, перевод 2 байта → pad до 4
            ok = injector.inject_segment('test', ['AB'], plugin)
            assert ok

            assert injector.modified_data[0x4000] == 0x41  # A
            assert injector.modified_data[0x4001] == 0x42  # B
            assert injector.modified_data[0x4002] == 0x20  # pad
            assert injector.modified_data[0x4003] == 0x20  # pad
        finally:
            os.unlink(rom_path)


# ─────────────────────────────────────────────────────────────
# P0: Pointer preservation
# ─────────────────────────────────────────────────────────────

class TestPointerPreservation:
    """Указатели на текст не должны ломаться после inject."""

    def test_pointers_unchanged_after_inject(self):
        """Указатели за пределами сегмента не модифицируются."""
        pointer_target = 0x4000
        pointer_bytes = bytes([pointer_target & 0xFF, (pointer_target >> 8) & 0xFF])

        rom_data = _build_gb_rom({
            0x4000: SAFE_TEXT,
            0x3FFE: pointer_bytes,
        })
        rom_path = _make_temp_rom(rom_data)
        output_path = rom_path + ".out.gbc"

        try:
            injector = TextInjector(rom_path)
            injector.inject_segment('main_text', [SAFE_TEXT.decode()], _simple_plugin())
            injector.save(output_path)

            result = bytearray(open(output_path, 'rb').read())
            assert result[0x3FFE] == pointer_bytes[0]
            assert result[0x3FFF] == pointer_bytes[1]
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)


# ─────────────────────────────────────────────────────────────
# P0: Multiple segments round-trip
# ─────────────────────────────────────────────────────────────

class TestMultiSegmentRoundtrip:
    """Round-trip для нескольких сегментов."""

    def test_two_segments_roundtrip(self):
        """Два сегмента: текст в каждом сохраняется."""
        rom_data = _build_gb_rom({
            0x4000: b'FIRST',
            0x4100: b'SECOND',
        })
        rom_path = _make_temp_rom(rom_data)
        output_path = rom_path + ".out.gbc"

        try:
            class _MultiPlugin:
                game_id_pattern = r'^MULTI'

                def get_text_segments(self, rom):
                    return [
                        {
                            'name': 'seg1',
                            'start': 0x4000,
                            'end': 0x4020,
                            'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                            'compression': None,
                        },
                        {
                            'name': 'seg2',
                            'start': 0x4100,
                            'end': 0x4120,
                            'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                            'compression': None,
                        },
                    ]

            plugin = _MultiPlugin()
            pm = _mock_plugin_manager(plugin)

            injector = TextInjector(rom_path)
            ok1 = injector.inject_segment('seg1', ['FIRST'], plugin)
            ok2 = injector.inject_segment('seg2', ['SECOND'], plugin)
            assert ok1 and ok2
            injector.save(output_path)

            ext = TextExtractor(output_path, plugin_manager=pm)
            results = ext.extract()

            assert 'seg1' in results
            assert 'seg2' in results
            assert 'FIRST' in results['seg1'][0]['text']
            assert 'SECOND' in results['seg2'][0]['text']
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)


# ─────────────────────────────────────────────────────────────
# P0: Edge case round-trip
# ─────────────────────────────────────────────────────────────

class TestEdgeCaseRoundtrip:
    """Граничные случаи round-trip."""

    def test_empty_segment_roundtrip(self):
        """Пустой сегмент (все нули) — inject не должен падать."""
        rom_data = _build_gb_rom({0x4000: b'\x00' * 16})
        rom_path = _make_temp_rom(rom_data)

        try:
            injector = TextInjector(rom_path)
            ok = injector.inject_segment('main_text', [], _simple_plugin())
            # Пустой список = нет сообщений = OK
            assert ok is True
        finally:
            os.unlink(rom_path)

    def test_same_text_roundtrip_identity(self):
        """Текст = 'A' * N — после round-trip байты совпадают."""
        text = b'AAAA'
        rom_data = _build_gb_rom({0x4000: text})
        rom_path = _make_temp_rom(rom_data)
        output_path = rom_path + ".out.gbc"

        try:
            plugin = _simple_plugin()
            injector = TextInjector(rom_path)
            injector.inject_segment('main_text', ['AAAA'], plugin)
            injector.save(output_path)

            orig = bytearray(open(rom_path, 'rb').read())[0x4000:0x4004]
            result = bytearray(open(output_path, 'rb').read())[0x4000:0x4004]
            assert orig == result, f"Байты не совпадают: {orig.hex()} != {result.hex()}"
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)


# ─────────────────────────────────────────────────────────────
# Compression round-trip
# ─────────────────────────────────────────────────────────────

class TestCompressionRoundtrip:
    """Round-trip через compress/decompress."""

    def test_lz77_compress_is_identity(self):
        """LZ77 compress (заглушка) возвращает те же данные."""
        from core.decoder import LZ77Handler
        handler = LZ77Handler()
        data = b'HELLO WORLD'
        assert handler.compress(data) == data

    def test_gba_lz77_compress_decompress_roundtrip(self):
        """GBA LZ77 compress → decompress roundtrip."""
        from core.gba_support import GBALZ77Handler
        handler = GBALZ77Handler()
        original = b'ABCDEFGHIJ' * 10
        compressed = handler.compress(original)
        assert compressed != original

        decompressed, _ = handler.decompress(compressed, 0)
        assert decompressed == original

    def test_gba_lz77_empty_roundtrip(self):
        """GBA LZ77 compress → decompress с пустыми данными."""
        from core.gba_support import GBALZ77Handler
        handler = GBALZ77Handler()
        original = b''
        compressed = handler.compress(original)
        decompressed, _ = handler.decompress(compressed, 0)
        assert decompressed == original


# ─────────────────────────────────────────────────────────────
# CharMap encode/decode round-trip
# ─────────────────────────────────────────────────────────────

class TestCharmapRoundtrip:
    """CharMapDecoder encode → decode round-trip."""

    def test_encode_decode_roundtrip(self):
        """encode(text) → decode(bytes) должен вернуть исходный текст."""
        decoder = CharMapDecoder(SIMPLE_CHARMAP)
        original = "HELLO WORLD"
        encoded = decoder.encode(original)
        decoded = decoder.decode(encoded, 0, len(encoded))
        assert decoded == original

    def test_encode_unknown_char_uses_space(self):
        """Неизвестный символ заменяется на пробел при encode."""
        decoder = CharMapDecoder(SIMPLE_CHARMAP)
        encoded = decoder.encode("A?B")
        decoded = decoder.decode(encoded, 0, len(encoded))
        assert 'A' in decoded
        assert 'B' in decoded

    def test_decode_terminator_produces_newline(self):
        """Байт 0x00 декодируется как \\n."""
        decoder = CharMapDecoder(SIMPLE_CHARMAP)
        data = bytes([0x41, 0x00, 0x42])
        result = decoder.decode(data, 0, len(data))
        assert '\n' in result
        assert 'A' in result
        assert 'B' in result


# ─────────────────────────────────────────────────────────────
# P1: GBA round-trip
# ─────────────────────────────────────────────────────────────

def _build_gba_rom(text_segments: dict[int, bytes] | None = None, size: int = 0x10000) -> bytes:
    """Строит минимальный валидный GBA ROM (32-bit header)."""
    data = bytearray(size)

    # GBA заголовок: 0xA0-0xAB = game title, 0x0BD = complement check
    # Nintendo logo в GBA начинается с 0x04
    data[0] = 0x2E  # байт входа (ARM branch)
    data[1] = 0x00
    data[2] = 0x00
    data[3] = 0xEA  # branch to 0x08000000

    # Game title (0xA0-0xAB)
    title = b'TESTROM'
    data[0xA0:0xA0 + len(title)] = title

    if text_segments:
        for offset, text_bytes in text_segments.items():
            end = min(offset + len(text_bytes), size)
            data[offset:end] = text_bytes[:end - offset]

    # GBA header checksum at 0xBD: (0 - sum(0xA0..0xBC) - 0x19) & 0xFF
    # Считается ПОСЛЕ записи сегментов, чтобы не зависеть от их содержимого.
    data[0xBD] = (0 - sum(data[0xA0:0xBD]) - 0x19) & 0xFF

    return bytes(data)


class TestGBARoundtrip:
    """P1: GBA-specific round-trip тесты."""

    def test_gba_roundtrip_preserves_text(self):
        """GBA ROM: text после inject сохраняется."""
        text = b'HELLO GBA'
        rom_data = _build_gba_rom({0x8000: text})
        rom_path = _make_temp_rom(rom_data, suffix=".gba")
        output_path = rom_path + ".out.gba"

        try:
            # GBA charmap: расширенный (0x20-0x7E = printable ASCII)
            gba_charmap = {i: chr(i) for i in range(0x20, 0x7F)}
            gba_charmap[0x00] = '\n'

            class _GBAPlugin:
                game_id_pattern = r'^GAME_00$'

                def get_text_segments(self, rom):
                    return [{
                        'name': 'gba_text',
                        'start': 0x8000,
                        'end': 0x8040,
                        'decoder': CharMapDecoder(gba_charmap),
                        'compression': None,
                    }]

            plugin = _GBAPlugin()
            pm = _mock_plugin_manager(plugin)

            ext = TextExtractor(rom_path, plugin_manager=pm)
            results = ext.extract()

            assert 'gba_text' in results
            messages = results['gba_text']
            assert len(messages) > 0
            assert 'HELLO' in messages[0]['text']

            # Inject
            injector = TextInjector(rom_path)
            ok = injector.inject_segment('gba_text', ['HELLO GBA'], plugin)
            assert ok
            injector.save(output_path)

            # Re-extract
            ext2 = TextExtractor(output_path, plugin_manager=pm)
            results2 = ext2.extract()
            messages2 = results2['gba_text']
            assert 'HELLO' in messages2[0]['text']
            assert 'GBA' in messages2[0]['text']
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)

    def test_gba_checksum_valid_after_inject(self):
        """GBA ROM: header checksum валиден до и после inject, complement пересчитан."""
        rom_data = _build_gba_rom({0x8000: b'ABC'})
        rom_path = _make_temp_rom(rom_data, suffix=".gba")

        try:
            gba_charmap = {i: chr(i) for i in range(0x20, 0x7F)}
            gba_charmap[0x00] = '\n'

            class _GBAPlugin:
                game_id_pattern = r'^GAME_00$'
                def get_text_segments(self, rom):
                    return [{
                        'name': 'gba_text',
                        'start': 0x8000,
                        'end': 0x8020,
                        'decoder': CharMapDecoder(gba_charmap),
                        'compression': None,
                    }]

            rom_before = GameBoyROM(rom_path)
            assert rom_before.validate_header(), "GBA header checksum невалиден ДО inject"

            injector = TextInjector(rom_path)
            ok = injector.inject_segment('gba_text', ['ZZZ'], _GBAPlugin())
            assert ok
            output_path = rom_path + ".out.gba"
            injector.save(output_path)

            rom_after = GameBoyROM(output_path)
            assert rom_after.validate_header(), "GBA header checksum невалиден ПОСЛЕ inject"
            assert bytes(rom_after.data[0x8000:0x8003]) == b'ZZZ'
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)


# ─────────────────────────────────────────────────────────────
# P1: Pointer relocation
# ─────────────────────────────────────────────────────────────

class TestPointerRelocation:
    """P1: Указатели должны оставаться валидными после inject."""

    def test_pointer_in_bank0_unchanged(self):
        """Указатель в bank 0 (0x0000-0x3FFF) не изменяется после inject в bank 1."""
        pointer_target = 0x4000
        pointer_bytes = bytes([
            pointer_target & 0xFF,
            (pointer_target >> 8) & 0xFF,
        ])

        rom_data = _build_gb_rom({
            0x3FFE: pointer_bytes,  # указатель в bank 0
            0x4000: b'HELLO',
        })
        rom_path = _make_temp_rom(rom_data)
        output_path = rom_path + ".out.gbc"

        try:
            plugin = _simple_plugin()
            injector = TextInjector(rom_path)
            injector.inject_segment('main_text', ['HELLO'], plugin)
            injector.save(output_path)

            result = bytearray(open(output_path, 'rb').read())
            # Указатель не должен измениться
            assert result[0x3FFE] == pointer_bytes[0]
            assert result[0x3FFF] == pointer_bytes[1]
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)

    def test_multiple_pointers_preserved(self):
        """Несколько указателей сохраняются после inject."""
        ptr1 = bytes([0x00, 0x40])  # -> 0x4000
        ptr2 = bytes([0x10, 0x41])  # -> 0x4110

        rom_data = _build_gb_rom({
            0x3F00: ptr1 + ptr2,
            0x4000: b'FIRST',
            0x4110: b'SECOND',
        })
        rom_path = _make_temp_rom(rom_data)
        output_path = rom_path + ".out.gbc"

        try:
            class _MultiSegPlugin:
                game_id_pattern = r'^MULTI'
                def get_text_segments(self, rom):
                    return [
                        {'name': 's1', 'start': 0x4000, 'end': 0x4020,
                         'decoder': CharMapDecoder(SIMPLE_CHARMAP), 'compression': None},
                        {'name': 's2', 'start': 0x4110, 'end': 0x4130,
                         'decoder': CharMapDecoder(SIMPLE_CHARMAP), 'compression': None},
                    ]

            plugin = _MultiSegPlugin()
            injector = TextInjector(rom_path)
            injector.inject_segment('s1', ['FIRST'], plugin)
            injector.inject_segment('s2', ['SECOND'], plugin)
            injector.save(output_path)

            result = bytearray(open(output_path, 'rb').read())
            assert result[0x3F00:0x3F02] == bytearray(ptr1)
            assert result[0x3F02:0x3F04] == bytearray(ptr2)
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)


# ─────────────────────────────────────────────────────────────
# P1: Compression + injection integration
# ─────────────────────────────────────────────────────────────

class TestCompressionInjectionIntegration:
    """P1: Интеграция сжатия и инжекции."""

    def test_inject_with_compression_object(self):
        """inject_segment с compression объектом (не строкой)."""
        rom_data = _build_gb_rom({0x4000: b'ABCDEF' + b'\x00'})
        rom_path = _make_temp_rom(rom_data)

        try:
            class _FakeCompression:
                def decompress(self, data, start):
                    return data[start:], len(data) - start

            segment = {
                'name': 'compressed',
                'start': 0x4000,
                'end': 0x4010,
                'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                'compression': _FakeCompression(),
            }

            class _CompPlugin:
                game_id_pattern = r'^COMP'
                def get_text_segments(self, rom):
                    return [segment]

            injector = TextInjector(rom_path)
            ok = injector.inject_segment('compressed', ['ABCDEF'], _CompPlugin())
            assert ok
        finally:
            os.unlink(rom_path)

    def test_inject_with_string_compression(self):
        """inject_segment с строковым compression типом."""
        rom_data = _build_gb_rom({0x4000: b'GHIJ' + b'\x00'})
        rom_path = _make_temp_rom(rom_data)

        try:
            segment = {
                'name': 'compressed_str',
                'start': 0x4000,
                'end': 0x4010,
                'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                'compression': 'lz77',  # строковый тип
            }

            class _StrCompPlugin:
                game_id_pattern = r'^SCMP'
                def get_text_segments(self, rom):
                    return [segment]

            injector = TextInjector(rom_path)
            # Не падает при строковом compression
            ok = injector.inject_segment('compressed_str', ['GHIJ'], _StrCompPlugin())
            assert isinstance(ok, bool)
        finally:
            os.unlink(rom_path)


# ─────────────────────────────────────────────────────────────
# P1: MultiByte charmap roundtrip
# ─────────────────────────────────────────────────────────────

MULTIBYTE_CHARMAP: dict[int, str] = {
    # Латиница (1 байт)
    0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E',
    0x46: 'F', 0x47: 'G', 0x48: 'H', 0x49: 'I', 0x4A: 'J',
    0x20: ' ',
    # Кириллица (2 байта в ROM, 1 символ в decoded)
    0x80: 'А', 0x81: 'Б', 0x82: 'В', 0x83: 'Г', 0x84: 'Д',
    0x85: 'Е', 0x86: 'Ж', 0x87: 'З', 0x88: 'И', 0x89: 'Й',
    0x8A: 'К', 0x8B: 'Л', 0x8C: 'М', 0x8D: 'Н', 0x8E: 'О',
    0x8F: 'П', 0x90: 'Р', 0x91: 'С', 0x92: 'Т', 0x93: 'У',
    0x94: 'Ф', 0x95: 'Х', 0x96: 'Ц', 0x97: 'Ч', 0x98: 'Ш',
    0x99: 'Щ', 0x9A: 'Ъ', 0x9B: 'Ы', 0x9C: 'Ь', 0x9D: 'Э',
    0x9E: 'Ю', 0x9F: 'Я',
}


class TestMultiByteCharmapRoundtrip:
    """P1: MultiByte charmap encode → decode round-trip."""

    def test_cyrillic_single_char_roundtrip(self):
        """Один кириллический символ: encode → decode."""
        decoder = CharMapDecoder(MULTIBYTE_CHARMAP)
        encoded = decoder.encode('А')
        decoded = decoder.decode(encoded, 0, len(encoded))
        assert 'А' in decoded

    def test_mixed_latin_cyrillic_roundtrip(self):
        """Смешанный текст: латиница + кириллица."""
        decoder = CharMapDecoder(MULTIBYTE_CHARMAP)
        original = 'AБB'
        encoded = decoder.encode(original)
        decoded = decoder.decode(encoded, 0, len(encoded))
        # Каждый символ должен присутствовать
        assert 'A' in decoded
        assert 'Б' in decoded
        assert 'B' in decoded

    def test_cyrillic_word_roundtrip(self):
        """Кириллическое слово."""
        decoder = CharMapDecoder(MULTIBYTE_CHARMAP)
        original = 'АБВ'
        encoded = decoder.encode(original)
        decoded = decoder.decode(encoded, 0, len(encoded))
        assert decoded == original

    def test_long_cyrillic_text_roundtrip(self):
        """Длинный кириллический текст."""
        decoder = CharMapDecoder(MULTIBYTE_CHARMAP)
        original = 'АБВГДЕЖЗИЙКЛМНОП' * 5
        encoded = decoder.encode(original)
        decoded = decoder.decode(encoded, 0, len(encoded))
        assert decoded == original
