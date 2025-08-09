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
from typing import List, Dict


class TextInjector:
    """Внедрение измененного текста обратно в ROM"""

    def __init__(self, rom_path: str):
        if not isinstance(rom_path, str):
            raise TypeError(f"rom_path должен быть строкой, а не {type(rom_path)}")

        self.rom = GameBoyROM(rom_path)
        self.original_data = bytearray(self.rom.data)
        self.modified_data = bytearray(self.rom.data)

    def inject_segment(self, segment_name: str, translations: List[str], plugin) -> bool:
        """
        Внедряет переводы в указанный сегмент
        Возвращает True, если внедрение прошло успешно
        """
        if not plugin:
            return False

        segments = plugin.get_text_segments(self.rom)
        segment = next((s for s in segments if s['name'] == segment_name), None)

        if not segment:
            return False

        # Проверяем, что переводы не длиннее оригинального текста
        original_messages = self._extract_original_messages(segment)

        if len(translations) != len(original_messages):
            return False

        for i, (original, translation) in enumerate(zip(original_messages, translations)):
            # Проверяем длину перевода
            if len(translation) > len(original['text']):
                return False

            # Внедряем перевод
            self._inject_message(segment, original['offset'], translation)

        return True

    def _extract_original_messages(self, segment) -> List[Dict]:
        """Извлекает оригинальные сообщения из сегмента"""
        data = self.rom.data[segment['start']:segment['end']]
        text = segment['decoder'].decode(data, 0, len(data))
        return self._split_messages(text)

    def _split_messages(self, text: str) -> List[Dict]:
        """Разделяет текст на отдельные сообщения"""
        messages = []
        current_message = ""
        offset = 0

        for char in text:
            if char == '\n':
                if current_message:
                    messages.append({
                        'text': current_message,
                        'offset': offset
                    })
                    current_message = ""
                offset += 1
                continue

            current_message += char
            offset += 1

        if current_message:
            messages.append({
                'text': current_message,
                'offset': offset
            })

        return messages

    def _inject_message(self, segment, offset: int, translation: str):
        """Внедряет одно сообщение в ROM"""
        # Преобразуем перевод в байты с использованием декодера
        encoded = segment['decoder'].encode(translation)

        # Вычисляем позицию в ROM
        rom_offset = segment['start'] + offset

        # Заменяем оригинальные байты
        for i, byte in enumerate(encoded):
            if rom_offset + i < len(self.modified_data):
                self.modified_data[rom_offset + i] = byte

    def save(self, output_path: str):
        """Сохраняет модифицированный ROM"""
        with open(output_path, 'wb') as f:
            f.write(self.modified_data)