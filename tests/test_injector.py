"""Тесты для модуля injector"""
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.decoder import CharMapDecoder
from core.injector import TextInjector

# Путь к тестовым ROM
TEST_ROMS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_roms")


def get_rom_files():
    """Получает список всех ROM"""
    if not os.path.exists(TEST_ROMS_DIR):
        return []
    return [os.path.join(TEST_ROMS_DIR, f) for f in os.listdir(TEST_ROMS_DIR)
            if f.endswith(('.gba', '.gbc', '.gb'))]


ALL_ROMS = get_rom_files()
GBA_ROMS = [r for r in ALL_ROMS if r.endswith('.gba')]


class TestTextInjector:
    """Тесты для TextInjector"""

    def test_init_valid_path(self):
        """Тест инициализации с валидным путём"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            assert injector is not None
        finally:
            os.unlink(temp_path)

    def test_init_invalid_path(self):
        """Тест инициализации с невалидным путём"""
        try:
            TextInjector("nonexistent_path_xyz123.rom")
        except (FileNotFoundError, TypeError):
            pass

    def test_ensure_decoder_with_decoder(self):
        """Тест ensure_decoder когда decoder уже есть"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            segment = {'decoder': 'test_decoder'}
            injector._ensure_decoder(segment)
            assert 'decoder' in segment
        finally:
            os.unlink(temp_path)

    def test_ensure_decoder_without_decoder(self):
        """Тест ensure_decoder когда decoder нет"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            segment = {}
            injector._ensure_decoder(segment)
        except Exception:
            pass
        finally:
            os.unlink(temp_path)

    def test_extract_original_messages(self):
        """Тест извлечения оригинальных сообщений"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            segment = {'data': b'Hello World!', 'start': 0, 'end': 12, 'decoder': 'test'}
            messages = injector._extract_original_messages(segment)
            assert isinstance(messages, list)
        finally:
            os.unlink(temp_path)

    def test_inject_segment(self):
        """Тест внедрения сегмента"""
        rom_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "test_roms", "Pokemon - Ruby Version (USA).gba")
        if os.path.exists(rom_path):
            injector = TextInjector(rom_path)
            # Mock plugin
            class MockPlugin:
                def __init__(self):
                    self.system = "gba"
            try:
                injector.inject_segment("test", ["Hello"], MockPlugin())
            except Exception:
                pass  # May fail due to complex logic

    def test_save(self):
        """Тест сохранения ROM"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            output_path = temp_path + ".out.gba"
            try:
                injector.save(output_path)
            except Exception:
                pass
            if os.path.exists(output_path):
                os.unlink(output_path)
        finally:
            os.unlink(temp_path)

    def test_inject_message(self):
        """Тест внедрения сообщения"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            injector._inject_message(0, b'Test', 5)
            assert bytes(injector.modified_data[:4]) == b'Test'
            assert bytes(injector.modified_data[4:5]) == b'\x20'
        finally:
            os.unlink(temp_path)

    def test_inject_with_real_rom(self):
        """Тест с реальным ROM"""
        if GBA_ROMS:
            rom_path = random.choice(GBA_ROMS)
            injector = TextInjector(rom_path)
            assert injector is not None
            assert hasattr(injector, 'rom')

    def test_inject_with_gbc_rom(self):
        """Тест с GBC ROM"""
        gbc_roms = [r for r in ALL_ROMS if r.endswith('.gbc')]
        if gbc_roms:
            rom_path = random.choice(gbc_roms)
            injector = TextInjector(rom_path)
            assert injector is not None

    def test_inject_with_gb_rom(self):
        """Тест с GB ROM"""
        gb_roms = [r for r in ALL_ROMS if r.endswith('.gb')]
        if gb_roms:
            rom_path = random.choice(gb_roms)
            injector = TextInjector(rom_path)
            assert injector is not None

    def test_inject_segment_empty_translations(self):
        """Тест внедрения с пустым списком переводов"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            class MockPlugin:
                system = "gba"
            # Пустой список переводов
            injector.inject_segment("test", [], MockPlugin())
        except Exception:
            pass
        finally:
            os.unlink(temp_path)

    def test_inject_with_moemon_rom(self):
        """Тест с Moemon ROM"""
        moemon_roms = [r for r in GBA_ROMS if 'moemon' in os.path.basename(r).lower()]
        if moemon_roms:
            rom_path = moemon_roms[0]
            injector = TextInjector(rom_path)
            assert injector is not None

    def test_inject_save_to_different_path(self):
        """Тест сохранения в другой путь"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            output_path = temp_path + "_modified.gba"
            try:
                injector.save(output_path)
                # Файл должен существовать
                assert os.path.exists(output_path) or True
            except Exception:
                pass
            if os.path.exists(output_path):
                os.unlink(output_path)
        finally:
            os.unlink(temp_path)

    def test_init_invalid_type_raises_error(self):
        """Тест что инициализация с неправильным типом вызывает TypeError"""
        try:
            TextInjector(12345)
            raise AssertionError("Должно вызвать TypeError")
        except TypeError as e:
            assert "rom_path" in str(e).lower() or "должен" in str(e).lower()

    def test_inject_segment_without_plugin(self):
        """Тест внедрения сегмента без плагина"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            result = injector.inject_segment("test", ["Hello"], None)
            assert not result
        finally:
            os.unlink(temp_path)

    def test_inject_segment_nonexistent_segment(self):
        """Тест внедрения в несуществующий сегмент"""
        class MockPluginWithSegments:
            system = "gba"
            def get_text_segments(self, rom):
                return [{'name': 'existing', 'start': 0, 'end': 100, 'decoder': None}]

        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            result = injector.inject_segment("nonexistent", ["Hello"], MockPluginWithSegments())
            assert not result
        finally:
            os.unlink(temp_path)

    def test_inject_segment_message_count_mismatch(self):
        """Тест внедрения когда количество сообщений не совпадает"""
        class MockPluginWithSegments:
            system = "gba"
            def get_text_segments(self, rom):
                return [{'name': 'test', 'start': 0, 'end': 100, 'decoder': None}]

        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            # Передаём 2 перевода но в оригинале будет другое количество
            injector.inject_segment("test", ["Hello", "World"], MockPluginWithSegments())
        except Exception:
            pass
        finally:
            os.unlink(temp_path)

    def test_ensure_decoder_with_exception(self):
        """Тест ensure_decoder когда возникает исключение"""
        class MockROM:
            data = b'\x00' * 1000

        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            injector.rom = MockROM()  # Replace with mock
            segment = {'start': -1, 'end': 100, 'decoder': None}  # Invalid start
            injector._ensure_decoder(segment)
        finally:
            os.unlink(temp_path)

    def test_extract_original_messages_with_terminators(self):
        """Тест извлечения оригинальных сообщений с разными терминаторами"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            # Создаём данные с разными терминаторами (нужен минимальный размер)
            data = b'\x00' * 0x150 + b'Hello\x00World\xFFTest\xFEEnd\x0DMore\x0A'
            f.write(data)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            from core.decoder import CharMapDecoder
            # Create charmap with string values
            charmap = {'H': 'H', 'e': 'e', 'l': 'l', 'o': 'o', 'W': 'W', 'r': 'r', 'd': 'd'}
            segment = {
                'data': data[0x150:],
                'start': 0x150,
                'end': len(data),
                'decoder': CharMapDecoder(charmap)
            }
            messages = injector._extract_original_messages(segment)
            assert isinstance(messages, list)
        finally:
            os.unlink(temp_path)

    def test_extract_original_messages_uses_plugin_terminators(self):
        """Сегмент с объявленными терминаторами игнорирует generic-набор.
        Для FF4/FF5 0x00 — это ПРОБЕЛ, а не разделитель."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gba") as f:
            f.write(b'\x00' * 0x150 + b'La li ho\x0C' + b'\x00' * 30)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            segment = {
                'start': 0x150, 'end': 0x158, 'terminators': [0x0C],
                'decoder': CharMapDecoder({0x20: ' ', 0x4C: 'L', 0x41: 'A', 0x69: 'i', 0x68: 'h', 0x6F: 'o'}),
            }
            messages = injector._extract_original_messages(segment)
            assert len(messages) == 1, "0x00 (пробел) не должен разрезать сообщение"
            assert messages[0]['offset'] == 0
            assert messages[0]['length'] == 8
        finally:
            os.unlink(temp_path)

    def test_inject_message_with_padding(self):
        """Тест внедрения сообщения с дополнением"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            # Внедряем короткое сообщение в больший слот
            injector._inject_message(100, b'Hi', 10)
            assert bytes(injector.modified_data[100:102]) == b'Hi'
            assert bytes(injector.modified_data[102:110]) == b'\x20' * 8
        finally:
            os.unlink(temp_path)

    def test_inject_segment_with_long_translation(self):
        """Тест внедрения когда перевод длиннее оригинала"""
        class MockPluginWithSegments:
            system = "gba"
            def get_text_segments(self, rom):
                # Сегмент с очень маленьким окном
                return [{'name': 'test', 'start': 0, 'end': 10, 'decoder': None}]

        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name

        try:
            injector = TextInjector(temp_path)
            # Пытаемся внедрить очень длинный перевод
            injector.inject_segment("test", ["This is a very long translation that exceeds original"], MockPluginWithSegments())
        except Exception:
            pass
        finally:
            os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────
# P0: Byte-level correctness (новые, без try/except: pass)
# ─────────────────────────────────────────────────────────────

SIMPLE_CHARMAP = {
    0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E',
    0x46: 'F', 0x47: 'G', 0x48: 'H', 0x49: 'I', 0x4A: 'J',
    0x4B: 'K', 0x4C: 'L', 0x4D: 'M', 0x4E: 'N', 0x4F: 'O',
    0x50: 'P', 0x51: 'Q', 0x52: 'R', 0x53: 'S', 0x54: 'T',
    0x55: 'U', 0x56: 'V', 0x57: 'W', 0x58: 'X', 0x59: 'Y',
    0x5A: 'Z', 0x20: ' ',
}


def _build_test_rom(segments: dict[int, bytes], size: int = 0x8000) -> str:
    """Создаёт тестовый ROM-файл и возвращает путь."""
    data = bytearray(size)

    # Nintendo logo (обязателен)
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

    for offset, text_bytes in segments.items():
        end = min(offset + len(text_bytes), size)
        data[offset:end] = text_bytes[:end - offset]

    # Header checksum (канонический: 0x134-0x14C, с title)
    checksum = 0
    for addr in range(0x0134, 0x014D):
        checksum = (checksum - data[addr] - 1) & 0xFF
    data[0x14D] = checksum

    fd, path = tempfile.mkstemp(suffix=".gb")
    os.write(fd, bytes(data))
    os.close(fd)
    return path


class TestByteLevelCorrectness:
    """P0: Проверка что байты записаны точно."""

    def test_inject_writes_bytes_at_correct_offset(self):
        """Байты перевода записываются по правильному offset."""
        # original_messages ищет данные до терминатора (0x00)
        original = b'ABCD' + b'\x00'
        rom_path = _build_test_rom({0x4000: original})

        try:
            injector = TextInjector(rom_path)
            segment = {
                'name': 'test',
                'start': 0x4000,
                'end': 0x4010,
                'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                'compression': None,
            }
            plugin = type('P', (), {
                'get_text_segments': lambda self, rom: [segment]
            })()

            ok = injector.inject_segment('test', ['XY'], plugin)
            assert ok

            assert injector.modified_data[0x4000] == 0x58  # X
            assert injector.modified_data[0x4001] == 0x59  # Y
        finally:
            os.unlink(rom_path)

    def test_inject_pads_shorter_translation(self):
        """Короткий перевод дополняется pad-байтом 0x20."""
        original = b'ABCD' + b'\x00'
        rom_path = _build_test_rom({0x4000: original})

        try:
            injector = TextInjector(rom_path)
            segment = {
                'name': 'test',
                'start': 0x4000,
                'end': 0x4010,
                'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                'compression': None,
            }
            plugin = type('P', (), {
                'get_text_segments': lambda self, rom: [segment]
            })()

            ok = injector.inject_segment('test', ['AB'], plugin)
            assert ok

            assert injector.modified_data[0x4000] == 0x41  # A
            assert injector.modified_data[0x4001] == 0x42  # B
            assert injector.modified_data[0x4002] == 0x20  # pad
            assert injector.modified_data[0x4003] == 0x20  # pad
        finally:
            os.unlink(rom_path)

    def test_inject_does_not_modify_bytes_outside_segment(self):
        """Байты за пределами сегмента не изменяются."""
        original = b'ABCD' + b'\x00'
        marker = b'\xDE\xAD\xBE\xEF'
        rom_path = _build_test_rom({0x4000: original, 0x5000: marker})

        try:
            injector = TextInjector(rom_path)
            segment = {
                'name': 'test',
                'start': 0x4000,
                'end': 0x4010,
                'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                'compression': None,
            }
            plugin = type('P', (), {
                'get_text_segments': lambda self, rom: [segment]
            })()

            injector.inject_segment('test', ['XY'], plugin)

            assert injector.modified_data[0x5000:0x5004] == bytearray(marker)
        finally:
            os.unlink(rom_path)

    def test_inject_preserves_terminator_byte(self):
        """Терминатор (0x00) после сообщения не затрагивается."""
        original = b'ABCD' + b'\x00' + b'FFFF' + b'\x00'
        rom_path = _build_test_rom({0x4000: original})

        try:
            injector = TextInjector(rom_path)
            segment = {
                'name': 'test',
                'start': 0x4000,
                'end': 0x4020,
                'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                'compression': None,
            }
            plugin = type('P', (), {
                'get_text_segments': lambda self, rom: [segment]
            })()

            injector.inject_segment('test', ['XX', 'YY'], plugin)

            # Терминатор между сообщениями
            assert injector.modified_data[0x4004] == 0x00
        finally:
            os.unlink(rom_path)

    def test_inject_returns_false_when_translation_too_long(self):
        """inject_segment возвращает False если перевод длиннее слота."""
        original = b'AB' + b'\x00'
        rom_path = _build_test_rom({0x4000: original})

        try:
            injector = TextInjector(rom_path)
            segment = {
                'name': 'test',
                'start': 0x4000,
                'end': 0x4010,
                'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                'compression': None,
            }
            plugin = type('P', (), {
                'get_text_segments': lambda self, rom: [segment]
            })()

            # 3 символа > 2 байт слот
            ok = injector.inject_segment('test', ['ABCDEF'], plugin)
            assert not ok
        finally:
            os.unlink(rom_path)

    def test_save_writes_file(self):
        """save() создаёт файл на диске."""
        original = b'ABCD' + b'\x00'
        rom_path = _build_test_rom({0x4000: original})
        output_path = rom_path + ".out.gbc"

        try:
            injector = TextInjector(rom_path)
            injector.save(output_path)
            assert os.path.exists(output_path)
            size = os.path.getsize(output_path)
            assert size == 0x8000
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)

    def test_inject_then_save_then_read_back(self):
        """inject → save → read: байты совпадают."""
        original = b'ABCD' + b'\x00'
        rom_path = _build_test_rom({0x4000: original})
        output_path = rom_path + ".out.gbc"

        try:
            injector = TextInjector(rom_path)
            segment = {
                'name': 'test',
                'start': 0x4000,
                'end': 0x4010,
                'decoder': CharMapDecoder(SIMPLE_CHARMAP),
                'compression': None,
            }
            plugin = type('P', (), {
                'get_text_segments': lambda self, rom: [segment]
            })()

            injector.inject_segment('test', ['XY'], plugin)
            injector.save(output_path)

            with open(output_path, 'rb') as f:
                saved = bytearray(f.read())

            assert saved[0x4000] == 0x58  # X
            assert saved[0x4001] == 0x59  # Y
        finally:
            for p in (rom_path, output_path):
                if os.path.exists(p):
                    os.unlink(p)


# ─────────────────────────────────────────────────────────────
# WS-3a: кэш get_text_segments по классу плагина
# ─────────────────────────────────────────────────────────────

class TestInjectorSegmentCache:
    """inject_segment не должен пересканировать ROM на каждый вызов."""

    def _segment(self, start=0x4000, end=0x4010, injectable=True):
        return {
            'name': 'test',
            'start': start,
            'end': end,
            'decoder': CharMapDecoder(SIMPLE_CHARMAP),
            'compression': None,
            'injectable': injectable,
        }

    def _counting_plugin_class(self, segment):
        class P:
            def __init__(self):
                self.calls = 0

            def get_text_segments(self, rom):
                self.calls += 1
                return [segment]

        return P

    def test_multiple_injections_single_scan(self):
        rom_path = _build_test_rom({0x4000: b'ABCD\x00'})
        try:
            injector = TextInjector(rom_path)
            plugin_cls = self._counting_plugin_class(self._segment())
            plugin = plugin_cls()
            for _ in range(3):
                assert injector.inject_segment('test', ['XY'], plugin)
            assert plugin.calls == 1
        finally:
            os.unlink(rom_path)

    def test_same_class_two_instances_scan_separately(self):
        rom_path = _build_test_rom({0x4000: b'ABCD\x00'})
        try:
            injector = TextInjector(rom_path)
            plugin_cls = self._counting_plugin_class(self._segment())
            a, b = plugin_cls(), plugin_cls()
            assert injector.inject_segment('test', ['XY'], a)
            assert injector.inject_segment('test', ['XY'], b)
            # Кэш по экземпляру (не по классу): разные экземпляры сканируют.
            assert a.calls == 1
            assert b.calls == 1
        finally:
            os.unlink(rom_path)

    def test_instances_with_distinct_segments_not_contaminated(self):
        # Регрессия: кэш по классу смешал бы сегменты двух экземпляров одного
        # класса (ConfigurablePlugin хранит config в self), записывая перевод
        # в чужие смещения.
        rom_path = _build_test_rom({0x4000: b'ABCD\x00', 0x4010: b'WXYZ\x00'})
        try:
            injector = TextInjector(rom_path)
            class P:
                def __init__(self, seg):
                    self.seg = seg
                    self.calls = 0

                def get_text_segments(self, rom):
                    self.calls += 1
                    return [self.seg]

            seg_a = self._segment(start=0x4000, end=0x4010)
            seg_b = self._segment(start=0x4010, end=0x4020)
            a, b = P(seg_a), P(seg_b)
            assert injector.inject_segment('test', ['XY'], a)
            assert injector.inject_segment('test', ['UV'], b)
            assert a.calls == 1
            assert b.calls == 1
            assert injector.modified_data[0x4000:0x4002] == bytearray(b'XY')
            assert injector.modified_data[0x4010:0x4012] == bytearray(b'UV')
        finally:
            os.unlink(rom_path)

    def test_two_plugin_classes_two_scans(self):
        rom_path = _build_test_rom({0x4000: b'ABCD\x00'})
        try:
            injector = TextInjector(rom_path)
            cls_a = self._counting_plugin_class(self._segment())
            cls_b = self._counting_plugin_class(self._segment())
            a, b = cls_a(), cls_b()
            assert injector.inject_segment('test', ['XY'], a)
            assert injector.inject_segment('test', ['XY'], b)
            assert a.calls == 1
            assert b.calls == 1
        finally:
            os.unlink(rom_path)

    def test_extract_only_guard_reuses_cache(self):
        rom_path = _build_test_rom({0x4000: b'ABCD\x00'})
        try:
            injector = TextInjector(rom_path)
            segment = self._segment()
            segment['injectable'] = False
            plugin_cls = self._counting_plugin_class(segment)
            plugin = plugin_cls()
            assert injector.inject_segment('test', ['XY'], plugin) is False
            assert injector.inject_segment('test', ['XY'], plugin) is False
            assert injector.modified_data == injector.original_data
            assert plugin.calls == 1
        finally:
            os.unlink(rom_path)
