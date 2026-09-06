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

from core.decoder import CompressionHandler, LZ77Handler as BaseLZ77Handler
from core.gba_support import GBALZ77Handler

logger = logging.getLogger('gb2text.compression')


class LZSSHandler(CompressionHandler):
    """
    Обработчик LZSS сжатия.

    LZSS использует:
    - Флаговый байт (0x00 = литерал, 0xFF = ссылка)
    - Для ссылок: 2 байта (смещение, длина)
    """

    def decompress(self, data: bytes, start: int) -> tuple[bytes, int]:
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

    def decompress(self, data: bytes, start: int) -> tuple[bytes, int]:
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
        'lz77': [],               # Nintendo LZ77 без заголовка
        'lzss': [],               # Без четкой сигнатуры
        'rle': [],               # Без четкой сигнатуры
    }

    def __init__(self):
        from core.gba_support import GBALZ77Handler
        self.handlers: dict[str, CompressionHandler] = {
            'gba_lz77': GBALZ77Handler(),
            'lz77': BaseLZ77Handler(),
            'lzss': LZSSHandler(),
            'rle': RLEHandler(),
        }

    def decompress(self, data: bytes, start: int) -> tuple[bytes, int]:
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
        logger.warning("Неизвестный тип сжатия, возвращаю данные без распаковки")
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


class FFTA_LZSSHandler(CompressionHandler):
    """
    Обработчик LZSS сжатия для Final Fantasy Tactics Advance (GBA).

    Формат (из DataCrystal):
    - 4 байта big-endian: размер распакованных данных
    - Затем команды, декодируемые по старшему биту:

    Бит 7 установлен: RLE — следующий байт повторяется (X+3) раз
    Бит 6 установлен: literals — следующий байт это X+1 литералов
    Бит 5 установлен: output zeros — X+2 нулевых байт
    Бит 4 установлен: backref — 3 байта, back Z, copy 4+0b00YYXXXX
    Бит 1 установлен: output 0x00 × (X+3)
    Бит 0 установлен: output 0xFF × (X+3)
    Нет бит: backref — 3 байта, back Z, copy X+5

    Алгоритм из C# референсного кода DataCrystal:
    Каждая команда — один байт. Старшие биты определяют тип:
    - 0b1XXXXXXX: RLE — X+3 копий следующего байта
    - 0b01XXXXXX: literals — X+1 следующих байт копируются
    - 0b001XXXXX: zeros — X+2 нулевых байт
    - 0b0001XXXX YYZZZZZZ ZZZZZZZZ: backref Z, copy 4+0b00YYXXXX
    - 0b00000010 XXXXXXXX: output 0x00 × (X+3)
    - 0b00000001 XXXXXXXX: output 0xFF × (X+3)
    - 0b00000000 XXXXXXXX YYYYYYYY ZZZZZZZZ: backref Z, copy X+5
    """

    def decompress(self, data: bytes, start: int) -> tuple[bytes, int]:
        """Распаковывает FFTA LZSS данные.

        Ожидает 4-байтовый заголовок big-endian с размером распакованных данных.
        """
        if start + 4 > len(data):
            return b"", 0

        # Читаем размер распакованных данных (big-endian, 4 байта)
        decomp_size = int.from_bytes(data[start:start + 4], 'big')

        if decomp_size <= 0 or decomp_size > 0x100000:
            return b"", 0

        # Данные начинаются после заголовка
        result = bytearray()
        i = start + 4

        while i < len(data) and len(result) < decomp_size:
            cmd = data[i]
            i += 1

            # Бит 7: RLE — повторить следующий байт (X+3) раз
            if cmd & 0x80:
                x = cmd & 0x7F
                repeat_count = x + 3
                if i < len(data):
                    val = data[i]
                    i += 1
                    for _ in range(repeat_count):
                        if len(result) >= decomp_size:
                            break
                        result.append(val)

            # Бит 6: literals — скопировать X+1 следующих байт
            elif cmd & 0x40:
                x = cmd & 0x3F
                lit_count = x + 1
                for _ in range(lit_count):
                    if i >= len(data) or len(result) >= decomp_size:
                        break
                    result.append(data[i])
                    i += 1

            # Бит 5: zeros — X+2 нулевых байт
            elif cmd & 0x20:
                x = cmd & 0x1F
                zero_count = x + 2
                for _ in range(zero_count):
                    if len(result) >= decomp_size:
                        break
                    result.append(0)

            # Бит 4: backref 4-байтовый
            elif cmd & 0x10:
                x = cmd & 0x0F
                if i + 1 < len(data):
                    b1 = data[i]
                    b2 = data[i + 1]
                    i += 2

                    # back Z bytes, copy 4 + (0b00 << 6 | YY << 4 | X)
                    # Из DataCrystal: 0b0001XXXX 0bYYZZZZZZ 0bZZZZZZZZ
                    z = ((b1 & 0x3F) << 8) | b2
                    yy = (b1 >> 6) & 0x03
                    copy_len = 4 + ((yy << 4) | x)

                    if z > 0 and z <= len(result):
                        for _ in range(copy_len):
                            if len(result) >= decomp_size:
                                break
                            result.append(result[len(result) - z])

            # Бит 1: output 0x00 × (X+3)
            elif cmd & 0x02:
                # Формат: 0b00000010 XXXXXXXX
                if i < len(data):
                    x = data[i]
                    i += 1
                    for _ in range(x + 3):
                        if len(result) >= decomp_size:
                            break
                        result.append(0)

            # Бит 0: output 0xFF × (X+3)
            elif cmd & 0x01:
                if i < len(data):
                    x = data[i]
                    i += 1
                    for _ in range(x + 3):
                        if len(result) >= decomp_size:
                            break
                        result.append(0xFF)

            # Нет бит: backref 5-байтовый
            else:
                if i + 2 < len(data):
                    x = data[i]
                    _ = data[i + 1]  # unused per DataCrystal spec
                    z = data[i + 2]
                    i += 3

                    # back Z bytes, copy X+5
                    copy_len = x + 5

                    if z > 0 and z <= len(result):
                        for _ in range(copy_len):
                            if len(result) >= decomp_size:
                                break
                            result.append(result[len(result) - z])

        return bytes(result[:decomp_size]), i - start


class HuffmanHandler(CompressionHandler):
    """
    Обработчик Huffman сжатия для Fire Emblem GBA.

    FE GBA использует кастомный Huffman coding для сжатия текста.
    Дерево Huffman хранится в ROM и используется для декодирования битовых потоков.

    Формат дерева FE GBA Huffman:
    - Каждый узел: 2 байта (left_child | (right_child << 8))
    - Если child >= 0x80, это лист (child - 0x80 = символ)
    - Если child < 0x80, это индекс следующего узла
    """

    def __init__(self):
        self.tree_base: int = 0
        self.tree_data: int = 0

    def set_tree_pointers(self, tree_base: int, tree_data: int):
        """Устанавливает указатели на Huffman дерево в ROM"""
        self.tree_base = tree_base
        self.tree_data = tree_data

    def decompress(self, data: bytes, start: int) -> tuple[bytes, int]:
        """Распаковывает Huffman данные"""
        raise NotImplementedError(
            "Huffman decompression requires tree_base/tree_data. "
            "Use decompress_text_block() with ROM data."
        )

    def decompress_text_block(self, rom_data: bytes, block_offset: int,
                              tree_base: int, tree_data: int) -> bytes:
        """
        Декодирует текстовый блок, сжатый Huffman для FE GBA.

        Формат:
        - Битовый поток начинается с block_offset
        - Дерево хранится по адресу tree_base
        - Каждый символ декодируется по дереву Huffman
        - Биты читаются LSB first (младший бит первый)
        """
        if block_offset >= len(rom_data) or tree_base >= len(rom_data):
            return b""

        result = bytearray()
        bit_pos = 0
        byte_offset = block_offset

        # Читаем до 1024 символов или до терминатора
        while byte_offset < len(rom_data) and len(result) < 1024:
            # Начинаем с корня дерева (индекс 0)
            node_idx = 0

            # Декодируем один символ
            while True:
                if byte_offset >= len(rom_data):
                    break

                # Читаем один бит (LSB first)
                current_byte = rom_data[byte_offset]
                bit = (current_byte >> bit_pos) & 1
                bit_pos += 1

                if bit_pos >= 8:
                    bit_pos = 0
                    byte_offset += 1

                # Читаем узел дерева
                node_addr = tree_base + (node_idx * 2)
                if node_addr + 1 >= len(rom_data):
                    break

                left_child = rom_data[node_addr]
                right_child = rom_data[node_addr + 1]

                # Выбираем ребенка
                child = left_child if bit == 0 else right_child

                # Проверяем, лист ли это
                if child >= 0x80:
                    char_code = child - 0x80
                    if char_code == 0x00:  # Терминатор
                        return bytes(result)
                    result.append(char_code)
                    break
                else:
                    # Переходим к следующему узлу
                    node_idx = child

        return bytes(result)


# Константы для FE GBA Huffman
FE_HUFFMAN_CONSTANTS = {
    'FE7U': {
        'tree_base': 0x08000000,  # Адрес дерева (нужно найти в ROM)
        'tree_data': 0x08000000,
        'text_start': 0x08000000,
    },
    'FE8U': {
        'tree_base': 0x08000000,
        'tree_data': 0x08000000,
        'text_start': 0x08000000,
    },
}


def get_compression_handler(compression_type: str) -> CompressionHandler | None:
    """
    Возвращает обработчик сжатия по типу.

    Args:
        compression_type: тип сжатия ('gba_lz77', 'lzss', 'rle', 'huffman', 'auto')

    Returns:
        Обработчик сжатия или None
    """
    handlers = {
        'gba_lz77': GBALZ77Handler(),
        'lz77': BaseLZ77Handler(),
        'lzss': LZSSHandler(),
        'rle': RLEHandler(),
        'huffman': HuffmanHandler(),
        'auto': AutoDetectCompressionHandler(),
    }
    return handlers.get(compression_type)


# Константы типов сжатия
COMPRESSION_TYPES = {
    'NONE': 'none',
    'GBA_LZ77': 'gba_lz77',
    'LZ77': 'lz77',
    'LZSS': 'lzss',
    'RLE': 'rle',
    'AUTO': 'auto',
}
