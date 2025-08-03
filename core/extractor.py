"""
Модуль для извлечения текста из ROM
"""

from typing import Dict, List
from .rom import GameBoyROM
from .plugin_manager import PluginManager


class TextExtractor:
    """Основной класс извлечения текста"""

    def __init__(self, rom_path: str):
        self.rom = GameBoyROM(rom_path)
        self.plugin_manager = PluginManager()
        self.plugin = self.plugin_manager.get_plugin(self.rom.get_game_id())

    def extract(self) -> Dict[str, List[Dict]]:
        if not self.plugin:
            raise ValueError(f"Не поддерживаемая игра: {self.rom.get_game_id()}")

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
                'offset': start + i * 100,  # Упрощенный пример
                'text': msg
            } for i, msg in enumerate(messages)]

        return results

    def _split_messages(self, text: str) -> List[str]:
        """Разделение текста на отдельные сообщения"""
        # Здесь должна быть логика разделения по терминаторам
        return [m for m in text.split('[END]') if m.strip()]