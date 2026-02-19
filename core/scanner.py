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

from core.constants import (
    ROM_HEADER_SIZE,
    MIN_SEGMENT_LENGTH,
    MIN_READABILITY,
    MIN_POINTER_LENGTH,
    READABLE_BLOCK_SIZE,
    TEXT_TERMINATORS,
    ASCII_PRINTABLE_START,
    ASCII_PRINTABLE_END,
    KATAKANA_RANGE,
    HIRAGANA_RANGE,
    BANK_0_START,
    VRAM_START,
    VRAM_END,
    CYRILLIC_UPPER,
    CYRILLIC_LOWER,
)

logger = logging.getLogger('gb2text.scanner')


def find_text_pointers(rom_data: bytes, start: int = 0, end: int = None,
                       pointer_size: int = 2, min_length: int = MIN_POINTER_LENGTH,
                       address_base: int = 0) -> List[Tuple[int, int]]:
    """
    Поиск указателей на текст в ROM с учетом размера указателя и базового адреса (для GBA)
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

        # Маппим адрес для систем с базой адреса (например, GBA 0x08000000)
        mapped = addr
        if pointer_size == 4 and address_base:
            mapped = addr - address_base
            if mapped < 0:
                continue

        # Проверяем, является ли значение возможным адресом
        if 0x4000 <= mapped < len(rom_data):
            # Проверяем, похож ли текст по адресу на текст
            if is_text_like(rom_data, mapped, min_length):
                pointers.append((i, mapped))
                logger.debug(f"Найден указатель: 0x{i:X} -> 0x{mapped:X} (raw=0x{addr:X}, base=0x{address_base:X})")

    logger.info(f"Найдено {len(pointers)} указателей")
    return pointers


def is_text_like(rom_data: bytes, start: int, min_length: int) -> bool:
    """Проверяет, похож ли участок данных на текст"""

    if start + min_length > len(rom_data):
        return False

    # Подсчитываем процент "читаемых" символов
    printable = 0
    for i in range(min_length):
        byte = rom_data[start + i]
        # ASCII символы и распространенные терминаторы
        if 0x20 <= byte <= 0x7E or byte in [0x00, 0x0A, 0x0D, 0xFF]:
            printable += 1

    result = min_length > 0 and printable / min_length > 0.6  # 60% символов должны быть "читаемыми"
    if result:
        logger.debug(f"Область 0x{start:X} похожа на текст ({printable / min_length:.0%} читаемых символов)")
    return result


def detect_multiple_languages(rom_data: bytes, start: int = 0, length: int = 2000) -> List[str]:
    """Определяет все языки, присутствующие в ROM"""

    logger = logging.getLogger('gb2text.scanner')
    logger.info(f"Определение всех языков в ROM, начиная с 0x{start:X}")

    freq = Counter()
    for i in range(start, min(start + length, len(rom_data))):
        byte = rom_data[i]
        freq[byte] += 1

    detected_languages = []

    # Проверка на английский (ASCII)
    ascii_count = sum(1 for i in range(0x20, 0x7F) if i in freq and freq[i] > 2)
    if ascii_count > 20:
        detected_languages.append('english')
        logger.info(f"Обнаружен английский язык (ASCII символов: {ascii_count})")

    # Проверка на японский
    japanese_count = sum(1 for i in range(0xA0, 0xDF) if i in freq and freq[i] > 2)
    if japanese_count > 10:
        detected_languages.append('japanese')
        logger.info(f"Обнаружен японский язык (катакана символов: {japanese_count})")

    # Проверка на русский
    cyrillic_count = sum(1 for i in range(CYRILLIC_UPPER[0], CYRILLIC_UPPER[1]) if i in freq and freq[i] > 2)
    if cyrillic_count > 10:
        detected_languages.append('russian')
        logger.info(f"Обнаружен русский язык (кириллица символов: {cyrillic_count})")

    return detected_languages if detected_languages else ['english']


def auto_detect_charmap(rom_data: bytes, start: int = 0, length: int = 1000) -> Dict[int, str]:
    """Автоматическое определение таблицы символов с поддержкой нескольких языков"""

    logger = logging.getLogger('gb2text.scanner')
    logger.info(f"Автоопределение таблицы символов, начиная с 0x{start:X}, длина: {length}")

    detected_languages = detect_multiple_languages(rom_data, start, length)
    logger.info(f"Обнаружены языки: {detected_languages}")

    if 'english' in detected_languages:
        primary_language = 'english'
        logger.info("Выбран английский язык как приоритетный")
    else:
        primary_language = detected_languages[0]
        logger.info(f"Выбран язык: {primary_language}")

    # Анализ статистики использования байтов (оптимизировано)
    # Используем Counter.update() вместо ручного инкрементирования
    freq = Counter(rom_data[start:min(start + length, len(rom_data))])

    # # Определение вероятных пробелов и терминаторов
    # common_bytes = freq.most_common()
    # logger.debug(f"Частота использования байтов: {common_bytes[:10]}...")

    charmap = {}

    # # Определяем язык игры по статистике
    # language = _detect_language(rom_data, start, length, freq)
    # logger.info(f"Определен язык игры: {language}")

    # Проверяем минимальный размер ROM
    if len(rom_data) < ROM_HEADER_SIZE:
        logger.error("ROM слишком маленький для анализа")
        for byte in range(ASCII_PRINTABLE_START, ASCII_PRINTABLE_END + 1):
            charmap[byte] = chr(byte)
        return charmap

    if primary_language == 'japanese':
        _setup_japanese_charmap(charmap, freq)
    elif primary_language == 'russian':
        _setup_russian_charmap(charmap)
    else:  # Английский по умолчанию
        _setup_english_charmap(charmap)

    # Добавляем пробелы и терминаторы
    _setup_common_symbols(charmap, freq, False, rom_data)

    logger.info(f"Создана таблица символов с {len(charmap)} символами для языка: {primary_language}")
    logger.debug(f"Таблица символов: {dict(list(charmap.items())[:10])}...")

    return charmap


def _detect_language(rom_data: bytes, start: int, length: int, freq: Counter) -> str:
    """Улучшенное определение языка с приоритетом английского"""

    # Сначала проверяем плотность ASCII символов
    ascii_density = sum(1 for i in range(start, min(start + length, len(rom_data)))
                        if 0x20 <= rom_data[i] <= 0x7E) / length

    if ascii_density > 0.3:  # 30% ASCII = английский
        return 'english'

    # Проверка на японский
    japanese_count = sum(1 for i in range(0xA0, 0xDF) if i in freq and freq[i] > 3)
    if japanese_count > 15:
        return 'japanese'

    # Проверка на русский
    cyrillic_count = sum(1 for i in range(CYRILLIC_LOWER[0], CYRILLIC_LOWER[1] + 1) if i in freq and freq[i] > 3)
    if cyrillic_count > 15:
        return 'russian'

    return 'english'  # По умолчанию английский


def _setup_russian_charmap(charmap: Dict):
    """Настраивает таблицу символов для русского языка"""

    # Пример таблицы для русского языка в CP866
    cyrillic_map = {
        0x80: 'Ё', 0x81: 'ё',
        0x98: 'Ж', 0x99: 'ж', 0x9A: 'Б', 0x9B: 'б', 0x9C: 'К', 0x9D: 'к',
        0x9E: 'Н', 0x9F: 'н', 0xA0: 'Г', 0xA1: 'г', 0xA2: 'Л', 0xA3: 'л',
        0xA4: 'Д', 0xA5: 'д', 0xA6: 'Т', 0xA7: 'т', 0xA8: 'Щ', 0xA9: 'щ',
        0xAA: 'З', 0xAB: 'з', 0xAC: 'Ш', 0xAD: 'ш', 0xAE: 'Ч', 0xAF: 'ч',
        0xB0: 'Ъ', 0xB1: 'ъ', 0xB2: 'Ы', 0xB3: 'ы', 0xB4: 'Ь', 0xB5: 'ь',
        0xB6: 'Э', 0xB7: 'э', 0xB8: 'Ф', 0xB9: 'ф', 0xBA: 'И', 0xBB: 'и',
        0xBC: 'С', 0xBD: 'с', 0xBE: 'В', 0xBF: 'в', 0xC0: 'У', 0xC1: 'у',
        0xC2: 'А', 0xC3: 'а', 0xC4: 'П', 0xC5: 'п', 0xC6: 'Р', 0xC7: 'р',
        0xC8: 'О', 0xC9: 'о', 0xCA: 'Л', 0xCB: 'л', 0xCC: 'Д', 0xCD: 'д',
        0xCE: 'Ж', 0xCF: 'ж', 0xD0: 'Э', 0xD1: 'е', 0xD2: 'Я', 0xD3: 'я',
        0xD4: 'Ч', 0xD5: 'ч', 0xD6: 'С', 0xD7: 'с', 0xD8: 'М', 0xD9: 'м',
        0xDA: 'И', 0xDB: 'и', 0xDC: 'Т', 0xDD: 'т', 0xDE: 'Ь', 0xDF: 'ь',
        0xE0: 'Б', 0xE1: 'б', 0xE2: 'Ю', 0xE3: 'ю', 0xE4: 'А', 0xE5: 'а',
        0xE6: 'Ц', 0xE7: 'ц', 0xE8: 'Е', 0xE9: 'е', 0xEA: 'Н', 0xEB: 'н',
        0xEC: 'Г', 0xED: 'г', 0xEE: 'Р', 0xEF: 'р', 0xF0: 'Ш', 0xF1: 'ш',
        0xF2: 'Щ', 0xF3: 'щ', 0xF4: 'З', 0xF5: 'з', 0xF6: 'Х', 0xF7: 'х',
        0xF8: 'Ъ', 0xF9: 'ъ', 0xFA: 'Ф', 0xFB: 'ф', 0xFC: 'Ы', 0xFD: 'ы',
        0xFE: 'Ь', 0xFF: 'ь'
    }
    charmap.update(cyrillic_map)

    # Добавляем распространенные символы
    charmap[0x00] = '\n'
    charmap[0x0D] = '\n'
    charmap[0x0A] = '\n'


def _setup_english_charmap(charmap: Dict):
    """Настраивает таблицу символов для английского языка"""
    # Добавляем только стандартные ASCII символы
    for byte in range(ASCII_PRINTABLE_START, ASCII_PRINTABLE_END + 1):
        charmap[byte] = chr(byte)

        # Добавляем основные управляющие символы
    charmap[0x00] = '\n'  # Null terminator
    charmap[0x0A] = '\n'  # Line feed
    charmap[0x0D] = '\n'  # Carriage return
    charmap[0xFF] = '\n'  # End marker

    logger.info("Настроена английская ASCII таблица символов")


def _setup_japanese_charmap(charmap: Dict, freq: Counter):
    """Настраивает таблицу символов для японского языка с поддержкой катаканы и хираганы"""

    # Проверяем, какие диапазоны реально используются
    katakana_used = any(i in freq and freq[i] > 2 for i in range(KATAKANA_RANGE[0], KATAKANA_RANGE[1] + 1))
    hiragana_used = any(i in freq and freq[i] > 2 for i in range(HIRAGANA_RANGE[0], HIRAGANA_RANGE[1] + 1))

    logger.info(f"Японские диапазоны: катакана={katakana_used}, хирагана={hiragana_used}")

    if katakana_used:
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
        logger.info("Добавлена катакана")

    if hiragana_used and not katakana_used:
        # Добавляем базовую хирагану
        hiragana_map = {
            0x80: '　', 0x81: '、', 0x82: '。', 0x83: '・', 0x84: '゛', 0x85: '゜',
            0x86: 'ー', 0x87: 'あ', 0x88: 'い', 0x89: 'う', 0x8A: 'え', 0x8B: 'お',
            0x8C: 'か', 0x8D: 'き', 0x8E: 'く', 0x8F: 'け', 0x90: 'こ', 0x91: 'さ',
            0x92: 'し', 0x93: 'す', 0x94: 'せ', 0x95: 'そ', 0x96: 'た', 0x97: 'ち',
            0x98: 'つ', 0x99: 'て', 0x9A: 'と', 0x9B: 'な', 0x9C: 'に', 0x9D: 'ぬ',
            0x9E: 'ね', 0x9F: 'の', 0xA0: 'は', 0xA1: 'ひ', 0xA2: 'ふ', 0xA3: 'へ',
            0xA4: 'ほ', 0xA5: 'ま', 0xA6: 'み', 0xA7: 'む', 0xA8: 'め', 0xA9: 'も',
            0xAA: 'や', 0xAB: 'ゆ', 0xAC: 'よ', 0xAD: 'ら', 0xAE: 'り', 0xAF: 'る',
            0xB0: 'れ', 0xB1: 'ろ', 0xB2: 'わ', 0xB3: 'を', 0xB4: 'ん', 0xB5: 'ゔ',
            0xB6: 'ゕ', 0xB7: 'ゖ', 0xB8: '゛', 0xB9: '゜', 0xBA: 'ゝ', 0xBB: 'ゞ',
            0xBC: 'ゟ', 0xBD: '゠', 0xBE: 'ァ', 0xBF: 'ィ', 0xC0: 'ゥ', 0xC1: 'ェ',
            0xC2: 'ォ', 0xC3: 'ャ', 0xC4: 'ュ', 0xC5: 'ョ', 0xC6: 'ッ', 0xC7: 'ー'
        }
        # Добавляем только те символы, которые встречаются в ROM
        for byte, char in hiragana_map.items():
            if byte in freq and freq[byte] > 1:
                charmap[byte] = char
        logger.info("Добавлена хирагана")

    # Добавляем распространенные символы
    charmap[0x00] = '\n'
    charmap[0xFF] = '\n'
    charmap[0x0D] = '\n'  # Возврат каретки


def _setup_common_symbols(charmap: Dict, freq: Counter, is_gbc: bool, rom_data: bytes = None):
    """Добавляет общие символы и терминаторы"""

    logger = logging.getLogger('gb2text.scanner')
    logger.info("Настройка общих символов и терминаторов")

    # Ищем наиболее частый байт как потенциальный пробел
    if freq:
        most_common = freq.most_common(10)
        for byte, count in most_common:
            # Если байт встречается часто и не является ASCII символом
            if count > len(rom_data) * 0.01 and byte not in charmap and byte not in TEXT_TERMINATORS:
                charmap[byte] = ' '
                logger.info(f"Определен символ пробела: 0x{byte:02X}")
                break

    # Попробуем определить терминаторы
    terminators = []
    for byte in freq:
        # Если байт часто встречается в конце сообщений
        if freq[byte] > 10 and byte not in charmap:
            is_terminator = True

            # Проверяем, часто ли этот байт встречается перед другими символами
            if rom_data is not None:
                data_slice = rom_data[:min(100, len(rom_data) - 1)]
                # Эффективная проверка с использованием any()
                is_terminator = any(
                    rom_data[i] == byte and rom_data[i + 1] != byte
                    for i in range(min(100, len(rom_data) - 1))
                )

            if is_terminator:
                terminators.append(byte)

    for byte in terminators[:3]:  # Берем 3 наиболее вероятных терминатора
        charmap[byte] = '\n'
        logger.info(f"Определен терминатор текста: 0x{byte:02X}")

    # Для GBC игр добавляем распространенные символы
    if is_gbc:
        # Добавляем распространенные японские символы как fallback
        charmap[0x00] = '\n'
        charmap[0xFF] = '\n'


def auto_detect_segments(rom_data: bytes, min_segment_length: int = MIN_SEGMENT_LENGTH, min_readability: float = MIN_READABILITY,
                         block_size: int = READABLE_BLOCK_SIZE) -> List[Dict]:
    """Автоматическое определение текстовых сегментов с улучшенной фильтрацией"""

    logger = logging.getLogger('gb2text.scanner')
    logger.info(
        f"Автоопределение текстовых сегментов (мин. длина={min_segment_length}, мин. читаемость={min_readability}, размер блока={block_size})")

    segments = []
    in_segment = False
    segment_start = 0
    current_run = 0

    # Используем более крупные блоки для анализа
    min_blocks_for_segment = max(3, min_segment_length // block_size)

    # Пропускаем известные нетекстовые области
    skip_ranges = [
        (0x0000, BANK_0_START),  # Область кода
        (VRAM_START, VRAM_END)   # Область VRAM
    ]

    i = 0
    while i < len(rom_data):
        # Пропускаем известные нетекстовые области
        i = _skip_non_text_regions(i, rom_data, skip_ranges)
        if i >= len(rom_data):
            break

        # Анализируем блок
        readability = _compute_block_readability(rom_data, i, block_size)

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
                if segment_length >= min_segment_length:
                    segments = _add_segment(segments, segment_start, segment_end, readability, logger)

                in_segment = False
                current_run = 0
            else:
                current_run = 0

            # Пропускаем больше байтов после низкой плотности
            i += max(1, block_size // 2)
            continue

        i += block_size

    # Проверяем последний сегмент
    if in_segment:
        segment_end = len(rom_data)
        segment_length = segment_end - segment_start

        if segment_length >= min_segment_length:
            segments = _add_segment(segments, segment_start, segment_end, 0, logger)

    logger.info(f"Автоопределено {len(segments)} текстовых сегментов")
    return segments


def _skip_non_text_regions(i: int, rom_data: bytes, skip_ranges: List[Tuple[int, int]]) -> int:
    """Пропускает известные нетекстовые области"""
    for start_skip, end_skip in skip_ranges:
        if start_skip <= i < end_skip:
            return end_skip
    return i


def _compute_block_readability(rom_data: bytes, start: int, block_size: int) -> float:
    """Вычисляет читаемость блока"""
    end_block = min(start + block_size, len(rom_data))
    readable_chars = sum(
        1 for j in range(start, end_block)
        if 0x20 <= rom_data[j] <= 0x7E or rom_data[j] in TEXT_TERMINATORS
    )
    return readable_chars / (end_block - start) if end_block > start else 0


def _add_segment(segments: List[Dict], start: int, end: int, readability: float, logger) -> List[Dict]:
    """Добавляет сегмент в список"""
    segments.append({
        'name': f'auto_segment_{len(segments)}',
        'start': start,
        'end': end
    })
    logger.info(f"Найден сегмент: 0x{start:X} - 0x{end:X} "
                f"(длина={end - start}, читаемость={readability:.2%})")
    return segments


def analyze_text_segment(rom_data: bytes, start: int, end: int) -> Dict:
    """Анализ текстового сегмента для определения характеристик"""

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