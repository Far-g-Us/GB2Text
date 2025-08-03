"""
Поддержка Game Boy Advance ROM
"""

from core.rom import GameBoyROM
from core.decoder import CompressionHandler
from typing import Tuple


class GBALZ77Handler(CompressionHandler):
    """Обработчик LZ77 сжатия для Pokemon игр на GBA"""

    def decompress(self, data: bytes, start: int) -> Tuple[bytes, int]:
        """
        Декомпрессия данных, сжатых с использованием LZ77 в Pokemon GBA игр.
        Формат LZ77 для GBA немного отличается от классического.
        """
        output = []
        i = start

        while i < len(data):
            flags = data[i]
            i += 1

            for j in range(8):
                if i >= len(data):
                    break

                if flags & (0x80 >> j):
                    # Ссылка
                    b1 = data[i]
                    b2 = data[i + 1]
                    i += 2

                    # В GBA формате смещение и длина закодированы иначе
                    dist = ((b1 & 0x0F) << 8) | b2
                    length = (b1 >> 4) + 3

                    # Корректировка для GBA
                    dist += 1

                    pos = len(output) - dist
                    for k in range(length):
                        if pos + k >= 0 and pos + k < len(output):
                            output.append(output[pos + k])
                else:
                    # Литерал
                    output.append(data[i])
                    i += 1

        return bytes(output), i


def analyze_gba_text_regions(rom: GameBoyROM) -> list:
    """Анализ GBA ROM для поиска текстовых регионов"""
    # GBA использует другие адреса и структуры
    text_regions = []

    # Стандартные области для GBA
    # Обычно текст находится в .text или .data секциях
    # Нужно искать последовательности ASCII-подобных символов

    for offset in range(0x08000000, len(rom.data), 0x1000):
        # Проверяем каждые 4KB
        region = rom.data[offset:offset + 0x1000]
        if is_potential_text_region(region):
            text_regions.append({
                'start': offset,
                'end': offset + 0x1000,
                'confidence': calculate_confidence(region)
            })

    return text_regions


def is_potential_text_region(data: bytes) -> bool:
    """Проверка, является ли регион потенциальным хранилищем текста"""
    printable_count = 0
    total = len(data)

    if total == 0:
        return False

    for b in data:
        if 0x20 <= b <= 0x7E or b in [0x0A, 0x0D]:  # ASCII printable + newlines
            printable_count += 1

    # Если более 30% символов - печатные, вероятно это текст
    return (printable_count / total) > 0.3


def calculate_confidence(data: bytes) -> float:
    """Расчет уверенности, что регион содержит текст"""
    # Более сложный анализ для определения уверенности
    # ...
    return 0.0