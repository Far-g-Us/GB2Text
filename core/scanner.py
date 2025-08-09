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
Модуль для поиска текстовых сегментов и указателей
"""

from collections import Counter
from typing import List, Dict, Tuple


def auto_detect_charmap(rom_data: bytes, start: int = 0, length: int = 1000) -> Dict[int, str]:
    """
    Автоматическое определение возможной таблицы символов.
    Пользователь должен проверить и скорректировать результат.
    """
    # Анализ статистики использования байтов
    freq = Counter()
    for i in range(start, min(start + length, len(rom_data))):
        byte = rom_data[i]
        freq[byte] += 1

    # Определение вероятных пробелов и терминаторов
    common_bytes = freq.most_common()

    charmap = {}
    # Предполагаем, что самый частый символ - пробел
    if common_bytes:
        charmap[common_bytes[0][0]] = ' '

    # Добавляем ASCII символы для известных диапазонов
    for byte in range(0x20, 0x7F):
        if byte in rom_data[start:start + length]:
            charmap[byte] = chr(byte)

    # Добавляем терминаторы
    for byte, count in common_bytes[:5]:
        if count > 10:  # Порог для терминатора
            if byte not in charmap:
                charmap[byte] = f'[TERM_{byte:02X}]'

    return charmap


def find_text_pointers(rom_data: bytes, min_length: int = 4) -> List[Tuple[int, int]]:
    """
    Поиск указателей на текст в ROM
    Возвращает список кортежей (адрес, адрес_текста)
    """
    pointers = []
    # Простой паттерн для поиска указателей (адреса в ROM)
    for i in range(0, len(rom_data) - 3, 4):
        # Проверяем, является ли значение возможным адресом
        addr = int.from_bytes(rom_data[i:i + 4], byteorder='little')
        if 0x4000 <= addr < len(rom_data) and addr % 4 == 0:
            # Проверяем, похож ли текст по адресу на текст
            if is_text_like(rom_data, addr, min_length):
                pointers.append((i, addr))
    return pointers


def is_text_like(rom_data: bytes, start: int, min_length: int) -> bool:
    """
    Проверяет, похож ли участок данных на текст
    """
    if start + min_length > len(rom_data):
        return False

    # Подсчитываем процент "читаемых" символов
    printable = 0
    for i in range(min_length):
        byte = rom_data[start + i]
        # ASCII символы и распространенные терминаторы
        if 0x20 <= byte <= 0x7E or byte in [0x00, 0x0A, 0x0D, 0xFF]:
            printable += 1

    return printable / min_length > 0.7  # 70% символов должны быть "читаемыми"


def auto_detect_segments(rom_data: bytes, min_segment_length: int = 100) -> List[Dict]:
    """
    Автоматическое определение текстовых сегментов
    """
    segments = []

    # Ищем области с высокой плотностью "читаемых" символов
    in_segment = False
    segment_start = 0

    for i in range(0, len(rom_data), 16):
        if is_text_like(rom_data, i, 16):
            if not in_segment:
                in_segment = True
                segment_start = i
        else:
            if in_segment and (i - segment_start) > min_segment_length:
                segments.append({
                    'name': f'auto_segment_{len(segments)}',
                    'start': segment_start,
                    'end': i
                })
                in_segment = False

    # Проверяем последний сегмент
    if in_segment and (len(rom_data) - segment_start) > min_segment_length:
        segments.append({
            'name': f'auto_segment_{len(segments)}',
            'start': segment_start,
            'end': len(rom_data)
        })

    return segments