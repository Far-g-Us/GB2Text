"""
GB Text Extraction Framework

ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ:
Этот программный инструмент предназначен ТОЛЬКО для анализа ROM-файлов,
законно принадлежащих пользователю. Использование этого инструмента для
нелегального копирования, распространения или модификации защищенных
авторским правом материалов строго запрещено.

Этот проект НЕ содержит и НЕ распространяет никакие ROM-файлы или
защищенные авторским правом материалы. Все ROM-файлы должны быть
законно приобретены пользователем самостоятельно.

Этот инструмент разработан исключительно для исследовательских целей,
обучения и реверс-инжиниринга в рамках, разрешенных законодательством.
"""

"""
Модуль сжатия данных для GB/GBC/GBA ROM
"""

import logging
from typing import Tuple, Optional, List, Dict
from core.decoder import CompressionHandler


logger = logging.getLogger('gb2text.compression')


class LZSSHandler(CompressionHandler):
    """
    Обработчик LZSS сжатия.
    
    LZSS использует:
    - Флаговый байт (0x00 = литерал, 0xFF = ссылка)
    - Для ссылок: 2 байта (смещение, длина)
    """
    
    def decompress(self, data: bytes, start: int) -> Tuple[bytes, int]:
        """Распаковывает LZSS данные"""
        if start >= len(data):
            return b"", 0
            
        logger.debug(f"Начало распаковки LZSS с адреса 0x{start:X}")
        
        out = bytearray()
        i = start
        
        # Проверяем, начинается ли блок с заголовка
        # LZSS обычно не имеет заголовка, данные идут сразу
        
        while i < len(data) and len(out) < 1024 * 64:  # Макс 64KB
            if i >= len(data):
                break
                
            flags = data[i]
            i += 1
            
            for bit in range(8):
                if i >= len(data):
                    break
                    
                if (flags >> (7 - bit)) & 1:
                    # Ссылка (compressed)
                    if i + 1 >= len(data):
                        break
                    offset = data[i]
                    length = data[i + 1]
                    i += 2
                    
                    # LZSS encoding: length = count + 2
                    length = (length & 0x0F) + 2
                    
                    if offset < len(out):
                        for _ in range(length):
                            if offset < len(out):
                                out.append(out[len(out) - offset - 1])
                            else:
                                break
                else:
                    # Литерал
                    out.append(data[i])
                    i += 1
        
        consumed = i - start
        logger.debug(f"LZSS распаковано: {len(out)} байт, использовано: {consumed}")
        return bytes(out), consumed


class RLEHandler(CompressionHandler):
    """
    Обработчик RLE (Run-Length Encoding) сжатия.
    
    Формат:
    - 0x00 + байт + количество - повторить байт N раз
    - или просто последовательность байтов без сжатия
    """
    
    def decompress(self, data: bytes, start: int) -> Tuple[bytes, int]:
        """Распаковывает RLE данные"""
        if start >= len(data):
            return b"", 0
            
        logger.debug(f"Начало распаковки RLE с адреса 0x{start:X}")
        
        out = bytearray()
        i = start
        
        while i < len(data) and len(out) < 1024 * 64:
            byte = data[i]
            
            # Проверяем RLE паттерн
            if byte == 0x00 and i + 2 < len(data):
                # Специальный маркер RLE
                repeat_byte = data[i + 1]
                count = data[i + 2]
                
                if count > 0:
                    out.extend([repeat_byte] * count)
                    i += 3
                    continue
            
            # Обычный байт - копируем как есть
            out.append(byte)
            i += 1
        
        consumed = i - start
        logger.debug(f"RLE распаковано: {len(out)} байт, использовано: {consumed}")
        return bytes(out), consumed


class AutoDetectCompressionHandler(CompressionHandler):
    """
    Автоматическое определение типа сжатия и распаковка.
    
    Поддерживаемые типы:
    - GBA LZ77 (тип 0x10)
    - LZSS
    - RLE
    - Без сжатия
    """
    
    # Карта сигнатур для определения типа сжатия
    SIGNATURES = {
        'gba_lz77': [0x10],      # GBA LZ77
        'lzss': [],               # Без четкой сигнатуры
        'rle': [],               # Без четкой сигнатуры
    }
    
    def __init__(self):
        self.handlers: Dict[str, CompressionHandler] = {
            'gba_lz77': GBALZ77Handler(),
            'lzss': LZSSHandler(),
            'rle': RLEHandler(),
        }
    
    def decompress(self, data: bytes, start: int) -> Tuple[bytes, int]:
        """Автоматически определяет тип сжатия и распаковывает"""
        if start >= len(data):
            return b"", 0
        
        compression_type = self.detect_compression(data, start)
        logger.info(f"Определен тип сжатия: {compression_type}")
        
        if compression_type == 'none':
            # Без сжатия - возвращаем как есть
            return data[start:], len(data) - start
        
        handler = self.handlers.get(compression_type)
        if handler:
            return handler.decompress(data, start)
        
        # Неизвестный тип - возвращаем как есть
        logger.warning(f"Неизвестный тип сжатия, возвращаю данные без распаковки")
        return data[start:], len(data) - start
    
    def detect_compression(self, data: bytes, start: int) -> str:
        """Определяет тип сжатия по сигнатуре"""
        if start >= len(data):
            return 'none'
        
        first_byte = data[start]
        
        # GBA LZ77 (тип 0x10)
        if first_byte == 0x10:
            return 'gba_lz77'
        
        # Пробуем распознать по косвенным признакам
        # Это упрощенная логика - можно улучшить
        
        # Проверяем на LZSS
        if self._is_likely_lzss(data, start):
            return 'lzss'
        
        # Проверяем на RLE
        if self._is_likely_rle(data, start):
            return 'rle'
        
        return 'none'
    
    def _is_likely_lzss(self, data: bytes, start: int) -> bool:
        """Проверяет, похоже ли данные на LZSS"""
        if start + 4 > len(data):
            return False
        
        # LZSS обычно имеет много повторяющихся паттернов
        # Проверяем на наличие флаговых байтов
        consecutive_zeros = 0
        consecutive_ff = 0
        
        for i in range(start, min(start + 16, len(data))):
            if data[i] == 0x00:
                consecutive_zeros += 1
            elif data[i] == 0xFF:
                consecutive_ff += 1
        
        return consecutive_zeros >= 3 or consecutive_ff >= 3
    
    def _is_likely_rle(self, data: bytes, start: int) -> bool:
        """Проверяет, похоже ли данные на RLE"""
        if start + 3 > len(data):
            return False
        
        # RLE часто содержит маркеры 0x00 + байт + счетчик
        rle_markers = 0
        for i in range(start, min(start + 16, len(data) - 2)):
            if data[i] == 0x00 and data[i + 2] > 1:
                rle_markers += 1
        
        return rle_markers >= 2


# Импорт GBA обработчика для совместимости
from core.gba_support import GBALZ77Handler


def get_compression_handler(compression_type: str) -> Optional[CompressionHandler]:
    """
    Возвращает обработчик сжатия по типу.
    
    Args:
        compression_type: тип сжатия ('gba_lz77', 'lzss', 'rle', 'auto')
    
    Returns:
        Обработчик сжатия или None
    """
    handlers = {
        'gba_lz77': GBALZ77Handler(),
        'lzss': LZSSHandler(),
        'rle': RLEHandler(),
        'auto': AutoDetectCompressionHandler(),
    }
    return handlers.get(compression_type)


# Константы типов сжатия
COMPRESSION_TYPES = {
    'NONE': 'none',
    'GBA_LZ77': 'gba_lz77',
    'LZSS': 'lzss',
    'RLE': 'rle',
    'AUTO': 'auto',
}
