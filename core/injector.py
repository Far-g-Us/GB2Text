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
import logging

class TextInjector:
    """Внедрение измененного текста обратно в ROM"""

    def __init__(self, rom_path: str):
        if not isinstance(rom_path, str):
            raise TypeError(f"rom_path должен быть строкой, а не {type(rom_path)}")
        self.rom = GameBoyROM(rom_path)
        self.original_data = bytearray(self.rom.data)
        self.modified_data = bytearray(self.rom.data)
        self.logger = logging.getLogger('gb2text.injector')

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

        # Гарантируем наличие decoder
        self._ensure_decoder(segment)
        if not segment.get('decoder'):
            return False

        # Проверяем, что переводы не длиннее оригинального текста
        original_messages = self._extract_original_messages(segment)

        if len(translations) != len(original_messages):
            return False

        enc = segment['decoder'].encode
        for original, translation in zip(original_messages, translations):
        # Сравниваем длину в байтах
            trans_bytes = enc(translation)
            if len(trans_bytes) > original['length']:
                return False

            # Внедряем перевод
            self._inject_message(segment, original['offset'], trans_bytes, original['length'])

        return True


    def _ensure_decoder(self, segment):
        """Гарантирует, что у сегмента есть decoder"""
        if not segment.get('decoder'):
            try:
                from core.scanner import auto_detect_charmap
                from core.decoder import CharMapDecoder
                charmap = auto_detect_charmap(self.rom.data, segment['start'])
                segment['decoder'] = CharMapDecoder(charmap)
            except Exception:
                segment['decoder'] = None

    def _extract_original_messages(self, segment) -> List[Dict]:
        """
        Извлекает оригинальные сообщения из сегмента, считая смещения в БАЙТАХ.
        Разделители: 0x00, 0xFF, 0xFE, 0x0D, 0x0A (терминаторы/переводы строки).
        """
        start = segment['start']
        end = segment['end']
        data = self.rom.data[start:end]
        decoder = segment['decoder']

        msgs: List[Dict] = []
        i = 0
        n = len(data)
        terminators = {0x00, 0xFF, 0xFE, 0x0D, 0x0A}

        while i < n:
            msg_start = i
            # идём до первого терминатора
            while i < n and data[i] not in terminators:
                i += 1

            msg_len = i - msg_start  # длина сообщения в БАЙТАХ (без терминатора)
            if msg_len > 0:
                msg_bytes = bytes(data[msg_start:i])
                try:
                    text = decoder.decode(msg_bytes, 0, len(msg_bytes))
                except Exception:
                    text = ""
                msgs.append({
                    'offset': msg_start,  # смещение в байтах от начала сегмента
                    'length': msg_len,  # длина доступного окна под текст
                    'text': text
                })

            # пропускаем терминатор (1 байт), если он есть
            if i < n:
                i += 1

        return msgs


    def _inject_message(self, segment, offset_bytes: int, data: bytes, orig_len: int):
        """Внедряет байты перевода в ROM, не затрагивая терминатор. Паддинг до прежней длины."""

        # Вычисляем позицию в ROM
        rom_offset = segment['start'] + offset_bytes

        # Заменяем оригинальные байты
        for i, byte in enumerate(data):
            if rom_offset + i < len(self.modified_data):
                self.modified_data[rom_offset + i] = byte

        # Если перевод короче оригинала — дополняем пробелами до orig_len
        pad_len = orig_len - len(data)
        if pad_len > 0:
            pad_byte = 0x20  # пробел по умолчанию
            for k in range(pad_len):
                if rom_offset + len(data) + k < len(self.modified_data):
                    self.modified_data[rom_offset + len(data) + k] = pad_byte

    def save(self, output_path: str):
        """Сохраняет модифицированный ROM"""
        with open(output_path, 'wb') as f:
            f.write(self.modified_data)