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
from typing import Dict, List, Optional
from core.rom import GameBoyROM
from core.plugin_manager import PluginManager, CancellationToken
from core.guide import GuideManager


class TextExtractor:
    """Основной класс извлечения текста"""

    def __init__(self, rom_path: str, plugin_manager=None, guide_manager=None, cancellation_token: Optional[CancellationToken] = None, max_segments: int = None):
        if not isinstance(rom_path, str):
            raise TypeError("rom_path должен быть строкой, а не типом")

        self.rom = GameBoyROM(rom_path)
        self.plugin_manager = plugin_manager or PluginManager()
        self.cancellation_token = cancellation_token
        self.plugin = None
        self.current_results = None
        self.guide_manager = guide_manager or GuideManager()
        self.guide = self.guide_manager.get_guide(self.rom.get_game_id())
        self.i18n = None
        self.max_segments = max_segments

    def extract(self) -> Dict[str, List[Dict]]:
        """Извлекает текст из ROM"""
        logger = logging.getLogger('gb2text.extractor')
        logger.info("Начало процесса извлечения текста")

        if not self.rom:
            logger.error("ROM не загружен")
            raise ValueError("ROM не загружен")

        # Проверяем, запрошена ли отмена
        if self.cancellation_token and self.cancellation_token.is_cancellation_requested():
            logger.info("Извлечение текста отменено")
            return {}

        # Определяем систему
        system = self.rom.system
        logger.info(f"Определена система: {system}")

        # Получаем плагин с учетом системы
        game_id = self.rom.get_game_id()
        logger.info(f"Идентификатор игры: {game_id}")

        # Обновляем статус в GUI, если доступен
        if hasattr(self.plugin_manager, 'update_status'):
            self.plugin_manager.update_status(self.i18n.t("plugin.searching"), 5)

        # Передаем cancellation_token в plugin_manager
        self.plugin = self.plugin_manager.get_plugin(game_id, system, self.cancellation_token)

        if not self.plugin:
            logger.error(f"Не поддерживаемая игра: {game_id}")
            if hasattr(self.plugin_manager, 'update_status'):
                self.plugin_manager.update_status(
                    self.i18n.t("plugin.not.found"),
                    100
                )
            raise ValueError(f"Не поддерживаемая игра: {game_id}")

        # Проверяем, запрошена ли отмена
        if self.cancellation_token and self.cancellation_token.is_cancellation_requested():
            logger.info("Извлечение текста отменено")
            return {}

        results = {}
        segments = self.plugin.get_text_segments(self.rom)

        logger.info(f"Найдено {len(segments)} текстовых сегментов для обработки")

        # Обновляем статус
        if hasattr(self.plugin_manager, 'update_status'):
            self.plugin_manager.update_status(
                f"{self.i18n.t('segments.found')} {len(segments)}",
                15
            )

        # Применяем ограничение только если задано
        if self.max_segments and len(segments) > self.max_segments:
            segments_to_process = segments[:self.max_segments]
            logger.warning(f"Ограничено до {self.max_segments} сегментов из {len(segments)}")
        else:
            segments_to_process = segments

        # Обрабатываем сегменты по одному с обновлением прогресса
        for i, segment in enumerate(segments_to_process):
            name = segment['name']
            start = segment['start']
            end = segment['end']

            logger.info(f"Обработка сегмента '{name}': 0x{start:X} - 0x{end:X}")

            # Проверяем, что адреса в пределах ROM
            if start >= len(self.rom.data) or end > len(self.rom.data) or start >= end:
                logger.error(
                    f"Пропущен сегмент с недопустимыми адресами: start=0x{start:X}, end=0x{end:X}, размер ROM={len(self.rom.data)}")
                continue

            # Проверяем, запрошена ли отмена
            if self.cancellation_token and self.cancellation_token.is_cancellation_requested():
                logger.info("Извлечение текста отменено")
                return {}

            # Обработка сжатия если необходимо
            data = self.rom.data[start:end]
            if segment.get('compression'):
                compression_type = segment.get('compression')
                if isinstance(compression_type, str):
                    from core.compression import get_compression_handler
                    handler = get_compression_handler(compression_type)
                    if handler:
                        logger.info(f"Распаковка: {compression_type}")
                        decompressed, _ = handler.decompress(data, 0)
                        data = decompressed
                    else:
                        logger.warning(f"Неизвестный тип сжатия: {compression_type}")
                elif hasattr(compression_type, 'decompress'):
                    logger.info("Распаковка (объект)")
                    decompressed, _ = compression_type.decompress(data, 0)
                    data = decompressed

            # Декодирование текста
            if not segment['decoder']:
                logger.info("Таблица символов не предоставлена, определяем автоматически")
                from core.scanner import auto_detect_charmap
                charmap = auto_detect_charmap(self.rom.data, start)
                from core.decoder import CharMapDecoder
                segment['decoder'] = CharMapDecoder(charmap)

            logger.info("Декодирование текста")
            text = segment['decoder'].decode(data, 0, len(data))

            # Проверка качества декодирования
            unknown_chars = text.count('[')
            total_chars = len(text)
            if total_chars > 0:
                quality = 1.0 - (unknown_chars / total_chars)
                logger.info(f"Качество декодирования для сегмента {name}: {quality:.2%}")

                # Если качество низкое, добавляем предупреждение
                if quality < 0.5:
                    logger.warning(f"Низкое качество декодирования для сегмента {name}")

            # Разделение на отдельные сообщения
            logger.info("Разделение на отдельные сообщения")
            messages = self._split_messages(text, start)

            results[name] = messages
            logger.info(f"Извлечено {len(messages)} сообщений из сегмента '{name}'")

            # Обновляем прогресс
            progress = 20 + int(75 * (i + 1) / len(segments_to_process))
            if hasattr(self.plugin_manager, 'update_status'):
                self.plugin_manager.update_status(
                    f"{self.i18n.t('processing.segment')} {i + 1}/{len(segments_to_process)}: {name}",
                    progress
                )

        self.current_results = results
        logger.info(f"Извлечение текста завершено. Найдено {len(results)} сегментов.")

        # Финальное обновление статуса
        if hasattr(self.plugin_manager, 'update_status'):
            self.plugin_manager.update_status(
                self.i18n.t("text.extracted"),
                100
            )

        return results

    def _split_messages(self, text: str, base_offset: int) -> List[Dict]:
        """Разделение на отдельные сообщения с улучшенной обработкой"""
        logger = logging.getLogger('gb2text.extractor')
        logger.debug(f"Начало разделения текста (длина: {len(text)})")

        messages = []
        current_msg = ""
        current_offset = base_offset
        i = 0

        while i < len(text):
            char = text[i]

            # Обработка специальных последовательностей
            if i + 4 < len(text) and text[i:i + 5] == '[END]':
                if current_msg:
                    messages.append({
                        'offset': current_offset,
                        'text': current_msg
                    })
                    logger.debug(f"Найдено сообщение длиной {len(current_msg)}")
                current_msg = ""
                current_offset = base_offset + i + 5
                i += 5
                continue

            # Обработка шестнадцатеричных кодов вида [XX]
            elif char == '[' and i + 3 < len(text) and text[i + 3] == ']':
                hex_part = text[i + 1:i + 3]
                if all(c in '0123456789ABCDEFabcdef' for c in hex_part):
                    # Это шестнадцатеричный код, возможно, терминатор
                    i += 4  # Пропускаем [XX]
                    if current_msg:
                        messages.append({
                            'offset': current_offset,
                            'text': current_msg
                        })
                        logger.debug(f"Найдено сообщение длиной {len(current_msg)}")
                        current_msg = ""
                    current_offset = base_offset + i
                    continue

            # Разделение по переводу строки — синхронизация с инжектором
            if char == '\n':
                if current_msg:
                    messages.append({
                        'offset': current_offset,
                        'text': current_msg
                    })
                    logger.debug(f"Найдено сообщение длиной {len(current_msg)}")
                    current_msg = ""
                i += 1
                current_offset = base_offset + i
                continue

            # Обработка обычного символа
            current_msg += char
            i += 1

        # Добавляем последнее сообщение, если оно есть
        if current_msg:
            messages.append({
                'offset': current_offset,
                'text': current_msg
            })
            logger.debug(f"Найдено последнее сообщение длиной {len(current_msg)}")

        logger.info(f"Разделено на {len(messages)} сообщений")
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