"""
Тесты для модуля кэширования ROM (core/rom_cache.py)
"""

import pytest
import tempfile
import os
import time
from core.rom_cache import ROMCache, get_rom_cache, load_rom_cached


class TestROMCache:
    """Тесты класса ROMCache"""
    
    @pytest.fixture
    def temp_rom(self):
        """Создаёт временный ROM файл для тестов"""
        with tempfile.NamedTemporaryFile(suffix='.gb', delete=False) as f:
            # Минимальный GB ROM (32KB)
            rom_data = bytearray(0x8000)
            # Добавляем сигнатуру GB
            rom_data[0x0100:0x0104] = b'\x00\x00\x00\x00'
            f.write(rom_data)
            temp_path = f.name
        
        yield temp_path
        
        # Очистка
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_cache_initialization(self):
        """Тест инициализации кэша"""
        cache = ROMCache(max_cache_size=2)
        assert cache._max_cache_size == 2
        assert len(cache._cache) == 0
    
    def test_cache_put_and_get(self, temp_rom):
        """Тест сохранения и получения из кэша"""
        cache = ROMCache()
        
        # Загружаем ROM
        from core.rom import GameBoyROM
        rom = GameBoyROM(temp_rom)
        
        # Сохраняем в кэш
        cache.put(temp_rom, rom)
        
        # Получаем из кэша
        cached_rom = cache.get(temp_rom)
        
        assert cached_rom is not None
        assert cached_rom.data == rom.data
    
    def test_cache_miss(self):
        """Тест промаха кэша"""
        cache = ROMCache()
        
        # Пробуем получить несуществующий ROM
        result = cache.get("/non/existent/rom.gb")
        
        assert result is None
    
    def test_cache_invalidate(self, temp_rom):
        """Тест удаления из кэша"""
        cache = ROMCache()
        
        from core.rom import GameBoyROM
        rom = GameBoyROM(temp_rom)
        cache.put(temp_rom, rom)
        
        # Инвалидируем
        cache.invalidate(temp_rom)
        
        # Проверяем, что ROM удалён
        assert cache.get(temp_rom) is None
    
    def test_cache_clear(self, temp_rom):
        """Тест очистки кэша"""
        cache = ROMCache()
        
        from core.rom import GameBoyROM
        rom = GameBoyROM(temp_rom)
        cache.put(temp_rom, rom)
        
        # Очищаем
        cache.clear()
        
        assert len(cache._cache) == 0
    
    def test_cache_max_size_eviction(self, temp_rom):
        """Тест вытеснения при достижении лимита"""
        # Создаём 3 временных файла
        temp_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix='.gb', delete=False) as f:
                rom_data = bytearray(0x8000)
                rom_data[0x0100] = i  # Уникальный байт
                f.write(rom_data)
                temp_files.append(f.name)
        
        try:
            cache = ROMCache(max_cache_size=2)
            
            # Загружаем 3 ROM
            from core.rom import GameBoyROM
            for path in temp_files:
                rom = GameBoyROM(path)
                cache.put(path, rom)
            
            # Должен остаться только 1 из 3 (самый старый удалён)
            assert len(cache._cache) == 2
            
        finally:
            for path in temp_files:
                if os.path.exists(path):
                    os.unlink(path)
    
    def test_cache_file_change_detection(self, temp_rom):
        """Тест определения изменения файла"""
        cache = ROMCache()
        
        from core.rom import GameBoyROM
        rom = GameBoyROM(temp_rom)
        cache.put(temp_rom, rom)
        
        # Модифицируем файл
        time.sleep(0.1)  # Нужно чтобы mtime изменился
        with open(temp_rom, 'r+b') as f:
            f.seek(0x100)
            f.write(b'\xFF')
        
        # При получении должен вернуться None (файл изменился)
        result = cache.get(temp_rom)
        
        # Кэш должен был автоматически очистить запись
        assert temp_rom not in cache._cache
    
    def test_global_cache(self, temp_rom):
        """Тест глобального кэша"""
        cache1 = get_rom_cache()
        cache2 = get_rom_cache()
        
        # Должен быть тот же самый экземпляр
        assert cache1 is cache2
    
    def test_load_rom_cached(self, temp_rom):
        """Тест функции load_rom_cached"""
        # Первая загрузка
        rom1 = load_rom_cached(temp_rom)
        
        # Вторая загрузка должна использовать кэш
        rom2 = load_rom_cached(temp_rom)
        
        # Должен быть тот же объект
        assert rom1 is rom2
    
    def test_get_stats(self, temp_rom):
        """Тест получения статистики"""
        cache = ROMCache(max_cache_size=5)
        
        stats = cache.get_stats()
        
        assert stats['cached_roms'] == 0
        assert stats['max_size'] == 5
