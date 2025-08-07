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
Модуль для извлечения текста из ROM
"""


from typing import Dict, List
from core.rom import GameBoyROM
from core.plugin_manager import PluginManager
from core.guide import GuideManager


class TextExtractor:
    """Основной класс извлечения текста"""

    def __init__(self, rom_path: str, plugin_manager=None, guide_manager=None):
        self.rom = GameBoyROM(rom_path)
        self.plugin_manager = plugin_manager or PluginManager()
        self.guide_manager = guide_manager or GuideManager()
        self.plugin = self.plugin_manager.get_plugin(self.rom.get_game_id())
        self.guide = self.guide_manager.get_guide(self.rom.get_game_id())

    def extract(self) -> Dict[str, List[Dict]]:
        if not self.plugin:
            raise ValueError(f"Не поддерживаемая игра: {self.rom.get_game_id()}")

        # Применение рекомендаций из руководства, если они есть
        self._apply_guide_recommendations()

        results = {}
        for segment in self.plugin.get_text_segments(self.rom):
            name = segment['name']
            start = segment['start']
            end = segment['end']

            # Обработка сжатия если необходимо
            data = self.rom.data[start:end]
            if segment.get('compression'):
                decompressed, _ = segment['compression'].decompress(data, 0)
                data = decompressed

            # Декодирование текста
            text = segment['decoder'].decode(data, 0, len(data))

            # Разделение на отдельные сообщения
            messages = self._split_messages(text)

            results[name] = [{
                'offset': start + i * 100,
                'text': msg
            } for i, msg in enumerate(messages)]

        return results

    def _split_messages(self, text: str) -> List[str]:
        """Разделение текста на отдельные сообщения"""
        # Здесь должна быть логика разделения по терминаторам
        return [m for m in text.split('[END]') if m.strip()]

    def _apply_guide_recommendations(self):
        """Применяет рекомендации из руководства к плагину"""
        if not self.guide:
            return

        # Пример применения рекомендаций
        recommendations = self.guide.get('recommendations', {})

        if 'decoder_adjustments' in recommendations:
            for seg_name, adjustments in recommendations['decoder_adjustments'].items():
                for segment in self.plugin.get_text_segments(self.rom):
                    if segment['name'] == seg_name and segment['decoder']:
                        # Применение корректировок к декодеру
                        self._adjust_decoder(segment['decoder'], adjustments)

    def _adjust_decoder(self, decoder, adjustments):
        """Корректирует декодер согласно рекомендациям"""
        if hasattr(decoder, 'charmap') and 'charmap' in adjustments:
            # Применение изменений к таблице символов
            for byte_str, char in adjustments['charmap'].items():
                try:
                    byte = int(byte_str, 16)
                    decoder.charmap[byte] = char
                except ValueError:
                    pass