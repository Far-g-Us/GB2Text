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

from core.constants import RomData
from core.guide import GuideManager
from core.plugin_api import GamePlugin
from core.plugin_manager import CancellationToken, PluginManager
from core.rom import GameBoyROM

# Указатели диалогов в ROM — GBA-адреса (0x08xxxxxx), а в манифесте лежат
# сырые смещения в файле. При чтении слота базу нужно снять, иначе любой
# валидный адрес выглядит «вне ROM».
_GBA_ROM_BASE = 0x08000000
_BLANK_PROBE = 32  # сколько байт опрашиваем, чтобы признать блок пустым


def _relocated_dialogue_addr(data, entry: dict, addr: int):
    """Новый адрес блока, если он был перенесён; иначе None.

    Перенос узнаётся по ДВУМ независимым признакам, и оба нужны:

      - слот указывает не на `target` манифеста (указатель переписан);
      - старый блок освобождён инжектором (забит нулями).

    Второй признак обязателен: на ROM-хаках слоты расходятся с манифестом
    УЖЕ на чистой ROM, и без проверки пустоты мы бы сочли переносом то, что
    переносом не является, сломав даже identity-проход.
    """
    if entry.get('relocated_from') is not None:
        return None  # цель уже разрешена вызывающим кодом
    slots = entry.get('slots')
    if not isinstance(slots, list) or not slots:
        return None
    room = entry.get('free_after')
    if isinstance(room, bool) or not isinstance(room, int) or room <= 0:
        room = _BLANK_PROBE
    probe = min(room, _BLANK_PROBE)
    if not all(b == 0 for b in bytes(data[addr:addr + probe])):
        return None  # старый блок на месте — это не перенос
    for slot in slots:
        if not isinstance(slot, int) or isinstance(slot, bool):
            continue
        # GB/GBC: слот 16-битный, значение отсчитывается от базы группы.
        # GBA: слот 32-битный, значение — линейный адрес с базой 0x08.
        slot_size = entry.get('slot_size', 4)
        raw_base = entry.get('reloc_base')
        gbc = slot_size == 2 and not isinstance(raw_base, bool) \
            and isinstance(raw_base, int)
        width = 2 if gbc else 4
        base = 0 if raw_base is None or isinstance(raw_base, bool) else int(raw_base)
        if slot < 0 or slot + width > len(data):
            continue
        live = int.from_bytes(data[slot:slot + width], 'little')
        moved = live + base if gbc else (
            live - _GBA_ROM_BASE if live >= _GBA_ROM_BASE else live)
        if moved <= 0 or moved >= len(data) or moved == addr:
            continue
        return moved
    return None


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
        self.plugin: GamePlugin | None = None
        self.current_results: dict[str, list[dict]] | None = None
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
        found = self.plugin_manager.get_plugin(game_id, system,
                                         self.cancellation_token,
                                         rom=self.rom)
        self.plugin = found

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
            if not isinstance(segment, dict):
                logger.error("Пропущен битый сегмент (не dict)")
                continue
            name = segment.get('name')
            start = segment.get('start')
            end = segment.get('end')
            if not isinstance(name, str) or isinstance(start, bool) or not isinstance(start, int) \
                    or isinstance(end, bool) or not isinstance(end, int):
                logger.error("Пропущен сегмент с битыми name/start/end")
                continue

            logger.info(f"Обработка сегмента '{name}': 0x{start:X} - 0x{end:X}")

            # Проверяем, что адреса в пределах ROM
            if start >= len(self.rom.data) or end > len(self.rom.data) or start >= end \
                    or start < 0 or end < 0:
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

            # Record-сегмент (CVAS/M&L и подобные): одна запись — одно
            # сообщение целиком, без сплита. Нужно блочной вставке
            # (language_block/interleaved ждут тексты уровня записей).
            if segment.get('kind') == 'record':
                raw_text = segment.get('raw_text')
                if raw_text is None:
                    window_bytes = self.rom.data[start:end]
                    data = self._decompress(window_bytes,
                                         segment.get('compression'))
                    decoder = segment.get('decoder')
                    if decoder is None:
                        logger.warning(f"Запись '{name}': нет текста и декодера, пропуск")
                        continue
                    try:
                        raw_text = decoder.decode(data, 0, len(data))
                    except Exception as exc:
                        logger.warning(f"Запись '{name}': сбой декодирования ({exc}), пропуск")
                        continue
                if not isinstance(raw_text, str):
                    logger.warning(f"Запись '{name}': raw_text не строка, пропуск")
                    continue
                results[name] = [{'offset': start, 'text': raw_text}]
                logger.info(f"Извлечена 1 запись из сегмента '{name}' (record)")
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
                window_bytes = self.rom.data[start:end]
                data = self._decompress(window_bytes,
                                     segment.get('compression'))

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

        self.current_results = dict(results)
        logger.info(f"Извлечение текста завершено. Найдено {len(results)} сегментов.")

        # Финальное обновление статуса
        self._report_progress(
            self._t("text.extracted"),
            100
        )

        return results

    def _extract_pointer_dialogues(self, segment: dict, decoder=None) -> list[dict]:
        """Декодирует каждую строку pointer-пула из манифеста по её target.

        Сообщения получают 'target_addr'/'length'/'slots' для in-place
        вставки; 'offset' продублирован для совместимости с GUI.
        decoder по умолчанию — из сегмента (переопределяется recode).
        """
        logger = logging.getLogger('gb2text.extractor')
        if decoder is None:
            decoder = segment.get('decoder')
        if decoder is None:
            logger.error("pointer_dialogues требует явный decoder")
            return []
        data = self.rom.data
        manifest = segment.get('manifest') or []
        messages: list[dict] = []
        for entry in manifest:
            if not isinstance(entry, dict):
                continue
            addr = entry.get('target')
            if not isinstance(addr, int) or isinstance(addr, bool) or not (0 <= addr < len(data)):
                continue
            try:
                max_decode = segment.get('max_decode_len', 320)
                if isinstance(max_decode, bool) or not isinstance(max_decode, int):
                    max_decode = 320
                free_after = entry.get('free_after', 320)
                if isinstance(free_after, bool) or not isinstance(free_after, int):
                    free_after = 320
                # Перенос диалога: инжектор переписал слот и ОСВОБОДИЛ старый
                # блок (забил его нулями). Манифест статичен, поэтому его
                # target устарел, и простое чтение по нему вернуло бы
                # оригинал. Признак переноса — старый блок пуст; тогда идём
                # по указателю.
                relocated = False
                moved = _relocated_dialogue_addr(data, entry, addr)
                if moved is not None:
                    addr, relocated = moved, True
                if relocated:
                    # Длина перенесённого блока не равна free_after: тот
                    # описывает ОРИГИНАЛЬНОЕ окно, а перенос может быть длиннее.
                    # Резать по нему нельзя — терялся последний символ.
                    max_decode = min(max_decode, len(data) - addr)
                else:
                    max_decode = min(max_decode, free_after, len(data) - addr)
                text = decoder.decode(data, addr, max_decode)
            except Exception as exc:
                logger.warning(f"Диалог 0x{addr:X}: сбой декодирования ({exc}), пропущен")
                continue
            if not text.strip():
                continue
            length = entry.get('free_after')
            if isinstance(length, bool) or not isinstance(length, int):
                continue
            messages.append({
                'text': text,
                'offset': addr,
                'target_addr': addr,
                'length': length,
                'slots': entry.get('slots', []),
            })
        return messages

    def _decompress(self, data: RomData, compression) -> bytes:
        """Распаковывает данные сегмента, если задан тип сжатия"""
        logger = logging.getLogger('gb2text.extractor')
        if not compression:
            return bytes(data)
        if isinstance(compression, str):
            from core.compression import get_compression_handler
            handler = get_compression_handler(compression)
            if handler:
                logger.info(f"Распаковка: {compression}")
                try:
                    decompressed, _ = handler.decompress(bytes(data), 0)
                except Exception as e:
                    # Часть обработчиков требует контекст ROM (tree_base/tree_data
                    # у Huffman), недоступный через decompress(data, 0). Падать из-за
                    # одного несжимаемого сегмента нельзя — пропускаем с предупреждением.
                    logger.warning(
                        f"Распаковка '{compression}' недоступна в этом контексте: {e}")
                    return bytes(data)
                if not isinstance(decompressed, (bytes, bytearray)):
                    logger.warning(f"Распаковка '{compression}' вернула не-байты")
                    return bytes(data)
                return bytes(decompressed)
            else:
                logger.warning(f"Неизвестный тип сжатия: {compression}")
        elif hasattr(compression, 'decompress'):
            logger.info("Распаковка (объект)")
            try:
                decompressed, _ = compression.decompress(data, 0)
            except Exception as e:
                logger.warning(f"Ошибка распаковки: {e}")
                return bytes(data)
            if not isinstance(decompressed, (bytes, bytearray)):
                logger.warning("Распаковка (объект) вернула не-байты")
                return bytes(data)
            return bytes(decompressed)
        return bytes(data)

    def recode_segment(self, segment: dict, decoder) -> list[dict]:
        """
        Перекодирует ОДИН сегмент указанным декодером и возвращает сообщения.

        Используется GUI при смене кодировки/тумблера неизвестных байтов.
        Позволяет перекодировать только текущий сегмент — переводы,
        введённые в остальных сегментах, сохраняются.
        """
        logger = logging.getLogger('gb2text.extractor')
        start = segment.get('start')
        end = segment.get('end')
        if (isinstance(start, bool) or not isinstance(start, int)
                or start < 0
                or isinstance(end, bool) or not isinstance(end, int)
                or end < 0):
            logger.error("Сегмент с битыми start/end")
            return []
        if start >= len(self.rom.data) or end > len(self.rom.data) or start >= end:
            logger.error(
                f"Сегмент с недопустимыми адресами: start=0x{start:X}, end=0x{end:X}, размер ROM={len(self.rom.data)}")
            return []
        if segment.get('fixed_width'):
            return self._extract_fixed_width_messages(segment, decoder)
        if segment.get('kind') == 'record':
            data = self._decompress(self.rom.data[start:end], segment.get('compression'))
            if decoder is None:
                logger.warning("Запись: нет декодера, пропуск")
                return []
            try:
                raw_text = decoder.decode(data, 0, len(data))
            except Exception as exc:
                logger.warning(f"Запись: сбой декодирования ({exc}), пропуск")
                return []
            if not isinstance(raw_text, str):
                return []
            return [{'offset': start, 'text': raw_text}]
        if segment.get('kind') == 'pointer_dialogues':
            return self._extract_pointer_dialogues(segment, decoder)
        data = self._decompress(self.rom.data[start:end], segment.get('compression'))
        if decoder is None:
            logger.warning("Нет декодера для перекодировки")
            return []
        try:
            text = decoder.decode(data, 0, len(data))
        except Exception as exc:
            logger.warning(f"Сбой декодирования ({exc}), пропуск")
            return []
        if not isinstance(text, str):
            # Декодер вернул не строку: раньше это уходило в _split_messages
            # и роняло GUI на TypeError вместо понятного отказа.
            logger.warning("Декодер вернул не строку, пропуск")
            return []
        return self._split_messages(text, start)

    @staticmethod
    def _strip_token_tail(text: str) -> str:
        """Срезает хвостовой прогон сырых токенов (см. core.decoder).

        Середина не трогается (токены идут inline); пустой остаток
        означает token-only фрагмент — сообщение не создаётся, байты
        остаются в ROM (инжектор такие окна не пишет).
        """
        from core.decoder import strip_raw_token_tail
        result: str = strip_raw_token_tail(text)
        return result

    def _split_messages(self, text: str, base_offset: int) -> list[dict]:
        """Разделение на отдельные сообщения с улучшенной обработкой.

        Сырые токены [XX] (сырые байты в показе плагинов) НЕ делят сообщение: внутри текста идут inline, ведущий/хвостовой
        token-only прогон отбрасывается (контролирующие байты остаются
        в ROM нетронутыми — инжектор их окна не пишет, см. trailing-правило
        inject_segment). Именованные токены ([PAGE], [PLAYER]) — контент,
        не трогаются. Разделители: [END] и \\n (синхронизация с инжектором:
        0x00/0xFF — те же границы в байтах).
        Offsets — текстовые координаты (индекс в декодированной строке),
        не байтовые ROM-адреса: [XX] занимает 4 символа за 1 байт.
        """
        logger = logging.getLogger('gb2text.extractor')
        logger.debug(f"Начало разделения текста (длина: {len(text)})")

        from core.decoder import raw_token_at
        messages = []
        current_msg = ""
        current_offset = base_offset
        i = 0

        def flush() -> None:
            nonlocal current_msg
            trimmed = self._strip_token_tail(current_msg)
            if trimmed:
                messages.append({
                    'offset': current_offset,
                    'text': trimmed
                })
                logger.debug(f"Найдено сообщение длиной {len(trimmed)}")
            current_msg = ""

        while i < len(text):
            char = text[i]

            # Обработка специальных последовательностей
            if i + 4 < len(text) and text[i:i + 5] == '[END]':
                flush()
                i += 5
                current_offset = base_offset + i
                continue

            # Сырые токены [XX]: inline внутри текста,
            # ведущий прогон пропускается (см. docstring)
            elif char == '[':
                token = raw_token_at(text, i)
                if token:
                    if self._strip_token_tail(current_msg):
                        current_msg += token
                    i += len(token)
                    if not current_msg:
                        current_offset = base_offset + i
                    continue

            # Разделение по переводу строки — синхронизация с инжектором
            if char == '\n':
                flush()
                i += 1
                current_offset = base_offset + i
                continue

            # Обработка обычного символа
            current_msg += char
            i += 1

        # Добавляем последнее сообщение, если оно есть
        if current_msg:
            trimmed = self._strip_token_tail(current_msg)
            if trimmed:
                messages.append({
                    'offset': current_offset,
                    'text': trimmed
                })
                logger.debug(f"Найдено последнее сообщение длиной {len(trimmed)}")

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
        start = segment.get('start')
        end = segment.get('end')
        if 'record_count' in segment:
            count = segment['record_count']
        else:
            # Число слотов по умолчанию считается ДО проверки границ, поэтому
            # здесь нужен собственный guard: битый start/end иначе дают
            # TypeError вместо отказа.
            usable = (isinstance(width, int) and not isinstance(width, bool)
                      and width > 0
                      and isinstance(start, int) and not isinstance(start, bool)
                      and isinstance(end, int) and not isinstance(end, bool))
            # isinstance-сужения mypy здесь не видит, поэтому доступ идёт
            # через локальные переменные:int вместо Optional.
            count = 0
            if usable:
                # После isinstance-проверок mypy не сужает тип
                # (start/end — Any | None), поэтому значения заранее
                # приводятся к int.
                lo = 0 if start is None else int(start)
                hi = 0 if end is None else int(end)
                count = (hi - lo) // int(width)
        if (isinstance(width, bool) or not isinstance(width, int) or width <= 0
                or isinstance(count, bool) or not isinstance(count, int) or count < 0
                or isinstance(start, bool) or not isinstance(start, int) or start < 0):
            logging.getLogger('gb2text.extractor').error(
                "Пропущена битая fixed_width-таблица (width/count/start)")
            return []
        data = self.rom.data
        count = min(count, (len(data) - start) // width if len(data) > start else 0)
        if decoder is None:
            decoder = segment.get('decoder')

        messages: list[dict] = []
        for i in range(count):
            slot_start = start + i * width
            # count выше ограничен по размеру файла, поэтому слот за
            # концом данных недостижим.
            if slot_start + width > len(data):  # pragma: no cover
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
