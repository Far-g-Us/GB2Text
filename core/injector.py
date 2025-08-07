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
Модуль для внедрения текста обратно в ROM
"""

from core.rom import GameBoyROM
from core.decoder import CharMapDecoder, TextDecoder
from typing import List


class TextInjector:
    """Внедрение измененного текста обратно в ROM"""

    def __init__(self, rom_path: str):
        self.rom = GameBoyROM(rom_path)
        self.backup = bytearray(self.rom.data)
        self.changes = []

    def inject_segment(self, segment_name: str, new_texts: List[str], plugin) -> bool:
        """Внедрение измененных текстов в указанный сегмент"""
        segments = plugin.get_text_segments(self.rom)
        target_segment = next((s for s in segments if s['name'] == segment_name), None)

        if not target_segment:
            return False

        decoder = target_segment['decoder']
        start = target_segment['start']
        end = target_segment['end']

        # Проверяем, можем ли мы заменить текст
        if not self._can_replace_text(start, end, new_texts, decoder):
            return False

        # Выполняем замену
        self._replace_text(start, new_texts, decoder)
        self.changes.append({
            'segment': segment_name,
            'start': start,
            'original': self.backup[start:start + (end - start)],
            'new': self.rom.data[start:start + (end - start)]
        })

        return True

    def _can_replace_text(self, start: int, end: int, new_texts: List[str],
                          decoder: TextDecoder) -> bool:
        """Проверка, подходит ли новый текст по размеру"""
        # В простом случае проверяем, что общий размер не превышает оригинальный
        total_size = 0
        for text in new_texts:
            total_size += self._calculate_encoded_size(text, decoder)

        return total_size <= (end - start)

    def _calculate_encoded_size(self, text: str, decoder: TextDecoder) -> int:
        """Расчет размера закодированного текста"""
        # Для простоты предполагаем, что каждый символ занимает 1 байт
        # В реальности может быть сложнее в зависимости от кодировки
        return len(text)

    def _replace_text(self, start: int, new_texts: List[str], decoder: TextDecoder):
        """Замена текста в ROM"""
        current_pos = start

        for text in new_texts:
            # Кодируем текст обратно в байты
            encoded = self._encode_text(text, decoder)

            # Заменяем в ROM
            for i, byte in enumerate(encoded):
                self.rom.data[current_pos + i] = byte

            current_pos += len(encoded)

    def _encode_text(self, text: str, decoder: TextDecoder) -> bytes:
        """Кодирование текста в байты согласно таблице символов"""
        if isinstance(decoder, CharMapDecoder):
            # Обратное преобразование через таблицу символов
            reverse_map = {v: k for k, v in decoder.charmap.items()}
            result = []

            for char in text:
                if char in reverse_map:
                    result.append(reverse_map[char])
                else:
                    # Используем пробел или первый неизвестный символ
                    result.append(reverse_map.get(' ', 0x20))

            return bytes(result)

        # Для других декодеров потребуется специальная обработка
        return text.encode('ascii', 'ignore')

    def save(self, output_path: str) -> bool:
        """Сохранение измененной ROM"""
        with open(output_path, 'wb') as f:
            f.write(self.rom.data)
        return True

    def revert(self):
        """Возврат к оригинальной ROM"""
        self.rom.data = bytearray(self.backup)
        self.changes = []

    def get_change_log(self) -> list:
        """Получение журнала изменений"""
        return self.changes