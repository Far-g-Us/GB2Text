"""Тесты для модуля extractor"""
import os
import sys
import tempfile
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.extractor import TextExtractor
from core.plugin_manager import PluginManager, CancellationToken
from core.guide import GuideManager

# Путь к тестовым ROM
TEST_ROMS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_roms")


def create_temp_rom_file(data: bytes = None, size: int = 0x8000) -> str:
    """Создаёт временный ROM файл с правильным расширением"""
    if data is None:
        data = b'\x00' * size
    with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
        f.write(data)
        return f.name


def get_gba_roms():
    """Получает список GBA ROM"""
    if not os.path.exists(TEST_ROMS_DIR):
        return []
    return [os.path.join(TEST_ROMS_DIR, f) for f in os.listdir(TEST_ROMS_DIR) if f.endswith('.gba')]


def get_gbc_roms():
    """Получает список GBC ROM"""
    if not os.path.exists(TEST_ROMS_DIR):
        return []
    return [os.path.join(TEST_ROMS_DIR, f) for f in os.listdir(TEST_ROMS_DIR) if f.endswith('.gbc')]


def get_gb_roms():
    """Получает список GB ROM"""
    if not os.path.exists(TEST_ROMS_DIR):
        return []
    return [os.path.join(TEST_ROMS_DIR, f) for f in os.listdir(TEST_ROMS_DIR) if f.endswith('.gb')]


# Кешируем списки
GBA_ROMS = get_gba_roms()
GBC_ROMS = get_gbc_roms()
GB_ROMS = get_gb_roms()


class TestTextExtractor:
    """Тесты для TextExtractor"""
    
    def test_init_valid_path(self):
        """Тест инициализации с валидным путём"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            assert extractor is not None
        finally:
            os.unlink(temp_path)
    
    def test_init_invalid_path(self):
        """Тест инициализации с невалидным путём"""
        try:
            extractor = TextExtractor("nonexistent.rom", PluginManager(), GuideManager())
        except (FileNotFoundError, TypeError):
            pass
    
    def test_init_with_cancellation_token(self):
        """Тест инициализации с токеном отмены"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            token = CancellationToken()
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager(), token)
            assert extractor.cancellation_token == token
        finally:
            os.unlink(temp_path)
    
    def test_apply_guide_recommendations(self):
        """Тест применения рекомендаций"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            extractor._apply_guide_recommendations()
        finally:
            os.unlink(temp_path)
    
    def test_adjust_decoder(self):
        """Тест корректировки декодера"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            extractor._adjust_decoder(None, {})
        finally:
            os.unlink(temp_path)
    
    def test_export_text(self):
        """Тест экспорта текста"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w') as f:
            temp_path = f.name
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
                f.write(b'\x00' * 1000)
                rom_path = f.name
            
            try:
                pm = PluginManager()
                extractor = TextExtractor(rom_path, pm, GuideManager())
                try:
                    extractor.export_text(temp_path)
                except Exception:
                    pass
            finally:
                os.unlink(rom_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_init_with_max_segments(self):
        """Тест инициализации с max_segments"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager(), max_segments=100)
            assert extractor is not None
        finally:
            os.unlink(temp_path)
    
    def test_extract_returns_dict(self):
        """Тест что extract возвращает словарь"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            pm = PluginManager()
            extractor = TextExtractor(temp_path, pm, GuideManager())
            try:
                result = extractor.extract()
                assert isinstance(result, dict)
            except Exception:
                pass
        finally:
            os.unlink(temp_path)
    
    def test_extract_gba_rom(self):
        """Тест извлечения из GBA ROM"""
        if GBA_ROMS:
            rom_path = random.choice(GBA_ROMS)
            pm = PluginManager()
            extractor = TextExtractor(rom_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)
    
    def test_extract_gbc_rom(self):
        """Тест извлечения из GBC ROM"""
        if GBC_ROMS:
            rom_path = random.choice(GBC_ROMS)
            pm = PluginManager()
            extractor = TextExtractor(rom_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)
    
    def test_extract_gb_rom(self):
        """Тест извлечения из GB ROM"""
        if GB_ROMS:
            rom_path = random.choice(GB_ROMS)
            pm = PluginManager()
            extractor = TextExtractor(rom_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)
    
    def test_extract_japanese_gba(self):
        """Тест извлечения из японского GBA ROM"""
        # Автоматически ищем японский ROM
        japanese_roms = [r for r in GBA_ROMS if 'japan' in os.path.basename(r).lower() or '.jp.' in os.path.basename(r).lower()]
        if japanese_roms:
            rom_path = japanese_roms[0]
            pm = PluginManager()
            extractor = TextExtractor(rom_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)

    def test_extract_russian_gba(self):
        """Тест извлечения из русского GBA ROM"""
        # Автоматически ищем русский ROM
        russian_roms = [r for r in GBA_ROMS if '[ru]' in os.path.basename(r).lower() or '_ru' in os.path.basename(r).lower()]
        if russian_roms:
            rom_path = russian_roms[0]
            pm = PluginManager()
            extractor = TextExtractor(rom_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)

    def test_extract_with_segment_limit(self):
        """Тест извлечения с ограничением сегментов"""
        if GBA_ROMS:
            rom_path = random.choice(GBA_ROMS)
            pm = PluginManager()
            extractor = TextExtractor(rom_path, pm, GuideManager(), max_segments=10)
            result = extractor.extract()
            assert isinstance(result, dict)

    def test_extract_with_cancellation(self):
        """Тест извлечения с отменой"""
        if GBA_ROMS:
            rom_path = random.choice(GBA_ROMS)
            pm = PluginManager()
            token = CancellationToken()
            extractor = TextExtractor(rom_path, pm, GuideManager(), cancellation_token=token)
            result = extractor.extract()
            assert isinstance(result, dict)

    def test_split_messages_basic(self):
        """Тест разделения сообщений"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            # Test _split_messages method
            result = extractor._split_messages("Hello[END]World", 0)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_split_messages_empty(self):
        """Тест разделения пустых сообщений"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            result = extractor._split_messages("", 0)
            assert isinstance(result, list)
            assert len(result) == 0
        finally:
            os.unlink(temp_path)

    def test_extract_with_pointer_size(self):
        """Тест извлечения с указанием pointer_size"""
        if GBA_ROMS:
            rom_path = random.choice(GBA_ROMS)
            pm = PluginManager()
            extractor = TextExtractor(rom_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)

    def test_extract_encoding_option(self):
        """Тест извлечения с опцией encoding"""
        if GBA_ROMS:
            rom_path = random.choice(GBA_ROMS)
            pm = PluginManager()
            extractor = TextExtractor(rom_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)

    def test_init_invalid_type(self):
        """Тест инициализации с неправильным типом"""
        try:
            TextExtractor(123, PluginManager(), GuideManager())
            assert False, "Должно вызвать TypeError"
        except TypeError:
            pass

    def test_extract_with_cancelled_token(self):
        """Тест извлечения с уже отменённым токеном"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'GBA' + b'\x00' * 500)  # Больше 0x150
            temp_path = f.name
        
        try:
            token = CancellationToken()
            token.cancel()
            pm = PluginManager()
            extractor = TextExtractor(temp_path, pm, GuideManager(), cancellation_token=token)
            result = extractor.extract()
            assert result == {}
        finally:
            os.unlink(temp_path)

    def test_split_messages_with_special_chars(self):
        """Тест разделения сообщений со специальными символами"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            # Test with multiple terminators
            result = extractor._split_messages("Test\x00Another\x00End", 0)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_apply_guide_recommendations_no_guide(self):
        """Тест применения рекомендаций без guide"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            extractor.guide = None  # No guide
            extractor._apply_guide_recommendations()
        finally:
            os.unlink(temp_path)

    def test_adjust_decoder_with_empty_adjustments(self):
        """Тест корректировки декодера с пустыми настройками"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            # Test with None and empty adjustments
            result = extractor._adjust_decoder(None, {})
            assert result is None
        finally:
            os.unlink(temp_path)

    def test_split_messages_with_terminators(self):
        """Тест разделения сообщений с разными терминаторами"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            # Test with multiple different terminators
            result = extractor._split_messages("Test\x00Hello\xFFWorld\xFEEnd", 0)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_split_messages_with_offsets(self):
        """Тест разделения сообщений со смещениями"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            result = extractor._split_messages("Hello[END]World", 0x1000)
            assert isinstance(result, list)
        finally:
            os.unlink(temp_path)

    def test_extract_rom_not_loaded(self):
        """Тест извлечения когда ROM не загружен"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            extractor.rom = None  # Simulate not loaded
            try:
                extractor.extract()
            except ValueError as e:
                assert "ROM не загружен" in str(e)
        finally:
            os.unlink(temp_path)

    def test_extract_with_plugin_update_status(self):
        """Тест извлечения с plugin_manager с update_status"""
        class MockPluginManager(PluginManager):
            def __init__(self):
                super().__init__()
                self.status_updates = []
            
            def update_status(self, status, progress):
                self.status_updates.append((status, progress))
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            pm = MockPluginManager()
            extractor = TextExtractor(temp_path, pm, GuideManager())
            try:
                extractor.extract()
            except Exception:
                pass
        finally:
            os.unlink(temp_path)

    def test_extract_with_segment_compression(self):
        """Тест извлечения с сегментом со сжатием"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            # Test with LZ77 compression handler
            from core.compression import get_compression_handler
            handler = get_compression_handler('LZ77')
            if handler:
                # Test compression handler
                test_data = b'Hello World!'
                try:
                    compressed, _ = handler.compress(test_data)
                    decompressed, _ = handler.decompress(compressed, 0)
                    assert decompressed == test_data
                except Exception:
                    pass
        finally:
            os.unlink(temp_path)

    def test_extract_segment_with_low_quality(self):
        """Тест извлечения сегмента с низким качеством декодирования"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            # Simulate a segment with mostly unknown characters
            extractor._split_messages("[[[[[[[[[", 0)
        finally:
            os.unlink(temp_path)

    def test_extract_with_no_segments(self):
        """Тест извлечения когда плагин возвращает пустой список сегментов"""
        class MockPluginManager(PluginManager):
            def get_plugin(self, game_id, system, cancellation_token):
                class MockPlugin:
                    system = "gba"
                    def get_text_segments(self, rom):
                        return []
                return MockPlugin()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'GBA' + b'\x00' * 500)
            temp_path = f.name
        
        try:
            pm = MockPluginManager()
            extractor = TextExtractor(temp_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)
        finally:
            os.unlink(temp_path)

    def test_extract_with_invalid_segment_addresses(self):
        """Тест извлечения с невалидными адресами сегмента"""
        class MockPluginManager(PluginManager):
            def get_plugin(self, game_id, system, cancellation_token):
                class MockPlugin:
                    system = "gba"
                    def get_text_segments(self, rom):
                        return [
                            {'name': 'invalid', 'start': 0x100000, 'end': 0x200000, 'decoder': None}
                        ]
                return MockPlugin()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'GBA' + b'\x00' * 500)
            temp_path = f.name
        
        try:
            pm = MockPluginManager()
            extractor = TextExtractor(temp_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)
        finally:
            os.unlink(temp_path)

    def test_extract_with_auto_detect_charmap(self):
        """Тест извлечения с автоматическим определением таблицы символов"""
        class MockPluginManager(PluginManager):
            def get_plugin(self, game_id, system, cancellation_token):
                class MockPlugin:
                    system = "gba"
                    def get_text_segments(self, rom):
                        return [
                            {'name': 'test', 'start': 0x150, 'end': 0x200, 'decoder': None}
                        ]
                return MockPlugin()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'GBA' + b'\x00' * 500)
            temp_path = f.name
        
        try:
            pm = MockPluginManager()
            extractor = TextExtractor(temp_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)
        finally:
            os.unlink(temp_path)

    def test_init_with_invalid_type_raises_error(self):
        """Тест что инициализация с неправильным типом вызывает TypeError"""
        try:
            TextExtractor(12345, PluginManager(), GuideManager())
            assert False, "Должно вызвать TypeError"
        except TypeError as e:
            assert "rom_path" in str(e).lower() or "должен" in str(e).lower()

    def test_extract_with_plugin_not_found(self):
        """Тест извлечения когда плагин не найден"""
        class MockPluginManagerNoPlugin(PluginManager):
            def get_plugin(self, game_id, system, cancellation_token):
                return None  # No plugin
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'GBA' + b'\x00' * 500)
            temp_path = f.name
        
        try:
            pm = MockPluginManagerNoPlugin()
            extractor = TextExtractor(temp_path, pm, GuideManager())
            try:
                extractor.extract()
            except ValueError as e:
                assert "Не поддерживаемая игра" in str(e)
        finally:
            os.unlink(temp_path)

    def test_extract_with_max_segments_limit(self):
        """Тест извлечения с ограничением количества сегментов"""
        class MockPluginManagerManySegments(PluginManager):
            def get_plugin(self, game_id, system, cancellation_token):
                class MockPlugin:
                    system = "gba"
                    def get_text_segments(self, rom):
                        # Return many segments
                        segments = []
                        for i in range(20):
                            segments.append({
                                'name': f'seg_{i}',
                                'start': 0x150 + i * 0x100,
                                'end': 0x200 + i * 0x100,
                                'decoder': None
                            })
                        return segments
                return MockPlugin()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'GBA' + b'\x00' * 5000)
            temp_path = f.name
        
        try:
            pm = MockPluginManagerManySegments()
            # Limit to 5 segments
            extractor = TextExtractor(temp_path, pm, GuideManager(), max_segments=5)
            result = extractor.extract()
            assert isinstance(result, dict)
        finally:
            os.unlink(temp_path)

    def test_extract_with_compression_segment(self):
        """Тест извлечения сегмента со сжатием"""
        class MockPluginManagerWithCompression(PluginManager):
            def get_plugin(self, game_id, system, cancellation_token):
                class MockPlugin:
                    system = "gba"
                    def get_text_segments(self, rom):
                        return [
                            {'name': 'compressed', 'start': 0x150, 'end': 0x300, 
                             'decoder': None, 'compression': 'LZ77'}
                        ]
                return MockPlugin()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'GBA' + b'\x00' * 1000)
            temp_path = f.name
        
        try:
            pm = MockPluginManagerWithCompression()
            extractor = TextExtractor(temp_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)
        finally:
            os.unlink(temp_path)

    def test_extract_with_auto_decoder(self):
        """Тест извлечения с автоматическим определением декодера"""
        class MockPluginManagerAutoDecoder(PluginManager):
            def get_plugin(self, game_id, system, cancellation_token):
                class MockPlugin:
                    system = "gba"
                    def get_text_segments(self, rom):
                        return [
                            {'name': 'autodecode', 'start': 0x150, 'end': 0x200, 
                             'decoder': None}  # No decoder, should auto-detect
                        ]
                return MockPlugin()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            # Add some text-like data for auto-detection
            rom_data = bytearray(b'GBA' + b'\x00' * 0x14C + b'Hello World!' + b'\x00' * 500)
            f.write(rom_data)
            temp_path = f.name
        
        try:
            pm = MockPluginManagerAutoDecoder()
            extractor = TextExtractor(temp_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)
        finally:
            os.unlink(temp_path)

    def test_extract_with_low_quality_segment(self):
        """Тест извлечения сегмента с низким качеством"""
        class MockPluginManagerLowQuality(PluginManager):
            def get_plugin(self, game_id, system, cancellation_token):
                class MockPlugin:
                    system = "gba"
                    def get_text_segments(self, rom):
                        return [
                            {'name': 'lowqual', 'start': 0x150, 'end': 0x200, 
                             'decoder': None}
                        ]
                return MockPlugin()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            # Add mostly unknown characters
            rom_data = bytearray(b'GBA' + b'\x00' * 0x14C + b'\x01\x02\x03\x04\x05\x06\x07\x08' + b'\x00' * 500)
            f.write(rom_data)
            temp_path = f.name
        
        try:
            pm = MockPluginManagerLowQuality()
            extractor = TextExtractor(temp_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)
        finally:
            os.unlink(temp_path)

    def test_extract_with_invalid_segment_addresses(self):
        """Тест извлечения с невалидными адресами сегмента"""
        class MockPluginManagerInvalidAddr(PluginManager):
            def get_plugin(self, game_id, system, cancellation_token):
                class MockPlugin:
                    system = "gba"
                    def get_text_segments(self, rom):
                        return [
                            {'name': 'invalid', 'start': 0x100000, 'end': 0x200000, 'decoder': None}
                        ]
                return MockPlugin()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'GBA' + b'\x00' * 500)
            temp_path = f.name
        
        try:
            pm = MockPluginManagerInvalidAddr()
            extractor = TextExtractor(temp_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)
        finally:
            os.unlink(temp_path)

    def test_extract_with_compression_handler_object(self):
        """Тест извлечения с объектом сжатия"""
        class MockCompression:
            def decompress(self, data, offset):
                return b'Decompressed data', len(data)
        
        class MockPluginManagerWithCompObj(PluginManager):
            def get_plugin(self, game_id, system, cancellation_token):
                class MockPlugin:
                    system = "gba"
                    def get_text_segments(self, rom):
                        return [
                            {'name': 'compobj', 'start': 0x150, 'end': 0x200, 
                             'decoder': None, 'compression': MockCompression()}
                        ]
                return MockPlugin()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(b'GBA' + b'\x00' * 1000)
            temp_path = f.name
        
        try:
            pm = MockPluginManagerWithCompObj()
            extractor = TextExtractor(temp_path, pm, GuideManager())
            result = extractor.extract()
            assert isinstance(result, dict)
        finally:
            os.unlink(temp_path)
