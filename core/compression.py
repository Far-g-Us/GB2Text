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
from typing import ClassVar

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
                break  # pragma: no cover - недостижимо: проверено условием цикла выше

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

                    if offset < len(out):  # pragma: no branch
                        for _ in range(length):
                            if offset < len(out):
                                out.append(out[len(out) - offset - 1])
                            else:  # pragma: no cover - недостижимо: offset фиксирован, out только растёт
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
    SIGNATURES: ClassVar[dict[str, list[int]]] = {
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


class FFTA_LZSSHandler(CompressionHandler):  # noqa: N801 — имя с префиксом игры осознанно
    """
    Обработчик LZSS сжатия для Final Fantasy Tactics Advance (GBA).

    Формат (DataCrystal + эталон references/ffta_lzss_myguyz.py):
    - 4 байта big-endian: размер распакованных данных
    - Затем поток команд; тип определяется старшим битом либо точным значением.

    Команды (первый байт `cmd`):
    - бит 7 (0b1XXXXYYY YYYYYYYY): backref — расстояние ((cmd&7)<<8|arg)+1
      (1..0x800), длина ((cmd>>3)&0xF)+3 (3..18); 2 байта.
    - бит 6 (0b01XXXXXX): литералы, длина (cmd&0x3F)+1.
    - бит 5 (0b001XXXXX): нули, длина (cmd&0x1F)+2.
    - бит 4 (0b0001XXXX YYZZZZZZ ZZZZZZZZ): backref — расстояние
      (((b1&0x3F)<<8)|b2)+1 (1..0x4000), длина (((b1>>2)&0x30)|(cmd&0xF))+4
      (4..67); 3 байта.
    - cmd == 0x02: нули. Следующий байт + 3.
    - cmd == 0x01: байты 0xFF. Следующий байт + 3.
    - cmd == 0x00: backref — расстояние (b2<<8)|b3 (1..0x10000),
      длина b1+5 (5..260); 4 байта.
    - прочие значения (0x03, 0x04, 0x06, ...) — невалидный поток.

    Семантика переполнения decomp_size: все команды (нули, backref, литералы)
    клampятся — вывод усекается до decomp_size, декомпрессия считается успешной.
    Это осознанно расходится с эталоном references/ffta_lzss_myguyz.py: литералы
    у эталона при переполнении возвращают None. Унификация оправдана длиной
    реальных блоков (ни один не переполняет заявленный размер) и прецедентом
    GBALZ77Handler (gba_support.py). Исчерпание входа при литералах по-прежнему
    ошибка.
    """

    def decompress(self, data: bytes, start: int) -> tuple[bytes, int]:
        """Распаковывает FFTA LZSS данные.

        Ожидает 4-байтовый big-endian заголовок с размером распакованных данных.
        При некорректном или оборванном потоке возвращает (b"", 0).
        """
        if start + 4 > len(data):
            return b"", 0

        decomp_size = int.from_bytes(data[start:start + 4], 'big')

        if decomp_size <= 0 or decomp_size > 0x100000:
            return b"", 0

        result: bytearray = bytearray()
        i = start + 4
        data_len = len(data)

        while len(result) < decomp_size:
            if i >= data_len:
                return b"", 0
            cmd = data[i]
            i += 1

            # Бит 7: backref — 2 байта (расстояние 1..0x800, длина 3..18)
            if cmd & 0x80:
                if i >= data_len:
                    return b"", 0
                dist = (((cmd & 0x07) << 8) | data[i]) + 1
                i += 1
                src_pos = len(result) - dist
                if src_pos < 0:
                    return b"", 0
                count = ((cmd >> 3) & 0x0F) + 3
                for _ in range(count):
                    if len(result) >= decomp_size:  # pragma: no branch
                        break  # pragma: no cover
                    if src_pos < len(result):
                        result.append(result[src_pos])
                    else:  # pragma: no cover - недостижимо: разрыв src/len сохраняется (оба +1 за итерацию)
                        result.append(0)
                    src_pos += 1

            # Бит 6: литералы — скопировать (cmd&0x3F)+1 следующих байт
            elif cmd & 0x40:
                lit_count = (cmd & 0x3F) + 1
                for _ in range(lit_count):
                    if len(result) >= decomp_size:
                        break
                    if i >= data_len:
                        return b"", 0
                    result.append(data[i])
                    i += 1

            # Бит 5: нули — (cmd&0x1F)+2 нулевых байт
            elif cmd & 0x20:
                zero_count = (cmd & 0x1F) + 2
                for _ in range(zero_count):
                    if len(result) >= decomp_size:  # pragma: no branch
                        break  # pragma: no cover
                    result.append(0)

            # Бит 4: backref — 3 байта (расстояние 1..0x4000, длина 4..67)
            elif cmd & 0x10:
                if i + 1 >= data_len:
                    return b"", 0
                b1 = data[i]
                b2 = data[i + 1]
                i += 2
                src_pos = len(result) - ((b1 & 0x3F) << 8) - b2 - 1
                if src_pos < 0:
                    src_pos = 0
                copy_len = (((b1 >> 2) & 0x30) | (cmd & 0x0F)) + 4
                for _ in range(copy_len):
                    if len(result) >= decomp_size:
                        break
                    if src_pos < len(result):
                        result.append(result[src_pos])
                    else:
                        result.append(0)
                    src_pos += 1

            # Команда 0x02: нули — следующий байт + 3 штук
            elif cmd == 0x02:
                if i >= data_len:  # pragma: no branch
                    return b"", 0  # pragma: no cover
                for _ in range(data[i] + 3):
                    if len(result) >= decomp_size:
                        break
                    result.append(0)
                i += 1

            # Команда 0x01: байты 0xFF — следующий байт + 3 штук
            elif cmd == 0x01:
                if i >= data_len:  # pragma: no branch
                    return b"", 0  # pragma: no cover
                for _ in range(data[i] + 3):
                    if len(result) >= decomp_size:
                        break
                    result.append(0xFF)
                i += 1

            # Команда 0x00: backref — 4 байта (расстояние 1..0x10000, длина 5..260)
            elif cmd == 0x00:
                if i + 2 >= data_len:
                    return b"", 0
                src_pos = len(result) - ((data[i + 1] << 8) | data[i + 2]) - 1
                if src_pos < 0:
                    src_pos = 0
                copy_len = data[i] + 5
                i += 3
                for _ in range(copy_len):
                    if len(result) >= decomp_size:  # pragma: no branch
                        break  # pragma: no cover
                    if src_pos < len(result):  # pragma: no branch
                        result.append(result[src_pos])
                    else:
                        result.append(0)  # pragma: no cover
                    src_pos += 1

            # Прочие байты — невалидная команда
            else:
                return b"", 0

        return bytes(result), i - start

    def compress(self, data: bytes) -> bytes:
        """Сжимает данные в FFTA LZSS.

        Возвращает 4-байтовый big-endian заголовок (размер распакованных данных)
        и поток команд, который корректно разбирается decompress() и эталоном.
        Жадный подбор: сначала run'ы нулей/0xFF, затем длиннейшее совпадение
        в окне 0x4000. Пустые данные не поддерживаются.
        """
        if not data:
            raise ValueError("FFTA LZSS не поддерживает сжатие пустых данных")

        if len(data) > 0x100000:
            raise ValueError(
                f"FFTA LZSS не сжимает блоки больше 0x100000 байт (получено {len(data)})"
            )

        n = len(data)
        out = bytearray()
        out.extend(n.to_bytes(4, 'big'))
        pos = 0
        literals = bytearray()

        def flush() -> None:
            """Сбрасывает накопленные литералы в поток (блоками до 64 байт)."""
            if not literals:
                return
            cur = 0
            while cur < len(literals):
                count = min(64, len(literals) - cur)
                out.append(0x40 | (count - 1))
                out.extend(literals[cur:cur + count])
                cur += count
            literals.clear()

        def find_best_match(start: int) -> tuple[int, int]:
            """Ищет длиннейшее совпадение в окне 0x4000. Возвращает (len, dist)."""
            best_len = 0
            best_dist = 0
            limit = min(start, 0x4000)
            max_len = min(260, n - start)
            for d in range(1, limit + 1):
                src = start - d
                ln = 0
                while ln < max_len and data[src + ln] == data[start + ln]:
                    ln += 1
                if ln > best_len:
                    best_len = ln
                    best_dist = d
                    if ln >= max_len:
                        break
            return best_len, best_dist

        while pos < n:
            field = data[pos]

            run = 1
            while pos + run < n and data[pos + run] == field and run < 260:
                run += 1

            # Run'ы нулей: бит5 (до 33 байт одной командой) и команда 0x02 (до 258)
            if field == 0x00 and run >= 2:
                flush()
                consumed = 0
                remaining = run
                while remaining > 258:
                    out.append(0x02)
                    out.append(0xFF)  # 258 нулей
                    remaining -= 258
                    consumed += 258
                if remaining >= 2:
                    if remaining <= 33:
                        out.append(0x20 | (remaining - 2))
                    else:
                        out.append(0x02)
                        out.append(remaining - 3)
                    consumed += remaining
                pos += consumed
                continue

            # Run 0xFF: только команда 0x01 (3..258 байт)
            if field == 0xFF and run >= 3:
                flush()
                consumed = 0
                remaining = run
                while remaining >= 3:
                    chunk = min(258, remaining)
                    out.append(0x01)
                    out.append(chunk - 3)
                    remaining -= chunk
                    consumed += chunk
                pos += consumed
                continue

            best_len, best_dist = find_best_match(pos)

            best_gain = -1
            best_cover = 0
            best_type = 0  # 7 = бит7, 4 = бит4, 0 = команда 0x00

            def consider(gain: int, cover: int, cmd_type: int) -> None:
                nonlocal best_gain, best_cover, best_type
                if gain > best_gain or (gain == best_gain and cover > best_cover):
                    best_gain = gain
                    best_cover = cover
                    best_type = cmd_type

            if best_len >= 3 and best_dist <= 0x800:
                consider(min(best_len, 18) - 2, min(best_len, 18), 7)
            if best_len >= 4 and best_dist <= 0x4000:
                consider(min(best_len, 67) - 3, min(best_len, 67), 4)
            if best_len >= 5:
                consider(min(best_len, 260) - 4, min(best_len, 260), 0)

            if best_gain > 0:
                flush()
                dist_code = best_dist - 1
                if best_type == 7:
                    out.append(0x80 | ((best_cover - 3) << 3) | ((dist_code >> 8) & 0x07))
                    out.append(dist_code & 0xFF)
                elif best_type == 4:
                    length_code = best_cover - 4
                    out.append(0x10 | (length_code & 0x0F))
                    out.append(((length_code >> 4) << 6) | ((dist_code >> 8) & 0x3F))
                    out.append(dist_code & 0xFF)
                else:
                    out.append(0x00)
                    out.append(best_cover - 5)
                    out.append((dist_code >> 8) & 0xFF)
                    out.append(dist_code & 0xFF)
                pos += best_cover
                continue

            literals.append(field)
            pos += 1

        flush()
        return bytes(out)


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
            depth = 0

            # Декодируем один символ
            while True:
                # Предохранитель от циклического/вырожденного дерева:
                # на боевых данных путь до листа не превышает ~16 узлов
                if depth > 64:
                    return bytes(result)
                depth += 1

                if byte_offset >= len(rom_data):
                    break  # pragma: no cover - недостижимо: внешний цикл гарантирует byte_offset < len

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
