"""
Поддержка Game Boy Advance ROM
"""

from core.rom import GameBoyROM
from core.decoder import CharMapDecoder


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