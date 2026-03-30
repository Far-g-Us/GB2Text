"""
Edge-case тесты для GUI компонентов GB2Text
Тестирует граничные условия, ошибки и нестандартные сценарии
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock


class TestROMValidationEdgeCases:
    """Edge-case тесты для валидации ROM"""

    def test_validate_rom_nonexistent_file(self):
        """Тест валидации несуществующего файла"""
        from core.rom import validate_rom_file
        
        result = validate_rom_file("/nonexistent/rom.gb")
        # Функция может возвращать False или строку с ошибкой
        assert result is False or isinstance(result, str)

    def test_validate_rom_too_small(self):
        """Тест валидации слишком маленького файла"""
        from core.rom import validate_rom_file
        
        with tempfile.NamedTemporaryFile(suffix='.gb', delete=False) as f:
            f.write(b'x' * 1024)  # 1KB - слишком мало
            temp_path = f.name
        
        try:
            result = validate_rom_file(temp_path)
            # Функция может возвращать False или строку с ошибкой
            assert result is False or isinstance(result, str)
        finally:
            os.unlink(temp_path)

    def test_validate_rom_too_large(self):
        """Тест валидации слишком большого файла"""
        from core.rom import validate_rom_file
        
        with tempfile.NamedTemporaryFile(suffix='.gb', delete=False) as f:
            # 100MB - слишком большой
            f.write(b'x' * (100 * 1024 * 1024))
            temp_path = f.name
        
        try:
            result = validate_rom_file(temp_path)
            # Функция может возвращать False или строку с ошибкой
            assert result is False or isinstance(result, str)
        finally:
            os.unlink(temp_path)

    def test_validate_rom_invalid_extension(self):
        """Тест валидации с некорректным расширением"""
        from core.rom import validate_rom_file
        
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'x' * 0x8000)
            temp_path = f.name
        
        try:
            result = validate_rom_file(temp_path)
            # Функция может возвращать False или строку с ошибкой
            assert result is False or isinstance(result, str)
        finally:
            os.unlink(temp_path)


class TestPluginManagerEdgeCases:
    """Edge-case тесты для PluginManager"""

    def test_plugin_manager_with_nonexistent_dir(self):
        """Тест с несуществующей директорией"""
        from core.plugin_manager import PluginManager
        
        # Не должно вызвать ошибку
        pm = PluginManager(plugins_dir="/nonexistent/plugins")
        
        assert pm.plugins_dir is not None

    def test_plugin_manager_empty_plugins_list(self):
        """Тест с пустым списком плагинов"""
        from core.plugin_manager import PluginManager
        
        pm = PluginManager()
        
        # Должен быть хотя бы один встроенный плагин
        assert len(pm.plugins) > 0


class TestROMCacheEdgeCases:
    """Edge-case тесты для ROMCache"""

    def test_cache_get_nonexistent(self):
        """Тест получения несуществующего из кэша"""
        from core.rom_cache import ROMCache
        
        cache = ROMCache()
        
        result = cache.get("/nonexistent/rom.gb")
        assert result is None

    def test_cache_with_file_deleted(self):
        """Тест с удалённым файлом"""
        from core.rom_cache import ROMCache
        from core.rom import GameBoyROM
        
        cache = ROMCache()
        
        # Создаём временный ROM
        with tempfile.NamedTemporaryFile(suffix='.gb', delete=False) as f:
            f.write(b'NTEJ' + b'\x00' * (0x8000 - 4))
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            cache.put(temp_path, rom)
            
            # Удаляем файл
            os.unlink(temp_path)
            
            # Кэш должен вернуть None
            result = cache.get(temp_path)
            assert result is None
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestGuideManagerEdgeCases:
    """Edge-case тесты для GuideManager"""

    def test_guide_manager_nonexistent_dir(self):
        """Тест с несуществующей директорией"""
        from core.guide import GuideManager
        
        gm = GuideManager(guides_dir="/nonexistent/guides")
        
        result = gm.get_guide("test_game")
        assert result is None

    def test_guide_get_nonexistent(self):
        """Тест получения несуществующего гайда"""
        from core.guide import GuideManager
        
        gm = GuideManager()
        
        result = gm.get_guide("nonexistent_game_xyz")
        assert result is None


class TestI18nEdgeCases:
    """Edge-case тесты для i18n"""

    def test_i18n_t(self):
        """Тест базовой функции перевода"""
        from core.i18n import I18N
        
        i18n = I18N()
        
        # Проверяем что функция t существует и работает
        result = i18n.t("test_key")
        assert result is not None


class TestDecoderEdgeCases:
    """Edge-case тесты для декодера"""

    def test_decoder_empty_data(self):
        """Тест декодера с пустыми данными"""
        from core.decoder import CharMapDecoder
        
        charmap = {0x41: 'A', 0x00: ''}
        decoder = CharMapDecoder(charmap)
        
        result = decoder.decode(bytes([]), 0, 0)
        assert result == ""

    def test_decoder_none_charmap(self):
        """Тест декодера с None charmap"""
        from core.decoder import CharMapDecoder
        
        with pytest.raises((TypeError, AttributeError)):
            decoder = CharMapDecoder(None)


class TestScannerEdgeCases:
    """Edge-case тесты для сканера"""

    def test_scanner_empty_data(self):
        """Тест сканера с пустыми данными"""
        from core.scanner import auto_detect_segments
        
        result = auto_detect_segments(bytes([]))
        assert result is not None

    def test_scanner_small_data(self):
        """Тест сканера с маленькими данными"""
        from core.scanner import auto_detect_segments
        
        result = auto_detect_segments(bytes(100))
        assert result is not None


class TestTMXEdgeCases:
    """Edge-case тесты для TMX"""

    def test_tmx_empty_segments(self):
        """Тест TMX с пустыми сегментами"""
        from core.tmx import TMXHandler
        
        handler = TMXHandler()
        
        result = handler.export_tmx({}, 'en', 'ru', 'Test')
        assert '<?xml' in result

    def test_tmx_empty_text(self):
        """Тест TMX с пустым текстом"""
        from core.tmx import TMXHandler
        
        handler = TMXHandler()
        
        result = handler.export_tmx(
            {'seg': [{'text': ''}]},
            'en', 'ru', 'Test'
        )
        assert '<?xml' in result


class TestDatabaseEdgeCases:
    """Edge-case тесты для базы данных переводов"""

    def test_database_empty_init(self):
        """Тест пустой инициализации базы данных"""
        from core.database import TranslationDatabase
        
        db = TranslationDatabase()
        
        # Должна иметь базовые методы
        assert hasattr(db, 'store_translation')
        assert hasattr(db, 'get_translation')


class TestCompressionEdgeCases:
    """Edge-case тесты для сжатия"""

    def test_compression_empty_data(self):
        """Тест с пустыми данными"""
        from core.compression import AutoDetectCompressionHandler
        
        handler = AutoDetectCompressionHandler()
        
        result = handler.decompress(bytes([]), 0)
        # Не должно вызвать критическую ошибку
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])