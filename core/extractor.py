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

import logging
from typing import Dict, List
from core.rom import GameBoyROM
from core.plugin_manager import PluginManager
from core.guide import GuideManager
from core.scanner import analyze_text_segment

class TextExtractor:
    """Основной класс извлечения текста"""

    def __init__(self, rom_path: str, plugin_manager=None, guide_manager=None):
        if not isinstance(rom_path, str):
            raise TypeError("rom_path должен быть строкой, а не типом")

        self.rom = GameBoyROM(rom_path)
        self.plugin_manager = plugin_manager or PluginManager()
        self.guide_manager = guide_manager or GuideManager()
        self.plugin = None
        self.current_results = None
        self.guide = self.guide_manager.get_guide(self.rom.get_game_id())

    def extract(self) -> Dict[str, List[Dict]]:
        """Извлекает текст из ROM"""
        logger = logging.getLogger('gb2text.extractor')
        logger.info("Начало процесса извлечения текста")

        if not self.rom:
            logger.error("ROM не загружен")
            raise ValueError("ROM не загружен")

        # Определяем систему
        system = self.rom.system
        logger.info(f"Определена система: {system}")

        # Получаем плагин с учетом системы
        game_id = self.rom.get_game_id()
        logger.info(f"Идентификатор игры: {game_id}")

        self.plugin = self.plugin_manager.get_plugin(game_id, system)

        if not self.plugin:
            logger.error(f"Не поддерживаемая игра: {game_id}")
            raise ValueError(f"Не поддерживаемая игра: {game_id}")

        results = {}
        segments = self.plugin.get_text_segments(self.rom)

        # Обрабатываем сегменты пакетами для повышения производительности
        batch_size = 5
        for i in range(0, len(segments), batch_size):
            batch = segments[i:i + batch_size]
            logger.info(f"Обработка пакета сегментов {i // batch_size + 1}/{(len(segments) - 1) // batch_size + 1}")

            for segment in batch:
                name = segment['name']
                start = segment['start']
                end = segment['end']

                logger.debug(f"Обработка сегмента '{name}': 0x{start:X} - 0x{end:X}")

                # Проверяем, что адреса в пределах ROM
                if start >= len(self.rom.data) or end > len(self.rom.data) or start >= end:
                    logger.error(
                        f"Пропущен сегмент с недопустимыми адресами: start=0x{start:X}, end=0x{end:X}, размер ROM={len(self.rom.data)}")
                    continue

                # Обработка сжатия если необходимо
                data = self.rom.data[start:end]
                if segment.get('compression') == 'gba_lz77':
                    logger.debug("Распаковка GBA LZ77 сжатия")
                    from core.gba_support import GBALZ77Handler
                    handler = GBALZ77Handler()
                    decompressed, _ = handler.decompress(data, 0)
                    data = decompressed
                elif segment.get('compression'):
                    logger.debug(f"Распаковка {segment['compression']}")
                    decompressed, _ = segment['compression'].decompress(data, 0)
                    data = decompressed

                # Декодирование текста
                if not segment['decoder']:
                    logger.debug("Таблица символов не предоставлена, определяем автоматически")
                    from core.scanner import auto_detect_charmap
                    charmap = auto_detect_charmap(self.rom.data, start)
                    from core.decoder import CharMapDecoder
                    segment['decoder'] = CharMapDecoder(charmap)

                logger.debug("Декодирование текста")
                text = segment['decoder'].decode(data, 0, len(data))

                # Разделение на отдельные сообщения
                logger.debug("Разделение на отдельные сообщения")
                messages = self._split_messages(text, start)

                results[name] = messages
                logger.debug(f"Извлечено {len(messages)} сообщений из сегмента '{name}'")

        self.current_results = results
        logger.info(f"Извлечение текста завершено. Найдено {len(results)} сегментов.")

        return results

    def _split_messages(self, text: str, base_offset: int) -> List[Dict]:
        """Разделение на отдельные сообщения"""
        messages = []
        current_msg = ""
        offset = 0
        start_offset = 0

        for i, char in enumerate(text):
            if char == '\n' or char == '[END]':
                if current_msg:
                    messages.append({
                        'offset': base_offset + start_offset,
                        'text': current_msg
                    })
                    current_msg = ""
                start_offset = i + 1
            else:
                current_msg += char

        if current_msg:
            messages.append({
                'offset': base_offset + start_offset,
                'text': current_msg
            })

        return messages

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