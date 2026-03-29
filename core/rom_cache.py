"""
Кэширование загруженных ROM файлов

Позволяет избежать повторной загрузки одного и того же ROM файла
при переключении между вкладками Extract и Edit.
"""

import logging
import os
from typing import Dict, Optional, Tuple
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.rom_cache')


class ROMCache:
    """
    Кэш для загруженных ROM файлов.
    
    Хранит загруженные ROM в памяти, проверяя хэш файла для определения
    необходимости перезагрузки.
    """
    
    def __init__(self, max_cache_size: int = 3):
        """
        Инициализация кэша.
        
        Args:
            max_cache_size: Максимальное количество ROM в кэше
        """
        self._cache: Dict[str, Tuple[GameBoyROM, str, float]] = {}
        self._max_cache_size = max_cache_size
        logger.info(f"Инициализирован ROMCache с лимитом {max_cache_size} файлов")
    
    def _get_file_hash(self, path: str) -> str:
        """Получает хэш файла (mtime + size) для проверки изменений"""
        stat = os.stat(path)
        return f"{stat.st_mtime}:{stat.st_size}"
    
    def get(self, path: str) -> Optional[GameBoyROM]:
        """
        Получает ROM из кэша, если файл не изменился.
        
        Args:
            path: Путь к ROM файлу
            
        Returns:
            Объект GameBoyROM из кэша или None, если нужно перезагрузить
        """
        if path not in self._cache:
            logger.debug(f"ROM '{path}' не в кэше")
            return None
        
        rom, old_hash, load_time = self._cache[path]
        
        # Проверяем, изменился ли файл
        try:
            new_hash = self._get_file_hash(path)
            if new_hash != old_hash:
                logger.info(f"ROM '{path}' изменился, требуется перезагрузка")
                del self._cache[path]
                return None
        except OSError as e:
            logger.warning(f"Не удалось проверить файл '{path}': {e}")
            del self._cache[path]
            return None
        
        logger.debug(f"ROM '{path}' получен из кэша (загружен {load_time:.1f}с назад)")
        return rom
    
    def put(self, path: str, rom: GameBoyROM) -> None:
        """
        Сохраняет ROM в кэш.
        
        Args:
            path: Путь к ROM файлу
            rom: Загруженный объект GameBoyROM
        """
        # Очищаем кэш, если достигнут лимит
        if len(self._cache) >= self._max_cache_size:
            self._evict_oldest()
        
        file_hash = self._get_file_hash(path)
        import time
        self._cache[path] = (rom, file_hash, time.time())
        logger.info(f"ROM '{path}' сохранён в кэш")
    
    def _evict_oldest(self) -> None:
        """Удаляет самый старый элемент из кэша"""
        if not self._cache:
            return
        
        # Находим самый старый по времени загрузки
        oldest_path = None
        oldest_time = float('inf')
        
        for path, (_, _, load_time) in self._cache.items():
            if load_time < oldest_time:
                oldest_time = load_time
                oldest_path = path
        
        if oldest_path:
            del self._cache[oldest_path]
            logger.debug(f"Удалён старый ROM из кэша: '{oldest_path}'")
    
    def invalidate(self, path: str) -> None:
        """
        Удаляет конкретный ROM из кэша.
        
        Args:
            path: Путь к ROM файлу
        """
        if path in self._cache:
            del self._cache[path]
            logger.info(f"ROM '{path}' удалён из кэша")
    
    def clear(self) -> None:
        """Очищает весь кэш"""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Кэш очищен ({count} файлов)")
    
    def get_stats(self) -> Dict[str, int]:
        """Возвращает статистику кэша"""
        return {
            'cached_roms': len(self._cache),
            'max_size': self._max_cache_size
        }


# Глобальный экземпляр кэша
_global_cache: Optional[ROMCache] = None


def get_rom_cache() -> ROMCache:
    """Возвращает глобальный экземпляр кэша"""
    global _global_cache
    if _global_cache is None:
        _global_cache = ROMCache()
    return _global_cache


def load_rom_cached(path: str) -> GameBoyROM:
    """
    Загружает ROM с использованием кэша.
    
    Args:
        path: Путь к ROM файлу
        
    Returns:
        Объект GameBoyROM
    """
    cache = get_rom_cache()
    
    # Пробуем получить из кэша
    rom = cache.get(path)
    if rom is not None:
        return rom
    
    # Загружаем заново
    logger.info(f"Загрузка ROM '{path}' (без кэша)")
    rom = GameBoyROM(path)
    
    # Сохраняем в кэш
    cache.put(path, rom)
    
    return rom
