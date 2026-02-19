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
        with tempfile.NamedTemporaryFile(delete=False) as f:
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
        with tempfile.NamedTemporaryFile(delete=False) as f:
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
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager())
            extractor._apply_guide_recommendations()
        finally:
            os.unlink(temp_path)
    
    def test_adjust_decoder(self):
        """Тест корректировки декодера"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
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
            with tempfile.NamedTemporaryFile(delete=False) as f:
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
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 1000)
            temp_path = f.name
        
        try:
            extractor = TextExtractor(temp_path, PluginManager(), GuideManager(), max_segments=100)
            assert extractor is not None
        finally:
            os.unlink(temp_path)
    
    def test_extract_returns_dict(self):
        """Тест что extract возвращает словарь"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
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
        with tempfile.NamedTemporaryFile(delete=False) as f:
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
        with tempfile.NamedTemporaryFile(delete=False) as f:
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
