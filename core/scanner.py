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

import logging
from collections import Counter
from typing import List, Dict, Tuple

logger = logging.getLogger('gb2text.scanner')


def auto_detect_charmap(rom_data: bytes, start: int = 0, length: int = 1000) -> Dict[int, str]:
    """
    Улучшенное автоопределение таблицы символов с учетом языка и системы
    """
    logger = logging.getLogger('gb2text.scanner')
    logger.info(f"Автоопределение таблицы символов, начиная с 0x{start:X}, длина: {length}")

    # Проверяем, не является ли ROM GBA
    is_gba = len(rom_data) > 0xB2 and rom_data[0xA0:0xB2] == b'Nintendo Game Boy'

    # Анализ статистики использования байтов
    freq = Counter()
    for i in range(start, min(start + length, len(rom_data))):
        byte = rom_data[i]
        freq[byte] += 1

    # Определение вероятных пробелов и терминаторов
    common_bytes = freq.most_common()
    logger.debug(f"Частота использования байтов: {common_bytes[:10]}...")

    charmap = {}

    # Попробуем определить систему
    is_gbc = False
    if len(rom_data) > 0x143:
        cgb_flag = rom_data[0x143]
        new_licensee_code = (rom_data[0x144] << 8) | rom_data[0x145]
        is_gbc = cgb_flag in [0x80, 0xC0] or new_licensee_code == 0x33

    # Для GBA игр используем другой подход
    if is_gba:
        logger.info("Обнаружена игра для Game Boy Advance, используем специфичную таблицу символов")
        # Стандартные символы для GBA
        for i in range(0x20, 0x7F):
            charmap[i] = chr(i)

        # Добавляем распространенные японские символы
        charmap[0x80] = '。'
        charmap[0x81] = '、'
        charmap[0x82] = '・'
        charmap[0x83] = '゛'
        charmap[0x84] = '゜'
        charmap[0x85] = 'ー'
        charmap[0xFF] = '[END]'

        logger.debug(f"Создана GBA таблица символов с {len(charmap)} символами")
        return charmap

    # Для GBC игр с японскими символами
    if is_gbc:
        logger.info("Обнаружена игра для Game Boy Color, возможно с японским текстом")
        # Проверяем наличие японских символов
        katakana_count = 0
        for i in range(0xA0, 0xE0):
            if i in freq and freq[i] > 5:
                katakana_count += 1

        if katakana_count > 10:
            logger.info("Обнаружены японские символы, настраиваем таблицу для катаканы")
            # Таблица катаканы
            katakana_map = {
                0xA1: '゠', 0xA2: 'ァ', 0xA3: 'ア', 0xA4: 'ィ', 0xA5: 'イ', 0xA6: 'ゥ',
                0xA7: 'ウ', 0xA8: 'ェ', 0xA9: 'エ', 0xAA: 'ォ', 0xAB: 'オ', 0xAC: 'カ',
                0xAD: 'ガ', 0xAE: 'キ', 0xAF: 'ギ', 0xB0: 'ク', 0xB1: 'グ', 0xB2: 'ケ',
                0xB3: 'ゲ', 0xB4: 'コ', 0xB5: 'ゴ', 0xB6: 'サ', 0xB7: 'ザ', 0xB8: 'シ',
                0xB9: 'ジ', 0xBA: 'ス', 0xBB: 'ズ', 0xBC: 'セ', 0xBD: 'ゼ', 0xBE: 'ソ',
                0xBF: 'ゾ', 0xC0: 'タ', 0xC1: 'ダ', 0xC2: 'チ', 0xC3: 'ヂ', 0xC4: 'ッ',
                0xC5: 'ツ', 0xC6: 'ヅ', 0xC7: 'テ', 0xC8: 'デ', 0xC9: 'ト', 0xCA: 'ド',
                0xCB: 'ナ', 0xCC: 'ニ', 0xCD: 'ヌ', 0xCE: 'ネ', 0xCF: 'ノ', 0xD0: 'ハ',
                0xD1: 'バ', 0xD2: 'パ', 0xD3: 'ヒ', 0xD4: 'ビ', 0xD5: 'ピ', 0xD6: 'フ',
                0xD7: 'ブ', 0xD8: 'プ', 0xD9: 'ヘ', 0xDA: 'ベ', 0xDB: 'ペ', 0xDC: 'ホ',
                0xDD: 'ボ', 0xDE: 'ポ', 0xDF: 'マ', 0xE0: 'ミ', 0xE1: 'ム', 0xE2: 'メ',
                0xE3: 'モ', 0xE4: 'ャ', 0xE5: 'ヤ', 0xE6: 'ュ', 0xE7: 'ユ', 0xE8: 'ョ',
                0xE9: 'ヨ', 0xEA: 'ラ', 0xEB: 'リ', 0xEC: 'ル', 0xED: 'レ', 0xEE: 'ロ',
                0xEF: 'ヮ', 0xF0: 'ワ', 0xF1: 'ヰ', 0xF2: 'ヱ', 0xF3: 'ヲ', 0xF4: 'ン',
                0xF5: 'ー', 0xF6: 'ヴ', 0xF7: 'ヵ', 0xF8: 'ヶ', 0xF9: 'ヷ', 0xFA: 'ヸ',
                0xFB: 'ヹ', 0xFC: 'ヺ'
            }
            charmap.update(katakana_map)

    # Попробуем определить, какие символы являются пробелами
    space_candidates = []
    for byte, count in common_bytes[:5]:  # 5 самых частых байтов
        if count > length * 0.05:  # Если встречается в 5% текста
            space_candidates.append(byte)

    if space_candidates:
        space_byte = space_candidates[0]
        charmap[space_byte] = ' '
        logger.info(f"Определен символ пробела: 0x{space_byte:02X}")

    # Добавляем ASCII символы для известных диапазонов
    for byte in range(0x20, 0x7F):
        if byte in rom_data[start:start + length]:
            charmap[byte] = chr(byte)

    # Попробуем определить терминаторы
    terminators = []
    for byte, count in common_bytes:
        # Если байт часто встречается в конце сообщений
        if count > 10 and byte not in charmap:
            is_terminator = True
            # Проверяем, часто ли этот байт встречается перед другими символами
            for i in range(start, min(start + length - 1, len(rom_data) - 1)):
                if rom_data[i] == byte and rom_data[i + 1] != byte:
                    # Если после этого байта часто идут другие символы
                    pass
                else:
                    is_terminator = False
                    break

            if is_terminator:
                terminators.append(byte)

    for byte in terminators[:3]:  # Берем 3 наиболее вероятных терминатора
        charmap[byte] = f'[END]'
        logger.info(f"Определен терминатор текста: 0x{byte:02X}")

    # Для японских игр добавляем распространенные символы
    if is_gbc and katakana_count > 10:
        # Добавляем распространенные японские символы
        charmap[0x00] = '\n'
        charmap[0xFF] = '\n'
    else:
        # Для западных игр используем стандартные терминаторы
        charmap[0x00] = '\n'
        charmap[0xFF] = '\n'

    logger.info(f"Создана таблица символов с {len(charmap)} символами")
    logger.debug(f"Таблица символов: {charmap}")

    return charmap


def find_text_pointers(rom_data: bytes, start: int = 0, end: int = None,
                       pointer_size: int = 2, min_length: int = 4) -> List[Tuple[int, int]]:
    """
    Поиск указателей на текст в ROM с учетом размера указателя
    Возвращает список кортежей (адрес, адрес_текста)
    """
    # Определяем конечный адрес
    end_value = end if end is not None else len(rom_data)

    # Формируем сообщение для лога
    logger.info(f"Поиск указателей (размер указателя: {pointer_size} байта) в диапазоне 0x{start:X}-0x{end_value:X}")

    pointers = []
    step = pointer_size

    for i in range(start, end_value - pointer_size + 1, step):
        # Определение адреса в зависимости от размера указателя
        if pointer_size == 2:
            addr = (rom_data[i + 1] << 8) | rom_data[i]
        elif pointer_size == 4:
            addr = (rom_data[i + 3] << 24) | (rom_data[i + 2] << 16) | (rom_data[i + 1] << 8) | rom_data[i]
        else:
            continue  # Неподдерживаемый размер указателя

        # Проверяем, является ли значение возможным адресом
        if 0x4000 <= addr < len(rom_data):
            # Проверяем, похож ли текст по адресу на текст
            if is_text_like(rom_data, addr, min_length):
                pointers.append((i, addr))
                logger.debug(f"Найден указатель: 0x{i:X} -> 0x{addr:X}")

    logger.info(f"Найдено {len(pointers)} указателей")
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

    result = printable / min_length > 0.7  # 70% символов должны быть "читаемыми"
    if result:
        logger.debug(f"Область 0x{start:X} похожа на текст ({printable/min_length:.0%} читаемых символов)")

    return result


def auto_detect_segments(rom_data: bytes, min_segment_length: int = 200, min_readability: float = 0.7) -> List[Dict]:
    """Автоматическое определение текстовых сегментов с улучшенной фильтрацией"""

    logger = logging.getLogger('gb2text.scanner')
    logger.info(f"Автоопределение текстовых сегментов (мин. длина={min_segment_length}, мин. читаемость={min_readability})")

    segments = []
    in_segment = False
    segment_start = 0
    current_run = 0

    # Используем более крупные блоки для анализа
    block_size = 32
    min_blocks_for_segment = max(3, min_segment_length // block_size)

    for i in range(0, len(rom_data), block_size):
        # Анализируем блок
        readable_chars = 0
        for j in range(block_size):
            if i + j < len(rom_data):
                byte = rom_data[i + j]
                # ASCII символы и распространенные терминаторы
                if 0x20 <= byte <= 0x7E or byte in [0x00, 0x0A, 0x0D, 0xFF]:
                    readable_chars += 1

        readability = readable_chars / block_size

        # Проверяем, начинается ли потенциальный сегмент
        if readability >= min_readability:
            current_run += 1

            if not in_segment and current_run >= min_blocks_for_segment:
                in_segment = True
                segment_start = i - (current_run - 1) * block_size
        else:
            if in_segment:
                # Завершаем сегмент
                segment_end = i
                segment_length = segment_end - segment_start

                # Проверяем минимальную длину и плотность текста
                if segment_length >= min_segment_length and readability > 0.65:
                    segments.append({
                        'name': f'auto_segment_{len(segments)}',
                        'start': segment_start,
                        'end': segment_end
                    })
                    logger.info(f"Найден сегмент: 0x{segment_start:X} - 0x{segment_end:X} "
                                f"(длина={segment_length}, читаемость={readability:.2%})")

                in_segment = False
                current_run = 0
            else:
                current_run = 0

        # Проверяем последний сегмент
    if in_segment:
        segment_end = len(rom_data)
        segment_length = segment_end - segment_start

        if segment_length >= min_segment_length:
            segments.append({
                'name': f'auto_segment_{len(segments)}',
                'start': segment_start,
                'end': segment_end
            })
            logger.info(f"Найден последний сегмент: 0x{segment_start:X} - 0x{segment_end:X} "
                        f"(длина={segment_length})")

    logger.info(f"Автоопределено {len(segments)} текстовых сегментов")
    return segments


def analyze_text_segment(rom_data: bytes, start: int, end: int) -> Dict:
    """
    Анализ текстового сегмента для определения характеристик
    """
    logger = logging.getLogger('gb2text.scanner')
    logger.info(f"Анализ текстового сегмента: 0x{start:X} - 0x{end:X}")

    segment = rom_data[start:end]

    # Анализ плотности "читаемых" символов
    printable_count = 0
    for byte in segment:
        if 0x20 <= byte <= 0x7E or byte in [0x00, 0x0A, 0x0D, 0xFF]:
            printable_count += 1

    readability = printable_count / len(segment) if segment else 0
    logger.info(f"Плотность читаемых символов: {readability:.2%}")

    # Анализ повторяющихся паттернов (возможно, сжатие)
    pattern_counts = Counter()
    for i in range(len(segment) - 3):
        pattern = segment[i:i + 4]
        pattern_counts[tuple(pattern)] += 1

    repeated_patterns = [p for p, c in pattern_counts.items() if c > 3]
    logger.info(f"Найдено {len(repeated_patterns)} повторяющихся паттернов")

    # Анализ возможных терминаторов
    terminators = Counter()
    for i in range(1, len(segment)):
        if segment[i - 1] != segment[i]:  # Если байт отличается от предыдущего
            terminators[segment[i - 1]] += 1

    common_terminators = terminators.most_common(3)
    logger.info(f"Наиболее вероятные терминаторы: {common_terminators}")

    # Анализ возможных указателей
    pointer_count = 0
    for i in range(0, len(segment) - 3, 4):
        addr = int.from_bytes(segment[i:i + 4], byteorder='little')
        if 0x4000 <= addr < len(rom_data):
            pointer_count += 1

    has_pointers = pointer_count > len(segment) * 0.1
    logger.info(f"Обнаружено {pointer_count} возможных указателей, {'есть' if has_pointers else 'нет'} указателей")

    return {
        'readability': readability,
        'common_terminators': [t[0] for t in common_terminators],
        'has_pointers': has_pointers,
        'repeated_patterns': repeated_patterns
    }