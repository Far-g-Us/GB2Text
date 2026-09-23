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
Поддержка Game Boy Advance ROM
"""

import logging

from core.decoder import CompressionHandler


class GBALZ77Handler(CompressionHandler):
    """Обработчик LZ77 (Nintendo, тип 0x10) для GBA.
    Формат:
        - data[start] == 0x10
        - далее 3 байта little-endian — длина распакованных данных (24-бит)
        - поток блоков: флаговый байт, затем 8 элементов:
            bit = 0 -> следующий байт — литерал
            bit = 1 -> 2 байта ссылки:
                длина = (b1 >> 4) + 3
                смещение = ((b1 & 0x0F) << 8) | b2
                distance = смещение + 1
                копируем length байт из уже распакованного буфера с заданной distance
    """

    def decompress(self, data: bytes, start: int) -> tuple[bytes, int]:
        logging.getLogger('gb2text.gba_lz77')

        # Грубая защита границ
        if start < 0 or start >= len(data):
            return b"", 0

        i = start
        # Проверяем заголовок LZ77 (тип 0x10)
        if data[i] != 0x10:
            # Не LZ77 0x10 — возвращаем как есть, чтобы не ломать пайплайн
            return data[start:], len(data) - start
        i += 1

        # Длина распакованных данных (24-бит, little-endian)
        if i + 3 > len(data):
            # Заголовок неполный — безопасный фолбэк
            return data[start:], len(data) - start
        decomp_len = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16)
        i += 3

        out = bytearray()

        # Читаем блоки до достижения заявленной длины
        while len(out) < decomp_len and i < len(data):
            flags = data[i]
            i += 1

            for bit in range(7, -1, -1):
                if len(out) >= decomp_len or i >= len(data):
                    break

                if ((flags >> bit) & 1) == 0:
                    # Литерал
                    out.append(data[i])
                    i += 1
                else:
                    # Ссылка (2 байта)
                    if i + 1 >= len(data):
                        # Неполная ссылка — прерываемся
                        break
                    b1 = data[i]
                    b2 = data[i + 1]
                    i += 2

                    length = (b1 >> 4) + 3
                    disp = ((b1 & 0x0F) << 8) | b2
                    distance = disp + 1

                    # Копирование из уже распакованных данных
                    for _ in range(length):
                        src_index = len(out) - distance
                        if src_index < 0:
                            # Некорректная ссылка — заполним нулями и продолжим
                            out.append(0)
                        else:
                            out.append(out[src_index])
                        if len(out) >= decomp_len:
                            break

        # Обрезаем до заявленной длины на всякий случай
        if len(out) > decomp_len:
            out = out[:decomp_len]  # pragma: no cover - недостижимо: все append под гардом len(out) < decomp_len

        consumed = i - start
        return bytes(out), consumed

    def compress(self, data: bytes) -> bytes:
        """
        Компрессия LZ77 (тип 0x10).
        Простой lazy-match алгоритм: ищет совпадения в предыдущих 4096 байтах.
        """
        import logging
        logging.getLogger('gb2text.gba_lz77')

        if not data:
            return b'\x10\x00\x00\x00'

        out = bytearray()
        i = 0

        # Вычисляем длину распакованных данных (24-bit LE)
        decomp_len = len(data)
        out.extend([
            0x10,
            decomp_len & 0xFF,
            (decomp_len >> 8) & 0xFF,
            (decomp_len >> 16) & 0xFF,
        ])

        while i < len(data):
            flags_pos = len(out)
            out.append(0)  # placeholder для флагового байта
            flags = 0

            for bit in range(8):
                if i >= len(data):
                    break

                # Ищем совпадение в предыдущих 4096 байтах
                best_length = 0
                best_offset = 0
                window_start = max(0, i - 4096)

                for j in range(window_start, i):
                    length = 0
                    while (i + length < len(data)
                           and length < 18
                           and data[j + length] == data[i + length]):
                        length += 1
                    if length >= 3 and length > best_length:
                        best_length = length
                        best_offset = i - j - 1

                if best_length >= 3:
                    # Ссылка: bit=1
                    flags |= (1 << (7 - bit))
                    length_byte = ((best_length - 3) << 4) | ((best_offset >> 8) & 0x0F)
                    offset_byte = best_offset & 0xFF
                    out.append(length_byte)
                    out.append(offset_byte)
                    i += best_length
                else:
                    # Литерал: bit=0
                    out.append(data[i])
                    i += 1

            out[flags_pos] = flags

        return bytes(out)

# def analyze_gba_text_regions(rom: GameBoyROM) -> list:
#     """Анализ GBA ROM для поиска текстовых регионов"""
#     # GBA использует другие адреса и структуры
#     text_regions = []
#
#     # Стандартные области для GBA
#     # Обычно текст находится в .text или .data секциях
#     # Нужно искать последовательности ASCII-подобных символов
#
#     for offset in range(0x08000000, len(rom.data), 0x1000):
#         # Проверяем каждые 4KB
#         region = rom.data[offset:offset + 0x1000]
#         if is_potential_text_region(region):
#             text_regions.append({
#                 'start': offset,
#                 'end': offset + 0x1000,
#                 'confidence': calculate_confidence(region)
#             })
#
#     return text_regions

# def is_potential_text_region(data: bytes) -> bool:
#     """Проверка, является ли регион потенциальным хранилищем текста"""
#     printable_count = 0
#     total = len(data)
#
#     if total == 0:
#         return False
#
#     for b in data:
#         if 0x20 <= b <= 0x7E or b in [0x0A, 0x0D]:  # ASCII printable + newlines
#             printable_count += 1
#
#     # Если более 30% символов - печатные, вероятно это текст
#     return (printable_count / total) > 0.3
#
#
# def calculate_confidence(data: bytes) -> float:
#     """Расчет уверенности, что регион содержит текст"""
#     # Более сложный анализ для определения уверенности
#     # ...
#     return 0.0
