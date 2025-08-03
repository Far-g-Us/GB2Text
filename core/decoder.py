"""
Модуль для декодирования текста и обработки сжатия
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple


class CompressionHandler(ABC):
    """Базовый класс для обработчиков сжатия"""

    @abstractmethod
    def decompress(self, data: bytes, start: int) -> Tuple[bytes, int]:
        pass


class LZ77Handler(CompressionHandler):
    def decompress(self, data: bytes, start: int) -> Tuple[bytes, int]:
        # Простая реализация LZ77 (требует улучшения)
        output = []
        i = start
        while i < len(data):
            flags = data[i]
            i += 1
            for j in range(8):
                if i >= len(data):
                    break
                if flags & (1 << (7 - j)):
                    # Ссылка
                    b1 = data[i]
                    b2 = data[i + 1]
                    i += 2
                    dist = ((b1 & 0xF) << 8) | b2
                    length = (b1 >> 4) + 3
                    pos = len(output) - dist
                    for k in range(length):
                        output.append(output[pos + k])
                else:
                    # Литерал
                    output.append(data[i])
                    i += 1
        return bytes(output), i


class TextDecoder(ABC):
    """Базовый класс для декодеров текста"""

    @abstractmethod
    def decode(self, data: bytes, start: int, end: int) -> str:
        pass


class CharMapDecoder(TextDecoder):
    def __init__(self, charmap: Dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, end: int) -> str:
        result = []
        i = start
        while i < end and i < len(data):
            byte = data[i]
            if byte in self.charmap:
                result.append(self.charmap[byte])
            else:
                result.append(f'[{byte:02X}]')
            i += 1
        return ''.join(result)