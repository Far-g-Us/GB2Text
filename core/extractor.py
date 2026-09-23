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

from core.guide import GuideManager
from core.plugin_manager import CancellationToken, PluginManager
from core.rom import GameBoyROM


class TextExtractor:
    """Основной класс извлечения текста"""

    def __init__(self, rom_path: str, plugin_manager=None, guide_manager=None, cancellation_token: CancellationToken | None = None, max_segments: int | None = None, rom: GameBoyROM | None = None, progress_callback=None):
        if not isinstance(rom_path, str):
            raise TypeError("rom_path должен быть строкой, а не типом")

        if rom is not None:
            self.rom = rom
        else:
            self.rom = GameBoyROM(rom_path)
        self.plugin_manager = plugin_manager or PluginManager()
        self.cancellation_token = cancellation_token
        self.plugin = None
        self.current_results = None
        self.guide_manager = guide_manager or GuideManager()
        self.guide = self.guide_manager.get_guide(self.rom.get_game_id())
        self.i18n = None
        self.max_segments = max_segments
        self.progress_callback = progress_callback

    def _t(self, key: str, default: str = '') -> str:
        """Безопасный вызов перевода"""
        if self.i18n is not None:
            try:
                return self.i18n.t(key)
            except Exception:
                return default
        return default

    def _report_progress(self, message: str, percent: int):
        """Единая точка отчёта о прогрессе"""
        if self.progress_callback:
            self.progress_callback(message, percent)
        elif hasattr(self.plugin_manager, 'update_status'):
            self.plugin_manager.update_status(message, percent)

    def extract(self) -> dict[str, list[dict]]:
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
        self._report_progress(self._t("plugin.searching"), 5)

        # Передаем cancellation_token в plugin_manager
        self.plugin = self.plugin_manager.get_plugin(game_id, system, self.cancellation_token, rom=self.rom)

        if not self.plugin:
            logger.error(f"Не поддерживаемая игра: {game_id}")
            self._report_progress(
                    self._t("plugin.not.found"),
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
        self._report_progress(
            f"{self._t('segments.found')} {len(segments)}",
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

            # Fixed-width слотовая таблица (имена/атаки): каждая запись —
            # ячейка фиксированной ширины, а не сплошной поток терминаторов.
            if segment.get('fixed_width'):
                messages = self._extract_fixed_width_messages(segment)
                logger.info(
                    f"Извлечено {len(messages)} сообщений из сегмента '{name}' "
                    f"(fixed_width={segment['fixed_width']})")
                results[name] = messages
                if len(segments_to_process) > 0:
                    progress = 20 + int(75 * (i + 1) / len(segments_to_process))
                else:  # pragma: no cover - недостижимо: цикл не выполняется на пустом списке
                    progress = 95
                self._report_progress(
                    f"{self._t('processing.segment')} {i + 1}/{len(segments_to_process)}: {name}",
                    progress)
                continue

            # Pointer-управляемый пул диалогов (Pokemon GBA): каждая строка —
            # отдельный target-адрес из манифеста, декодер вызывается на месте.
            if segment.get('kind') == 'pointer_dialogues':
                messages = self._extract_pointer_dialogues(segment)
                logger.info(
                    f"Извлечено {len(messages)} сообщений из сегмента '{name}' "
                    f"(pointer_dialogues)")
                results[name] = messages
                if len(segments_to_process) > 0:
                    progress = 20 + int(75 * (i + 1) / len(segments_to_process))
                else:  # pragma: no cover - недостижимо: цикл не выполняется на пустом списке
                    progress = 95
                self._report_progress(
                    f"{self._t('processing.segment')} {i + 1}/{len(segments_to_process)}: {name}",
                    progress)
                continue

            # Обработка сжатия если необходимо
            # Если сегмент уже содержит декодированный текст (raw_text), используем его напрямую
            raw_text = segment.get('raw_text')
            if raw_text is not None:
                text = raw_text
                logger.info(f"Использован предварительно декодированный текст: {len(text)} символов")
            else:
                data = self.rom.data[start:end]
                data = self._decompress(data, segment.get('compression'))

                # Декодирование текста
                if not segment['decoder']:
                    logger.info("Таблица символов не предоставлена, определяем автоматически")
                    from core.scanner import auto_detect_charmap
                    charmap = auto_detect_charmap(
                        self.rom.data, start, prefer_lang=segment.get('lang'))
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
            if len(segments_to_process) > 0:
                progress = 20 + int(75 * (i + 1) / len(segments_to_process))
            else:  # pragma: no cover - недостижимо: цикл не выполняется на пустом списке
                progress = 95
            self._report_progress(
                f"{self._t('processing.segment')} {i + 1}/{len(segments_to_process)}: {name}",
                progress
            )

        self.current_results = results
        logger.info(f"Извлечение текста завершено. Найдено {len(results)} сегментов.")

        # Финальное обновление статуса
        self._report_progress(
            self._t("text.extracted"),
            100
        )

        return results

    def _extract_pointer_dialogues(self, segment: dict) -> list[dict]:
        """Декодирует каждую строку pointer-пула из манифеста по её target.

        Сообщения получают 'target_addr'/'length'/'slots' для in-place
        вставки; 'offset' продублирован для совместимости с GUI.
        """
        logger = logging.getLogger('gb2text.extractor')
        decoder = segment.get('decoder')
        if decoder is None:
            logger.error("pointer_dialogues требует явный decoder")
            return []
        data = self.rom.data
        manifest = segment.get('manifest') or []
        messages: list[dict] = []
        for entry in manifest:
            addr = entry.get('target')
            if not isinstance(addr, int) or not (0 <= addr < len(data)):
                continue
            try:
                max_decode = min(segment.get('max_decode_len', 320),
                                 entry.get('free_after', 320),
                                 len(data) - addr)
                text = decoder.decode(data, addr, max_decode)
            except Exception as exc:
                logger.warning(f"Диалог 0x{addr:X}: сбой декодирования ({exc}), пропущен")
                continue
            if not text.strip():
                continue
            messages.append({
                'text': text,
                'offset': addr,
                'target_addr': addr,
                'length': entry['free_after'],
                'slots': entry.get('slots', []),
            })
        return messages

    def _decompress(self, data: bytes, compression) -> bytes:
        """Распаковывает данные сегмента, если задан тип сжатия"""
        logger = logging.getLogger('gb2text.extractor')
        if not compression:
            return data
        if isinstance(compression, str):
            from core.compression import get_compression_handler
            handler = get_compression_handler(compression)
            if handler:
                logger.info(f"Распаковка: {compression}")
                try:
                    decompressed, _ = handler.decompress(data, 0)
                    assert isinstance(decompressed, bytes)
                    return decompressed
                except Exception as e:
                    # Часть обработчиков требует контекст ROM (tree_base/tree_data
                    # у Huffman), недоступный через decompress(data, 0). Падать из-за
                    # одного несжимаемого сегмента нельзя — пропускаем с предупреждением.
                    logger.warning(
                        f"Распаковка '{compression}' недоступна в этом контексте: {e}")
            else:
                logger.warning(f"Неизвестный тип сжатия: {compression}")
        elif hasattr(compression, 'decompress'):
            logger.info("Распаковка (объект)")
            try:
                decompressed, _ = compression.decompress(data, 0)
                assert isinstance(decompressed, bytes)
                return decompressed
            except Exception as e:
                logger.warning(f"Ошибка распаковки: {e}")
        return data

    def recode_segment(self, segment: dict, decoder) -> list[dict]:
        """
        Перекодирует ОДИН сегмент указанным декодером и возвращает сообщения.

        Используется GUI при смене кодировки/тумблера неизвестных байтов.
        Позволяет перекодировать только текущий сегмент — переводы,
        введённые в остальных сегментах, сохраняются.
        """
        logger = logging.getLogger('gb2text.extractor')
        start = segment['start']
        end = segment['end']
        if start >= len(self.rom.data) or end > len(self.rom.data) or start >= end:
            logger.error(
                f"Сегмент с недопустимыми адресами: start=0x{start:X}, end=0x{end:X}, размер ROM={len(self.rom.data)}")
            return []
        if segment.get('fixed_width'):
            return self._extract_fixed_width_messages(segment, decoder)
        data = self._decompress(self.rom.data[start:end], segment.get('compression'))
        text = decoder.decode(data, 0, len(data))
        return self._split_messages(text, start)

    def _split_messages(self, text: str, base_offset: int) -> list[dict]:
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

    def _extract_fixed_width_messages(self, segment: dict, decoder=None) -> list[dict]:
        """Разбиение fixed-width слотовой таблицы на сообщения (байтовый уровень).

        Сегмент должен иметь 'fixed_width' (ширина слота) и 'record_count'.
        Каждый слот: data[start + i*W : start + (i+1)*W]. Текст слота — до
        первого 0xFF (декодер сам останавливается на терминаторе); 0x00 внутри
        слота — пробел, а не разделитель. Пустые слоты ('?'-паддинг)
        пропускаются, но offset сохраняет абсолютную позицию слота,
        чтобы инжектор мог писать на свои места.
        """
        width = segment['fixed_width']
        count = segment['record_count'] if 'record_count' in segment else (
            (segment['end'] - segment['start']) // width if width else 0)
        start = segment['start']
        if decoder is None:
            decoder = segment.get('decoder')
        data = self.rom.data

        messages: list[dict] = []
        for i in range(count):
            slot_start = start + i * width
            if slot_start + width > len(data):
                break
            slot_bytes = data[slot_start:slot_start + width]
            if decoder is not None:
                try:
                    text = decoder.decode(slot_bytes, 0, len(slot_bytes))
                except Exception as exc:
                    logging.getLogger('gb2text.extractor').warning(
                        f"Слот 0x{slot_start:X}: сбой декодирования ({exc}), пропущен")
                    text = ""
            else:
                text = ""
            if text.strip("-? ") == "":
                continue
            messages.append({
                'offset': slot_start,
                'text': text,
            })
        return messages

    def _apply_guide_recommendations(self):
        """Применяет рекомендации из руководства к плагину"""
        if not self.guide:
            return
        assert self.plugin is not None

        # Пример применения рекомендаций
        recommendations = self.guide.get('recommendations', {})

        if 'decoder_adjustments' in recommendations:
            for seg_name, adjustments in recommendations['decoder_adjustments'].items():  # pragma: no branch - arc выхода через исключение в заголовке for не фиксируется замером (исполнение доказано мутацией в test_extractor_guide_not_dict)
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
