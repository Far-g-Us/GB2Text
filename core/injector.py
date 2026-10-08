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

import logging
import struct
from bisect import bisect_right

from core.rom import GameBoyROM


def _gb_bank_of(offset: int, bank_size: int = 0x4000) -> int:
    """Номер банка GB/GBC по линейному смещению в файле."""
    return offset // bank_size


def _resolve_pad(segment, default: int) -> int:
    """`pad_byte` сегмента, приведённый к байту. Битое значение — `default`.

    Единая точка для всех путей вставки. Раньше каждый путь резолвил значение сам,
    и три из пяти проверяли только тип: `pad_byte='FF'` давал TypeError из
    `bytes([...])`, а `256` — ValueError, оба ПОСЛЕ начала цикла, то есть роняли
    `inject_segment` посреди записи сегмента вместо тихого отката. Тип и
    диапазон проверяются здесь, у отправителя.
    """
    pad = segment.get('pad_byte', default)
    if (isinstance(pad, bool) or not isinstance(pad, int)
            or not 0 <= pad <= 255):
        return default
    return pad


def _decode_bytes(decoder, raw: bytes | bytearray) -> str | None:
    """Декодировать байты тем же декодером, что и сегмент. None — не вышло.

    Сигнатуры декодеров в проекте разные: большинство принимает
    `decode(data, start, length)`, единицы — `decode(data)`. Перебираются обе,
    потому что `TypeError` от неизвестной сигнатуры нельзя отличить от
    `TypeError` внутри самого декодера, и молчаливый `None` честнее, чем
    исключение посреди вставки.
    """
    if decoder is None or not callable(getattr(decoder, 'decode', None)):
        return None
    data = bytes(raw)
    for args in ((data, 0, len(data)), (data,)):
        try:
            out = decoder.decode(*args)
        except TypeError:
            continue
        except Exception:
            return None
        return out if isinstance(out, str) else None
    return None


def _read_back_fixed(decoder, raw: bytes | bytearray,
                     pad_byte: object = None) -> str | None:
    """Что из байтов слота реально прочитает извлечение.

    Декодеру отдаётся НЕ сам `raw`: хвост из pad-байта срезается ДО
    декодирования — так делает плагин при извлечении (`_en_window_end` у WL4
    режет прогон `0xFF`). Без этого модель врала бы: у WL4 `decode` даёт
    `'So '` для байт `53 6F FF`, хотя в игре и при обратном извлечении видно
    `'So'`. Декодеры, которые сами обрываются на паде (Pokemon GBA, Gen1),
    от этой предобработки не меняются.
    """
    data = bytes(raw)
    if (not isinstance(pad_byte, bool) and isinstance(pad_byte, int)
            and 0 <= pad_byte <= 255):
        data = data.rstrip(bytes([pad_byte]))
    return _decode_bytes(decoder, data)



class TextInjector:
    """Внедрение измененного текста обратно в ROM"""

    def __init__(self, rom_path: str):
        if not isinstance(rom_path, str):
            raise TypeError(f"rom_path должен быть строкой, а не {type(rom_path)}")
        self.rom = GameBoyROM(rom_path)
        self.original_data = bytearray(self.rom.data)
        self.modified_data = bytearray(self.rom.data)
        self._segment_cache: dict[object, list] = {}
        self._bank_segments: list = []
        self._taken_free_blocks: list[tuple[int, int]] = []
        self.last_overflow_report: list[dict] = []
        self.last_relocate_report: list[dict] = []
        self.last_align_report: dict = {}
        self.last_overlap_report: list[dict] = []
        # Записи, сокращение которых отвергнуто из-за чужого указателя в
        # середину (см. флаг сегмента has_mid_alias). Нужен, чтобы GUI
        # показал переводчику, почему запись осталась оригиналом.
        self.last_mid_alias_report: list[dict] = []
        self._written_spans: list[tuple[int, int]] = []
        self.last_spellcheck_report: list[dict] = []
        self.last_fit_report: list[dict] = []
        self.last_unmapped_chars: list[str] = []
        self.logger = logging.getLogger('gb2text.injector')

    def _run_spellcheck_gate(self, translations: list[str],
                             skip_long: bool = True) -> None:
        """Мягкая проверка орфографии переводов перед записью в ROM.

        Каждая строка перевода прогоняется через
        spell_checker.check_text(text, lang="auto", with_suggestions=False);
        найденные опечатки аккумулируются в self.last_spellcheck_report
        (паттерн last_overflow_report: отчёт сбрасывается при старте
        операции). Кандидаты исправлений не считаются — на больших корпусах
        pyspellchecker.candidates() даёт ~99% времени, а позиции и слова
        находятся без него.

        Гейт ВСЕГДА мягкий: найденные опечатки НИКОГДА не блокируют запись
        и не влияют на возвращаемое значение инжекции — независимо от
        skip_long. skip_long управляет только логированием и попаданием
        опечаток в отчёт (при skip_long=False отчёт не заполняется), а не
        самим процессом записи.

        Игнор-спаны ([XX], {VAR}, %s, числа, {{XX}}) отсекаются внутри
        spell_checker — не считаются опечатками.

        Формат записи отчёта:
        {'index', 'text', 'word', 'suggestions', 'start', 'end'}.
        """
        self.last_spellcheck_report = []
        if not translations or not skip_long:
            return
        from core.spell_checker import check_text
        for i, text in enumerate(translations):
            if not isinstance(text, str) or not text.strip():
                continue
            try:
                errors = check_text(text, lang="auto",
                                    with_suggestions=False)
            except Exception as exc:
                self.logger.debug(
                    f"Spellcheck failed for message {i}: {exc!s}")
                continue
            for start, end, word, suggestions in errors:
                self.last_spellcheck_report.append({
                    'index': i,
                    'text': text,
                    'word': word,
                    'suggestions': list(suggestions)[:8],
                    'start': start,
                    'end': end,
                })
        if self.last_spellcheck_report:
            self.logger.info(
                f"Spellcheck: {len(self.last_spellcheck_report)} опечаток "
                f"(запись не блокируется)")

    def collect_unmapped_chars(self) -> list[str]:
        """Собирает символы, потерянные при последнем encode переводов.

        Каждый CharMapDecoder накапливает потерянные символы в свою
        last_unmapped_chars (см. CharMapDecoder.encode). Здесь они агрегируются
        из декодеров всех закэшированных сегментов; после сбора список
        сбрасывается, чтобы следующий инжект считался с чистого листа.
        """
        seen: list[str] = []
        for segments in self._segment_cache.values():
            for segment in segments:
                decoder = segment.get('decoder')
                if decoder is None:
                    continue
                for char in getattr(decoder, 'last_unmapped_chars', []):
                    if char not in seen:
                        seen.append(char)
                if hasattr(decoder, 'last_unmapped_chars'):
                    decoder.last_unmapped_chars = []
        return seen

    def _get_segments(self, plugin) -> list:
        """Сегменты плагина с кэшем по экземпляру плагина.

        self.rom.data неизменен в течение жизни инстанса (правки идут только
        в self.modified_data), поэтому get_text_segments достаточно вызвать один
        раз на экземпляр плагина: пакетная инъекция не пересканирует ROM.
        Ключ — экземпляр, а не класс: ConfigurablePlugin хранит self.config,
        влияющий на сегменты, и разные экземпляры одного класса дают разные
        списки.
        """
        if plugin not in self._segment_cache:
            raw = plugin.get_text_segments(self.rom)
            valid = self._validated(raw)
            if valid is None:
                self.logger.warning("Плагин вернул битый список сегментов — пусто")
                valid = []
            self._segment_cache[plugin] = valid
        segments = self._segment_cache[plugin]
        self._sync_bank_segments(segments)
        return segments

    def _segments_by_name(self, segments: list) -> dict:
        """Словарь имя→сегмент, кэшированный по идентичности списка.

        Поиск `next(s for s in segments if s['name'] == ...)` выполнялся
        дважды на каждую инъекцию и давал 70 с на Golden Sun (10863 сегмента
        × 10863 инъекций). Список приходит из плагина и меняется целиком,
        поэтому кэш по идентичности безопасен.
        """
        if getattr(self, '_by_name_src', None) is segments:
            return self._by_name
        by_name: dict = {}
        for s in segments:
            if isinstance(s, dict) and isinstance(s.get('name'), str):
                by_name.setdefault(s['name'], s)
        self._by_name_src = segments
        self._by_name: dict = by_name
        return by_name

    def _validated(self, segments):
        """`_valid_segments` с кэшем: список проверяется один раз на объект.

        Проверка на КАЖДЫЙ вызов стоила 118 млн isinstance на Golden Sun
        (10863 сегмента × 10863 вызовов). Возвращается исходный список:
        идентичность нужна кэшу индекса чужих диапазонов.
        """
        if not hasattr(self, '_validated_lists'):
            self._validated_lists: dict = {}
        if self._validated_lists.get(id(segments)) is segments:
            return segments
        checked = self._valid_segments(segments)
        if checked is not None:
            self._validated_lists[id(segments)] = segments
        return checked

    def _sync_bank_segments(self, segments: list) -> None:
        """Фиксирует банковые сегменты для _occupied_intervals.

        Вызывается при каждом получении сегментов (включая ручную передачу
        в inject_segment), чтобы перед relocate был актуальный список
        таблиц всех банков.

        Индекс чужих диапазонов здесь НЕ сбрасывается: метод вызывается на
        каждый сегмент (10863 раз на Golden Sun), а список не меняется —
        сброс стоил бы полной перестройки индекса на каждый сегмент.
        Недействительность индекса отслеживает сама `_foreign_index` по
        признаку из ссылок на списки и размера буфера.
        """
        if not isinstance(segments, list):
            return
        # Список банковых сегментов кэшируем по ИДЕНТИЧНОСТИ входа: метод
        # зовётся на каждый сегмент (21727 раз на Golden Sun), а сам список
        # сегментов при этом не меняется. Пересобирать его каждый раз значило
        # сканировать 10863 сегмента на каждый вызов.
        if getattr(self, '_bank_src', None) is segments:
            return
        self._bank_src = segments
        bank_segs = [s for s in segments if isinstance(s, dict) and s.get('bank_meta')]
        if bank_segs and self._bank_segments != bank_segs:
            self._bank_segments = bank_segs
            self._taken_free_blocks = []

    def inject_translations(self, segment_name: str, translations: list[str], plugin,
                            segments: list | None = None,
                            results: dict[str, list[dict]] | None = None,
                            relocate: bool | None = None) -> bool:
        """Вставка с маршрутизацией: record-сегменты → блочный путь.

        Сегменты kind='record' с 'lang' принадлежат языковому блоку
        (pointer-таблица): вставляются целиком через inject_language_block
        (meta с 'blocks') или inject_interleaved_language (meta с
        lang_slots/index_of). Остальные — обычный inject_segment.
        translations — переводы ТЕКУЩЕГО сегмента (для record ровно одно
        сообщение); sibling-сегменты берут saved-or-original из results
        (entry['translation'] или entry['text']) либо raw_text; без обоих —
        честный False. results=None допустим только если все sibling имеют
        raw_text (иначе False вместо тихой затирки). relocate пробрасывается
        в inject_segment (pointer_dialogues, generic); record-пути
        (inject_language_block/interleaved) живут своей логикой расширения
        и флаг игнорируют.
        """
        if segments is None:
            segments = self._get_segments(plugin)
        else:
            segments = self._validated(segments)
            if segments is None:
                return False
            self._segment_cache[plugin] = segments
            self._sync_bank_segments(segments)
        segment = self._segments_by_name(segments).get(segment_name)
        if segment is None:
            return False
        lang = segment.get('lang')
        if segment.get('kind') != 'record' or not isinstance(lang, str):
            return self.inject_segment(segment_name, translations, plugin,
                                       segments=segments, relocate=relocate)
        if not isinstance(translations, (list, tuple)) or len(translations) != 1:
            return False
        meta = plugin.get_pointer_table_meta() if hasattr(plugin, 'get_pointer_table_meta') else None
        if not isinstance(meta, dict):
            return False
        members = sorted(
            (s for s in segments
             if isinstance(s, dict) and s.get('kind') == 'record'
             and TextInjector._segment_lang(s) == lang),
            key=lambda s: s.get('index', 0) if isinstance(s.get('index'), int)
            and not isinstance(s.get('index'), bool) else 0)
        if not members:
            return False
        texts: list[str] = []
        for member in members:
            if member['name'] == segment_name:
                texts.append(translations[0])
                continue
            text = self._sibling_text(member, results)
            if text is None:
                return False
            texts.append(text)
        if isinstance(meta.get('blocks'), list) and meta.get('blocks'):
            pos = {id(member): i for i, member in enumerate(members)}
            ordered = sorted(
                members,
                key=lambda s: s['start'] if isinstance(s.get('start'), int)
                and not isinstance(s.get('start'), bool) else 0)
            ordered_texts = [texts[pos[id(member)]] for member in ordered]
            return self.inject_language_block(lang, ordered_texts, plugin, segments=segments)
        if isinstance(meta.get('lang_slots'), dict) and callable(meta.get('index_of')):
            count = meta.get('count')
            if not isinstance(count, int) or isinstance(count, bool):
                return False
            indices: set[int] = set()
            for s in members:
                idx = s.get('index')
                if isinstance(idx, bool) or not isinstance(idx, int):
                    return False
                indices.add(idx)
            if not indices or len(indices) != len(members) or len(indices) != count \
                    or min(indices) != 0 or max(indices) != count - 1:
                return False
            return self.inject_interleaved_language(lang, texts, plugin, segments=segments)
        return self.inject_segment(segment_name, translations, plugin,
                                   segments=segments, relocate=relocate)

    @staticmethod
    def _sibling_text(member: dict, results: dict[str, list[dict]] | None) -> str | None:
        """Текст sibling-записи: saved-or-original из results либо raw_text."""
        if results is not None:
            entries = results.get(member['name'])
            if isinstance(entries, list) and entries:
                entry = entries[0]
                if isinstance(entry, dict):
                    text = entry.get('translation', entry.get('text'))
                    if isinstance(text, str):
                        return text
        raw = member.get('raw_text')
        return raw if isinstance(raw, str) else None

    def inject_segment(self, segment_name: str, translations: list[str], plugin,
                       skip_long: bool = True, segments: list | None = None,
                       relocate: bool | None = None) -> bool:
        """
        Внедряет переводы в указанный сегмент

        Args:
            segment_name: имя сегмента
            translations: список переводов
            plugin: плагин игры
            skip_long: если True, пропускает слишком длинные сообщения вместо отклонения всего сегмента
            segments: если передан, используются готовые сегменты плагина
                (вызов get_text_segments пропускается — экономит повторный
                скан/декомпрессию ROM при пакетной вставке)
            relocate: переносить ли слишком длинные записи в свободные
                зоны (None — брать из bank_meta['relocate']; для
                pointer_dialogues None — пытаться при известных slots,
                иначе пропуск как раньше)

        Returns:
            True если хотя бы одно сообщение было внедрено
        """
        self.last_overflow_report = []
        self.last_align_report = {}
        self.last_overlap_report = []
        self.last_mid_alias_report = []
        # Отказ «перевод кончается raw-токеном» живёт по тому же контракту,
        # что и остальные: отчёт = ОДИН сегмент. Без сброса список копился бы
        # весь инстанс, и харнесс получал бы адрес чужого сегмента.
        # `last_mid_alias_report` сбрасывается здесь же ради симметрии: его
        # читает GUI, а не census, поэтому протечка была безвредной, но
        # ровно этим же сдвигом отчёт пришёл бы не в тот сегмент.
        self.last_affix_report = []
        self.last_spellcheck_report = []
        self.last_fit_report = []
        self.last_relocate_report = []

        if not plugin:
            return False

        if not isinstance(translations, (list, tuple)):
            return False

        if segments is None:
            segments = self._get_segments(plugin)
        else:
            segments = self._validated(segments)
            if segments is None:
                return False
            self._segment_cache[plugin] = segments
            self._sync_bank_segments(segments)
        if not isinstance(segments, list):
            return False
        segment = self._segments_by_name(segments).get(segment_name)

        if not segment:
            return False

        if segment.get('injectable') is False:
            reason = str(segment.get('not_writable_reason') or 'read_only')
            self.logger.info(
                f"Сегмент '{segment_name}' не поддерживает вставку (extract-only)")
            # Отказ обязан быть наблюдаемым: без записи в
            # `last_affix_report` причина отказа не видно ни census, ни GUI.
            ro_report: list = getattr(self, 'last_affix_report', None) or []
            self.last_affix_report = ro_report
            ro_report.append({'segment': segment_name, 'reason': reason})
            return False

        is_fixed = bool(segment.get('fixed_width'))

        self._run_spellcheck_gate(translations, skip_long)
        from core.textbox import fit_report

        try:
            self.last_fit_report = fit_report(segment, translations)
        except Exception as exc:
            # Отчёт не должен менять поведение записи (report-only).
            self.logger.debug(f"Fit-отчёт пропущен: {exc!s}")
            self.last_fit_report = []

        enc = segment.get('encoder')
        if enc is not None:
            # Сжатый сегмент: текст перекодируется плагином (Huffman/LZSS и т.п.)
            # и должен поместиться в исходное сжатое окно (start:end).
            if not translations:
                return True
            if len(translations) != 1:
                self.logger.warning(
                    f"Compressed segment expects 1 translation, "
                    f"got {len(translations)}; only the first will be injected")
                translations = translations[:1]
            translation = translations[0]

            original_length = segment['end'] - segment['start']
            pad_byte = _resolve_pad(segment, 0x00)

            trans_bytes = None
            try:
                trans_bytes = enc(translation)
            except (ValueError, KeyError, IndexError, TypeError) as e:
                self.logger.debug(f"Could not recompress: {e}")
            if trans_bytes is not None and not isinstance(trans_bytes, (bytes, bytearray)):
                self.logger.debug("Compressor returned non-bytes, skipping")
                trans_bytes = None
            if trans_bytes is not None and len(trans_bytes) > original_length:
                self.logger.debug(
                    f"Translation too long ({len(trans_bytes)} > "
                    f"{original_length}), skipping")
                trans_bytes = None

            if trans_bytes is None:
                if not skip_long:
                    return False
                self.logger.info(
                    "[compressed] Skipped: could not recompress or too long")
                return False

            # Сжатый сегмент пишется ОДНИМ блоком от начала окна, поэтому
            # гард здесь обязателен: без него запись перекрывала чужой
            # сегмент молча (тот же класс дефекта, что закрыт в обычном
            # generic-пути и в pointer-пути).
            cbase = segment['start']
            # Тот же гейт, что и в generic-пути, но для сжатого сегмента.
            # Экстрактор срезает хвостовой token-only прогон из ПОКАЗАННОЙ
            # записи (`strip_raw_token_tail`), поэтому перевод, заканчивающийся
            # raw-токеном, которого не было в конце оригинала, не пережил бы
            # round-trip: при следующем извлечении токен исчез, а GUI взял бы
            # перевод уже без него — и записал бы это в ROM. На FFTA так терялся
            # байт `0xC8` (имя персонажа) в 7 диалогах: сжатый перевод
            # заканчивался на `[C8]`, оригинал кончался на `es/`.
            orig_text = self._compressed_original_text(segment)
            if orig_text is not None and self._ends_with_raw_token(
                    translation, orig_text):
                comp_report: list = getattr(
                    self, 'last_affix_report', None) or []
                self.last_affix_report = comp_report
                comp_report.append({'segment': segment_name, 'index': 0,
                                    'offset': cbase,
                                    'room': original_length,
                                    'reason': 'trailing_raw_token'})
                if not skip_long:
                    return False
                self.logger.info(
                    '[compressed] Skipped: translation ends with a raw token, '
                    'which extraction would drop')
                return False

            cfull = bytes(trans_bytes) + bytes([pad_byte]) * (
                original_length - len(trans_bytes))
            own_lo, own_hi = self._own_span(segment)
            foreign_hit = self._foreign_hit(
                self._foreign_index(), segment_name, segment, cbase,
                len(cfull), own_lo, own_hi)
            if self._check_write_overlap(cbase, cfull) == 'conflict' \
                    or foreign_hit:
                overlap_log = getattr(self, 'last_overlap_report', None)
                if overlap_log is None:
                    overlap_log = self.last_overlap_report = []
                entry = {'segment': segment_name, 'index': 0, 'offset': cbase,
                         'length': len(cfull), 'room': original_length}
                if foreign_hit:
                    entry['foreign'] = True
                overlap_log.append(entry)
                self.logger.info(
                    "[compressed] Skipped: overlaps another record or segment")
                return False

            if not self._safe_inject_message(cbase, trans_bytes,
                                             original_length, pad_byte):
                if not skip_long:
                    return False
                self.logger.info("[compressed] Skipped: out of ROM bounds")
                return False
            self.logger.info("[compressed] Injected 1 message")
            return True

        # Гарантируем наличие decoder
        self._ensure_decoder(segment)
        if not segment.get('decoder'):
            return False
        # Если декодер не поддерживает кодирование — сегмент extract-only
        if not callable(getattr(segment.get('decoder'), 'encode', None)):
            self.logger.warning(
                "Сегмент '%s' не поддерживает инжект (декодер без encode)",
                segment_name,
            )
            return False

        # Банковый сегмент (Zelda TMC и игры со схожей структурой):
        # записи адресуются таблицей относительных смещений, границы записей
        # берутся из таблицы, а не из сплошного скана терминаторов.
        if segment.get('bank_meta'):
            return self._inject_bank_segment(segment, translations, skip_long,
                                             relocate=relocate)

        # Pointer-пул диалогов (Pokemon GBA): привязка идёт по манифесту
        # адресов (target + free_after), терминатор пишется явно.
        if segment.get('kind') == 'pointer_dialogues':
            return self._inject_pointer_dialogues(segment, translations, skip_long, relocate)

        if not isinstance(translations, (list, tuple)):
            return False
        # Проверяем, что переводы не длиннее оригинального текста
        original_messages = self._extract_original_messages(segment)

        from core.decoder import (
            is_raw_token_text_ignorable as is_ignorable,
            remove_raw_tokens,
        )
        if len(translations) != len(original_messages):
            trimmed = list(translations)
            if skip_long and not is_fixed:
                while trimmed and is_ignorable(trimmed[-1]):
                    trimmed.pop()
            mapped, dropped = self._drop_junk_windows(original_messages)
            if not is_fixed and mapped is not None and len(trimmed) == len(mapped):
                original_messages = mapped
                translations = trimmed
            else:
                self.last_align_report = {
                    'segment': segment_name,
                    'translations': len(translations),
                    'windows': len(original_messages),
                    'extra': [self._preview(w.get('text')) for w in original_messages[len(translations):]],
                    'extra_translations': [self._preview(t) for t in translations[len(original_messages):]],
                    'dropped': dropped if mapped is not None else 0,
                }
                return False

        # Пустой список переводов = нет сообщений = OK только для пустого сегмента
        if len(translations) == 0:
            if not original_messages:
                return True
            self.last_align_report = {
                'segment': segment_name,
                'translations': 0,
                'windows': len(original_messages),
                'extra': [self._preview(w.get('text')) for w in original_messages],
                'extra_translations': [],
            }
            return False

        injected = 0
        skipped = 0
        enc = segment['decoder'].encode
        max_len = segment.get(
            'max_length',
            segment['fixed_width'] - 1 if is_fixed else None)
        # Чужие диапазоны — один раз на сегмент: сборка стоит O(сегментов),
        # а внутри цикла это 17 секунд чистого гарда на FF5 (5242 сообщения).
        # Отсекаем только те, что целиком внутри какой-либо нашей записи:
        # фильтр зависит от base/room, поэтому фильтруем на месте (дёшево).
        # Чужие диапазоны — индекс строится один раз на список сегментов, а
        # проверка идёт через bisect. Раньше список пересобирался на КАЖДЫЙ
        # сегмент (O(n²): 118 млн вызовов на Golden Sun).
        foreign_idx = self._foreign_index()
        for i, (original, translation) in enumerate(zip(original_messages, translations, strict=False)):
            # Нестроковый перевод — отказ/пропуск (TypeError наружу нельзя)
            if not isinstance(translation, str):
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: non-string translation, skipping")
                    continue
                return False
            # Провал декода окна: писать вслепую нельзя (skip сохраняет байты)
            window_text = original.get('text')
            if not isinstance(window_text, str):
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: window decode failed, skipping")
                    continue
                return False
            # Контент на мусорное окно = рассогласование (не длина!) — всегда отказ.
            # Только non-fixed: fixed-слоты позиционные, переименование
            # token-слота там легитимно. Пробельные окна — не мусор
            # (blank-filling разрешён как раньше).
            if not is_fixed and remove_raw_tokens(window_text) == '' \
                    and not is_ignorable(translation):
                self.last_align_report = {
                    'segment': segment_name,
                    'translations': len(translations),
                    'windows': len(original_messages),
                    'extra': [window_text[:60]],
                    'extra_translations': [],
                }
                return False
            # Пустой/мусорный перевод контентного окна — пропуск без затирки:
            # pad'ом стирать текст нельзя, удаление — только осознанно.
            # Только non-fixed: blank фиксированного слота — legacy-семантика.
            if not is_fixed and not is_ignorable(window_text) \
                    and is_ignorable(translation):
                # Отказ без отчёта был молчаливым: запись оставалась
                # английской, переводчик видел «принято», а census считал
                # расхождение порчей байтов, хотя байты не тронуты. Семантика
                # та же, что у `empty_translation` в pointer-пути, поэтому
                # причина переиспользуется, а не заводится вторая.
                base_prev = segment['start'] + original['offset']
                empty_report: list = getattr(
                    self, 'last_affix_report', None) or []
                self.last_affix_report = empty_report
                empty_report.append({
                    'segment': segment_name, 'index': i,
                    'offset': base_prev,
                    'room': original['length'],
                    # Набор полей совпадает с writer'ом pointer-пути
                    # (`empty_translation`, ~строка 1815): GUI читает `room`,
                    # поэтому без него диалог отказа показывал бы
                    # free_after = 0.
                    'length': len(translation),
                    'reason': 'empty_translation',
                    'text': translation,
                    # Текст ОРИГИНАЛЬНОГО окна: он, а не адрес и не индекс,
                    # является доказуемым ключом отказа. Адрес отчёта —
                    # байтовый, а census знает адрес из координат экстрактора
                    # (1 байт на символ), поэтому у Zelda они расходятся на
                    # несколько байт на запись, а индекс инжектора после
                    # `_drop_junk_windows` перестаёт совпадать с позицией.
                    'original': window_text,
                })
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: empty translation, skipping")
                    continue
                return False
            # Аффиксы окна — только generic-путь: fixed-сообщения содержат
            # всё (включая токены), там запись legacy с начала окна.
            # Generic: уже содержащиеся в переводе токены потребляются
            # (без дублей), пишется остаток между аффиксами, fit считается
            # от свободной середины окна.
            if is_fixed:
                # Fixed-слоты: перевод видит всё (включая токены) — правка
                # явная, ответственность переводчика (линтер флагует токены).
                # room — ВСЯ ширина слота, а не длина текста: иначе при
                # сокращении перевода хвост слота не затирается и старые
                # байты остаются видимыми (WL4: «Entry Passage» → «Entr»
                # извлекался как «Entr  Passage»).
                base, room, effective = (
                    segment['start'] + original['offset'], original['length'], translation)
            else:
                base, room, effective = self._affix_region(
                    segment, original, window_text, enc, translation)
            if base is None or room is None or effective is None:
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: window affixes not reproducible, skipping")
                    continue
                return False
            if not is_fixed and self._ends_with_raw_token(effective, window_text):
                # Перевод, заканчивающийся raw-токеном, НЕПРЕДСТАВИМ: при
                # обратном извлечении хвостовой token-only прогон отбрасывается
                # из отображения, и запись молча теряет символы. Пример (FF5):
                # `in[F6]a!` при сокращении до `in[F6]` превращается в `in`.
                # Отказ, а не запись: иначе переводчик увидит «принято», а в
                # игре будет обрезанный текст.
                report: list = getattr(self, 'last_affix_report', None) or []
                self.last_affix_report = report
                report.append({'segment': segment_name, 'index': i,
                               'offset': base, 'room': room,
                               'reason': 'trailing_raw_token'})
                if skip_long:
                    skipped += 1
                    self.logger.debug(
                        f"Message {i}: translation ends with a raw token, "
                        f"which extraction would drop, skipping")
                    continue
                return False
            try:
                trans_bytes = enc(effective)
            except (ValueError, KeyError, IndexError, TypeError):
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: cannot encode translation, skipping")
                    continue
                return False
            if not isinstance(trans_bytes, (bytes, bytearray)):
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: encoder returned non-bytes, skipping")
                    continue
                return False
            # Сравниваем длину в байтах (для fixed_width — окно слота без 0xFF)
            if len(trans_bytes) > room:
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: translation too long ({len(trans_bytes)} > {room}), skipping")
                    continue
                else:
                    return False
            if max_len is not None and len(trans_bytes) > max_len:
                if skip_long:
                    skipped += 1
                    self.logger.debug(
                        f"Message {i}: translation too long for fixed slot "
                        f"({len(trans_bytes)} > {max_len}), skipping")
                    continue
                else:
                    return False
            # Fixed-слоты по умолчанию добиваются 0xFF (EOS terminal),
            # а не 0x20: пробел внутри слота виден при ре-экстракте.
            # Резолвится ДО гейта читаемости: иначе проверка срезала бы хвост
            # по сырому значению (None при отсутствующем ключе), и запись
            # падала бы уже по нормализованному — а WL4-класс проскочил бы
            # на сегментах с битым (некорректным) pad_byte.
            pad_byte = _resolve_pad(segment, 0xFF if is_fixed else 0x20)
            if is_fixed:
                # Перевод, который не читается обратно из СВОИХ ЖЕ байтов,
                # писать в слот нельзя: отрезанный хвост — это молчаливая
                # потеря символов. WL4: пробел — байт `0xFF`, и он же
                # граница записи, поэтому `So ` физически не представим —
                # ROM хранит `So`. Отказ, а не предупреждение, по образцу
                # `trailing_raw_token` выше: иначе переводчик увидит «принято»,
                # а в игре будет обрезанный текст.
                # Условие — ИМЕННО обрезанный хвост (back — префикс).
                # Подстановка символа под отказ НЕ попадает: это другой дефект
                # (см. ROADMAP: Pokemon/Gen1 энкодеры подставляют пробел и
                # last_unmapped_chars у них пуст), и здесь он не лечится.
                # Замер по 15 ROM из test_game (3 плагина с fixed_width,
                # 8208 записей, scripts_roms/fixed_representability_probe.py):
                # по исходным текстам обрезанных нет — они представимы по
                # построению, ведь извлечение уже срезало хвост. На УКОРОЧЁННЫХ
                # вариантах (1/3 длины) обрезание есть: 497 из 8208 — 12 у WL4,
                # 485 у Pokemon GBA, где обрезка приходится на control-коды.
                # То есть гейт на реальных данных не молчит, а на настоящих
                # переводах отверг бы 6 % записей; ложных срабатываний на
                # исходных текстах он не даёт вовсе.
                back = _read_back_fixed(segment.get('decoder'), trans_bytes,
                                        pad_byte)
                if back is not None and len(back) < len(effective) \
                        and effective.startswith(back):
                    affix_report: list = getattr(self, 'last_affix_report', None) or []
                    self.last_affix_report = affix_report
                    affix_report.append({
                        'segment': segment_name, 'index': i,
                        'offset': base, 'room': room,
                        # Причина — по СОДЕРЖИМОМУ записи, а не по пустому
                        # read-back: декодер, возвращающий '' на непустой вход,
                        # иначе получил бы «перевод из одного заполнения» на
                        # каждой записи сегмента и оставил бы его целиком
                        # оригиналом.
                        # Семантика совпадает с `empty_translation` в
                        # pointer-пути (`_inject_pointer_dialogues`): обе причины
                        # означают «слот стал бы пустым», различаясь тем, что
                        # здесь нашлось непробельное содержимое, которое
                        # экстрактор срежет как заполнение.
                        'reason': 'all_padding'
                                  if trans_bytes
                                  and all(b == pad_byte for b in trans_bytes)
                                  else 'trailing_truncated',
                        'written': len(trans_bytes),
                        'chars': len(effective),
                        'read_back': len(back)})
                    if skip_long:
                        skipped += 1
                        self.logger.debug(
                            f"Message {i}: translation is truncated when read "
                            f"back ({len(back)} of {len(effective)} chars), "
                            f"skipping")
                        continue
                    return False

            # Внедряем перевод
            # Запись, в середину которой смотрит чужой указатель (сегмент
            # помечен плагином флагом has_mid_alias), нельзя сокращать.
            # Причина: extent записи задаётся ЕЁ разделителем, а он у
            # FF4/FF5 одновременно и есть pad_byte. То есть при любом
            # сокращении extent сжимается, хвост забивается разделителями,
            # и указатель, смотрящий в этот хвост, начинает пустую запись,
            # которая отфильтровывается — алиас исчезает из манифеста.
            # Поэтому сокращение здесь отвергается, а не паддингуется:
            # иначе в игре вторая запись отобразилась бы пустой строкой.
            # Цена отказа измерена: 561 из 646 переводимых записей FF4
            # (86.8%) и 40 из 4901 FF5 (0.8%) нельзя сократить. Отказ
            # попадает в last_mid_alias_report, чтобы GUI показал его
            # переводчику, а не оставил запись молча английской.
            if segment.get('has_mid_alias') and not is_fixed \
                    and len(trans_bytes) < room:
                self.last_mid_alias_report.append({
                    'segment': segment_name, 'index': i,
                    'offset': base, 'room': room,
                    'written': len(trans_bytes),
                })
                if skip_long:
                    skipped += 1
                    self.logger.debug(
                        f"Message {i}: record has a mid-record pointer, "
                        f"shorter translation refused (would blank it)")
                    continue
                return False
            if is_fixed and len(trans_bytes) < room:
                # Хвост — оригинальные байты (там бывает чужой контент
                # через aliasing!), первый байт — EOS-терминатор.
                # Только для has_mid_alias: иначе хвост — дополнение,
                # заполняем pad_byte (WL4: «Entry Passage» → «Entr»
                # иначе оставлял «Entr  Passage»).
                terms = segment.get('terminators')
                eos = 0xFF
                # Только упорядоченные коллекции: у set «первый» терминатор
                # недетерминирован, а здесь выбирается именно он.
                if isinstance(terms, (list, tuple)) and terms:
                    first = next(iter(terms))
                    if isinstance(first, int) and not isinstance(first, bool) \
                            and 0 <= first <= 255:
                        eos = first
                if segment.get('has_mid_alias'):
                    tail = bytes(self.modified_data[base + len(trans_bytes) + 1:base + room])
                    trans_bytes = trans_bytes + bytes([eos]) + tail
                else:
                    trans_bytes = trans_bytes + bytes([eos]) + bytes([pad_byte]) * (room - len(trans_bytes) - 1)
            full = bytes(trans_bytes) + bytes([pad_byte]) * (room - len(trans_bytes))
            verdict = self._check_write_overlap(base, full)
            if verdict == 'conflict':
                self.last_overlap_report.append({
                    'segment': segment_name, 'index': i,
                    'offset': base, 'length': len(full), 'room': room,
                })
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: overlaps a previous write, skipping")
                    continue
                return False
            # Запись в чужой сегмент — тоже порча, даже если предыдущих
            # записей в этом запуске не было. На Odyssey окно сегмента
            # способностей накрывало запись диалога, и generic-путь писал
            # туда молча: чужие байты затирались, а обратное извлечение
            # показывало чужой текст вместо перевода.
            # Ширина — len(full), НЕ len(trans_bytes): non-fixed запись
            # падает до room и пишется целиком, поэтому короткий перевод
            # стирал хвост чужой записи МОЛЧА (отчёт пустой).
            own_lo, own_hi = self._own_span(segment)
            if self._foreign_hit(foreign_idx, segment_name, segment,
                                   base, len(full), own_lo, own_hi):
                self.last_overlap_report.append({
                    'segment': segment_name, 'index': i,
                    'offset': base, 'length': len(full), 'room': room,
                    'foreign': True,
                })
                # Всегда пропуск, а не отказ: иначе ОДНО пересекающееся
                # сообщение уронило бы весь сегмент вместе с сотнями
                # корректных переводов. Байты не трогаем — это безопасно,
                # в отличие от записи.
                skipped += 1
                self.logger.debug(
                    f"Message {i}: overlaps another segment, skipping")
                continue
            if not self._safe_inject_message(base, trans_bytes, room, pad_byte):
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: out of ROM bounds, skipping")
                    continue
                return False
            self._tracked_spans().append((base, base + room))
            injected += 1

        self.logger.info(f"Injected {injected} messages, skipped {skipped}")
        return injected > 0


    def inject_language_block(self, lang: str, texts: list[str], plugin,
                              segments: list | None = None) -> bool:
        """Внедряет целый языковой блок текста, адресуемого таблицей указателей.

        Требования к плагину: get_pointer_table_meta() -> {'table','count',
        'blocks':[(idx_from, idx_to, lang), ...]} и make_text_encoder().
        Блок пересобирается (запись + 2x0x00), цели поддиапазона таблицы
        переписываются: in-place, если блок помещается в исходный span,
        иначе relocate в свободный 0x00-run вне всех блоков и таблицы.

        Если плагин использует slot-interleaved раскладку (метаданные содержат
        'index_of'+'lang_slots', без 'blocks') — делегируется в
        inject_interleaved_language.
        """
        self.last_spellcheck_report = []
        # Сегментных данных о ширине здесь нет — честное [] (см. core/textbox).
        self.last_fit_report = []
        self.last_overflow_report = []
        self.last_relocate_report = []
        self.last_align_report = {}
        # Симметрично `overflow/align/fit` выше:
        # контракт «отчёт = один сегмент».
        # Без сброса элементы предыдущего
        # сегмента протекали бы в следующий, а
        # census, читающий отчёты после каждого вызова,
        # отнёс бы их к текущему сегменту.
        self.last_affix_report = []
        meta = plugin.get_pointer_table_meta() if hasattr(plugin, 'get_pointer_table_meta') else None
        if not meta or not isinstance(meta, dict):
            return False
        if not isinstance(texts, (list, tuple)) or not isinstance(lang, str):
            return False
        if 'index_of' in meta and 'lang_slots' in meta and not meta.get('blocks'):
            return self.inject_interleaved_language(lang, texts, plugin, segments=segments)
        table_offset = meta.get('table')
        count = meta.get('count')
        blocks = meta.get('blocks') or []
        if (isinstance(table_offset, bool) or not isinstance(table_offset, int)
                or isinstance(count, bool) or not isinstance(count, int)
                or not isinstance(blocks, list)):
            return False
        if count <= 0 or table_offset < 0 or table_offset + 4 * count > len(self.rom.data):
            self.logger.warning(
                f"Некорректная таблица указателей: offset=0x{table_offset:X}, "
                f"count={count}, rom_size={len(self.rom.data)}")
            return False
        if any(not (isinstance(b, (list, tuple)) and len(b) == 3)
                for b in blocks):
            self.logger.warning("Некорректная форма записей blocks в get_pointer_table_meta")
            return False
        if any(not (isinstance(bs, int) and not isinstance(bs, bool)
                    and isinstance(be, int) and not isinstance(be, bool)
                    and 0 <= bs < count and 0 <= be <= count and bs < be)
                for bs, be, _ in blocks):
            self.logger.warning("Некорректные индексы блоков в get_pointer_table_meta")
            return False

        self._run_spellcheck_gate(texts, skip_long=True)

        if segments is None:
            segments = self._get_segments(plugin)
        else:
            segments = self._validated(segments)
            if segments is None:
                return False
            self._segment_cache[plugin] = segments

        block = next((b for b in blocks if b[2] == lang), None)
        if block is None:
            return False
        idx_from, idx_to, _ = block
        segs = [
            s for s in segments
            if isinstance(s, dict) and isinstance(s.get('name'), str)
            and isinstance(s.get('start'), int) and not isinstance(s.get('start'), bool)
            and isinstance(s.get('end'), int) and not isinstance(s.get('end'), bool)
            and 0 <= s['start'] <= s['end'] <= len(self.modified_data)
            and TextInjector._segment_lang(s) == lang
            and s.get('kind', 'record') == 'record'
        ]
        segs.sort(key=lambda s: s['start'])
        if not segs or len(segs) != len(texts) or len(texts) == 0:
            return False
        if len(segs) != idx_to - idx_from:
            return False

        targets = [
            int.from_bytes(
                self.rom.data[table_offset + 4 * i: table_offset + 4 * i + 4], 'little'
            ) - 0x08000000
            for i in range(count)
        ]
        if not all(0 <= t < len(self.rom.data) for t in targets):
            return False

        encoder = plugin.make_text_encoder() if hasattr(plugin, 'make_text_encoder') else None
        if encoder is None:
            return False

        records: list[bytes] = []
        for text in texts:
            if not isinstance(text, str):
                return False
            try:
                encoded = encoder.encode(text)
            except (ValueError, KeyError, IndexError, TypeError):
                return False
            if not isinstance(encoded, (bytes, bytearray)):
                return False
            records.append(bytes(encoded))

        from core.pointer_table import assemble_block, find_free_space, patch_pointer_range

        ranges = self._block_ranges(blocks, segments, targets, count, len(self.modified_data))
        # block найден выше из того же списка blocks и список не мутировал —
        # enumerate всегда находит индекс (проверка None недостижима).
        block_index = next(
            i for i, b in enumerate(blocks) if b[2] == lang)
        span_start, span_end = ranges[block_index]

        new_block = assemble_block(records)
        extra = b'\x00\x00'
        if len(new_block) + len(extra) <= span_end - span_start:
            dest = span_start
        else:
            dest = find_free_space(
                self.modified_data, len(new_block) + len(extra),
                [*ranges, (table_offset, table_offset + 4 * count)])
            if dest is None:
                return False

        new_block = extra + new_block
        rom_len = len(self.modified_data)
        if not (0 <= span_start <= span_end <= rom_len and 0 <= dest
                and dest + len(new_block) <= rom_len):
            return False
        # Дальше буфер грязнится: при отказе патча таблицы — откат.
        snapshot = bytes(self.modified_data)
        self.modified_data[dest:dest + len(new_block)] = new_block
        if dest == span_start:
            if dest + len(new_block) < span_end:
                self.modified_data[dest + len(new_block):span_end] = b'\x00' * (
                    span_end - dest - len(new_block))
        else:
            self.modified_data[span_start:span_end] = b'\x00' * (span_end - span_start)

        record_offsets: list[int] = []
        offset = dest + len(extra)
        for record in records:
            record_offsets.append(offset)
            offset += len(record) + 2
        if not patch_pointer_range(self.modified_data, table_offset,
                                   idx_from, idx_to, record_offsets):
            self.modified_data[:] = snapshot
            return False
        self.logger.info(
            f"Блок '{lang}': {len(records)} записей, "
            f"{len(new_block)} б, dest=0x{dest:X} "
            f"({'in-place' if dest == span_start else 'relocation'})")
        return True

    def _block_ranges(self, blocks, segments, targets, count, rom_size):
        """Исключаемые/граничные диапазоны блоков: низ = первая цель блока,
        верх = первая цель следующего блока либо конец последней записи."""
        ranges = []
        for bs, be, blang in blocks:
            if not (0 <= bs < count and 0 <= be <= count and bs < be):
                ranges.append((0, 0))
                continue
            low = targets[bs]
            if be < count:
                high = targets[be]
            else:
                end = None
                for seg in segments:
                    if not isinstance(seg, dict):
                        continue
                    name = seg.get('name')
                    if not isinstance(name, str):
                        continue
                    if TextInjector._segment_lang(seg) != blang:
                        continue
                    seg_end = seg.get('end')
                    if (isinstance(seg_end, int) and not isinstance(seg_end, bool)
                            and 0 <= seg_end <= rom_size):
                        end = seg_end if end is None else max(end, seg_end)
                high = end if end is not None else min(low + 1, rom_size)
            if high <= low:
                ranges.append((0, 0))
                continue
            ranges.append((low, high))
        return ranges

    def inject_interleaved_language(self, lang: str, texts: list[str], plugin,
                                    segments: list | None = None,
                                    expand_if_full: bool = True) -> bool:
        """Внедряет языковой блок текста для slot-interleaved таблицы
        (MLSS: table[idx*5+slot]). Каждая запись пересобирается независимо.

        Требования к плагину: get_pointer_table_meta() -> {'table','count',
        'lang_slots','index_of', 'record_terminator', 'record_pad'} и
        get_pointer_slot_of(lang) + make_text_encoder().

        Записи с injectable=False (каталоги) пропускаются verbatim (их
        указатель и данные не трогаются). Остальные пересобираются: in-place,
        если помещаются в исходный span, иначе relocate в свободный 0x00-run
        вне всех записей всех языков и таблицы. Запись идёт по одной:
        поздний отказ не откатывает уже перенесённые записи (органично
        для per-record relocate; вызывающая сторона не должна save'ить
        после False).
        """
        self.last_spellcheck_report = []
        # Сегментных данных о ширине здесь нет — честное [] (см. core/textbox).
        self.last_fit_report = []
        self.last_overflow_report = []
        self.last_relocate_report = []
        self.last_align_report = {}
        # Симметрично `overflow/align/fit` выше:
        # контракт «отчёт = один сегмент».
        # Без сброса элементы предыдущего
        # сегмента протекали бы в следующий, а
        # census, читающий отчёты после каждого вызова,
        # отнёс бы их к текущему сегменту.
        self.last_affix_report = []
        meta = plugin.get_pointer_table_meta() if hasattr(plugin, 'get_pointer_table_meta') else None
        if not meta or not isinstance(meta, dict):
            return False
        if not isinstance(texts, (list, tuple)) or not isinstance(lang, str):
            return False
        table_offset = meta.get('table')
        count = meta.get('count')
        lang_slots = meta.get('lang_slots')
        index_of = meta.get('index_of')
        if not isinstance(table_offset, int) or isinstance(table_offset, bool):
            return False
        if not isinstance(count, int) or isinstance(count, bool):
            return False
        if not isinstance(lang_slots, dict) or lang not in lang_slots:
            return False
        if not callable(index_of):
            return False
        slot = lang_slots[lang]
        if isinstance(slot, bool) or not isinstance(slot, int):
            return False
        if table_offset < 0 or table_offset + 4 * count * max(len(lang_slots), 1) > len(self.rom.data):
            return False

        if segments is None:
            segments = self._get_segments(plugin)
        else:
            segments = self._validated(segments)
            if segments is None:
                return False
            self._segment_cache[plugin] = segments
        if not isinstance(segments, list):
            return False

        by_idx: dict[int, dict] = {}
        for s in segments:
            if not isinstance(s, dict):
                continue
            if TextInjector._segment_lang(s) == lang:
                index = s.get('index')
                if isinstance(index, bool) or not isinstance(index, int):
                    continue
                start = s.get('start')
                end = s.get('end')
                if (isinstance(start, bool) or not isinstance(start, int)
                        or isinstance(end, bool) or not isinstance(end, int)
                        or not 0 <= start <= end <= len(self.modified_data)):
                    continue
                if index in by_idx:
                    self.logger.warning(f"Дубль index={index} для '{lang}', первый выигрывает")
                by_idx.setdefault(index, s)

        # переводов должно быть ровно count
        if len(texts) != count:
            return False
        if count == 0:
            return False

        self._run_spellcheck_gate(texts, skip_long=True)

        encoder = plugin.make_text_encoder() if hasattr(plugin, 'make_text_encoder') else None
        if encoder is None:
            return False

        # занятые диапазоны: все записи всех языков + сама таблица
        occupied = [(s['start'], s['end']) for s in segments
                    if isinstance(s, dict) and isinstance(s.get('start'), int)
                    and not isinstance(s.get('start'), bool)
                    and isinstance(s.get('end'), int) and not isinstance(s.get('end'), bool)
                    and 0 <= s['start'] <= s['end'] <= len(self.modified_data)]
        occupied.append((table_offset, table_offset + 4 * count * len(lang_slots)))

        try:
            records: dict[int, bytes] = {}
            for idx in range(count):
                seg = by_idx.get(idx)
                if seg is None:
                    return False
                if not seg.get('injectable', True):
                    continue
                text = texts[idx] if idx < len(texts) else None
                if not isinstance(text, str):
                    return False
                try:
                    records[idx] = bytes(encoder.encode(text))
                except (ValueError, KeyError, IndexError, TypeError):
                    return False
        except Exception as exc:
            self.logger.debug(f"interleaved block failed: {exc}")
            return False

        from core.pointer_table import find_free_space
        changed = False
        for idx, new in records.items():
            seg = by_idx[idx]
            start, end = seg['start'], seg['end']
            if len(new) <= end - start:
                pad = _resolve_pad(seg, 0x00)
                self.modified_data[start:end] = new + bytes([pad]) * (end - start - len(new))
                changed = True
                continue
            dest = find_free_space(self.modified_data, len(new), occupied)
            if dest is None:
                if not expand_if_full:
                    return False
                try:
                    dest = self._expand_rom(len(new))
                except ValueError:
                    return False
                changed = True
            self.modified_data[start:end] = b'\x00' * (end - start)
            self.modified_data[dest:dest + len(new)] = new
            occupied.append((dest, dest + len(new)))
            try:
                entry_offset = table_offset + 4 * index_of(idx, slot)
            except (ValueError, KeyError, IndexError, TypeError):
                return False
            if (isinstance(entry_offset, bool) or not isinstance(entry_offset, int)
                    or entry_offset < 0 or entry_offset + 4 > len(self.modified_data)):
                return False
            try:
                self._patch_one_pointer(entry_offset, dest)
            except ValueError:
                return False
            changed = True

        self.logger.info(
            f"Внедрён блок '{lang}': {len(records)} записей пересобрано"
            f" (каталогов пропущено: {count - len(records)})")
        return changed

    def _patch_one_pointer(self, absolute_offset: int, target: int) -> None:
        """Записывает GBA-указатель (база 0x08000000) в absolute_offset.

        Границы проверяются вызывающей стороной; прямое нарушение —
        ValueError (fail-closed выше).
        """
        from core.pointer_table import HEADER_BASE
        if (isinstance(absolute_offset, bool) or not isinstance(absolute_offset, int)
                or isinstance(target, bool) or not isinstance(target, int)):
            raise ValueError(f"bad pointer patch args: {absolute_offset!r} {target!r}")
        if absolute_offset < 0 or absolute_offset + 4 > len(self.modified_data):
            raise ValueError(f"pointer patch outside ROM: {absolute_offset:#x}")
        if target < 0 or target >= len(self.modified_data):
            raise ValueError(f"pointer target outside ROM: {target:#x}")
        self.modified_data[absolute_offset:absolute_offset + 4] = (
            (HEADER_BASE + target) & 0xFFFFFFFF).to_bytes(4, 'little')

    def _expand_rom(self, size: int) -> int:
        """Расширяет modified_data в конец блоком 0x00 начиная с выровненного
        (0x100) смещения, гарантируя >= size байт свободного места, и
        возвращает это (выровненное) смещение."""
        from core.rom import MAX_ROM_SIZE
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise ValueError(f"bad expand size: {size!r}")
        align = 0x100
        orig = len(self.modified_data)
        dest = ((orig + align - 1) // align) * align
        if dest + size > MAX_ROM_SIZE:
            raise ValueError(f"ROM expansion past {MAX_ROM_SIZE:#x} refused")
        self.modified_data.extend(b'\x00' * ((dest - orig) + size))
        self.logger.info(f"ROM расширен до {len(self.modified_data)} байт")
        return dest

    def _inject_bank_segment(self, segment, translations: list[str],
                             skip_long: bool = True,
                             relocate: bool | None = None) -> bool:
        """Вставка переводов в банковый сегмент.

        Записи адресуются таблицей относительных смещений (bank_meta:
        {'offsets': [...], 'count': N}). Каждая запись терминируется 0x00;
        граница берётся с учётом контрольных кодов (0x00 в параметре
        control code — не терминатор). Перевод короче/равен оригиналу —
        записывается на место записи, остаток окна зануляется.

        Если relocate включён (bank_meta['relocate'] или параметром),
        запись, не влезающая в своё окно, переносится в свободную 0xFF-зону
        банка (bank_meta['free_zones']), а её offset в таблице банка
        обновляется.
        """
        meta = segment.get('bank_meta') or {}
        offsets = meta.get('offsets') or []
        if len(offsets) != len(translations):
            return False
        if not offsets:
            return True

        relocate = meta.get('relocate') if relocate is None else relocate

        original_messages = self._extract_bank_messages(segment)
        if not isinstance(translations, (list, tuple)):
            return False
        if len(original_messages) != len(translations):
            return False

        decoder = segment['decoder']
        pad_byte = _resolve_pad(segment, 0x00)
        # Тот же гард, что в generic- и pointer-путях: чужая запись поверх
        # нашей — порча, а не «перевод не применился». Раньше банковый путь
        # (Zelda TMC) писал без сверки, и тот же класс дефекта был открыт.
        injected = 0
        skipped = 0
        for i, (orig, translation) in enumerate(
                zip(original_messages, translations, strict=False)):
            if not isinstance(translation, str):
                if skip_long:
                    skipped += 1
                    continue
                return False
            try:
                trans_bytes = decoder.encode(translation)
            except (ValueError, KeyError, IndexError, TypeError):
                if skip_long:
                    skipped += 1
                    self.logger.debug(
                        f"Message {i}: cannot encode translation, skipping")
                    continue
                return False
            if not isinstance(trans_bytes, (bytes, bytearray)):
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: encoder returned non-bytes, skipping")
                    continue
                return False
            trans_bytes = bytes(trans_bytes)
            room = orig['length']
            if len(trans_bytes) > room:
                if not relocate:
                    if skip_long:
                        skipped += 1
                        self.logger.debug(
                            f"Message {i}: translation too long "
                            f"({len(trans_bytes)} > {orig['length']}), skipping")
                        continue
                    return False
                relocated = self._inject_bank_record_relocate(
                    segment, i, trans_bytes, skip_long)
                if not relocated:
                    if skip_long:
                        skipped += 1
                        self.logger.debug(
                            f"Message {i}: cannot relocate "
                            f"({len(trans_bytes)} > {orig['length']}), skipping")
                        continue
                    return False
                injected += 1
                continue
            base = segment['start'] + orig['offset']
            full = trans_bytes + bytes([pad_byte]) * (room - len(trans_bytes))
            own_lo, own_hi = self._own_span(segment)
            foreign_hit = self._foreign_hit(
                self._foreign_index(), segment.get('name'), segment,
                base, len(full), own_lo, own_hi)
            if self._check_write_overlap(base, full) == 'conflict' \
                    or foreign_hit:
                overlap_log = getattr(self, 'last_overlap_report', None)
                if overlap_log is None:
                    overlap_log = self.last_overlap_report = []
                entry = {'segment': segment.get('name', '?'), 'index': i,
                         'offset': base, 'length': len(full), 'room': room}
                if foreign_hit:
                    entry['foreign'] = True
                overlap_log.append(entry)
                if skip_long:
                    skipped += 1
                    self.logger.debug(
                        f"Message {i}: overlaps another record or segment, "
                        f"skipping")
                    continue
                return False
            if not self._safe_inject_message(base, trans_bytes, room, pad_byte):
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: out of ROM bounds, skipping")
                    continue
                return False
            # Свои записи тоже регистрируем: иначе пересечение двух
            # записей ОДНОГО банкового сегмента гард не увидит, хотя
            # generic- и pointer-пути это делают.
            self._tracked_spans().append((base, base + room))
            injected += 1

        self.logger.info(
            f"Injected {injected} bank messages, skipped {skipped}")
        return injected > 0

    def _inject_bank_record_relocate(self, segment, index: int,
                                     trans_bytes: bytes, skip_long: bool
                                     ) -> bool:
        """Переносит запись банка в свободную 0xFF-зону.

        Ищет первый подходящий блок в bank_meta['free_zones'] (не короче
        len(trans_bytes)+1, чтобы осталось место под терминатор 0x00),
        записывает туда перевод и патчит offset в таблице банка.

        Возвращает True при успехе.
        """
        meta = segment.get('bank_meta') or {}
        offsets = meta.get('offsets') or []
        if not isinstance(offsets, list):
            return False
        offsets_idx = meta.get('offsets_idx') or list(range(len(offsets)))
        if not isinstance(offsets_idx, list):
            return False
        if index < 0 or index >= len(offsets):
            return False
        table_idx = offsets_idx[index] if index < len(offsets_idx) else index
        if isinstance(table_idx, bool) or not isinstance(table_idx, int):
            return False
        base = segment.get('start')
        if isinstance(base, bool) or not isinstance(base, int):
            return False

        if table_idx == 0:
            # Слот 0 таблицы хранит N*4 (сигнатура банка) — он одновременно
            # offset первой записи. Менять его нельзя, иначе повторный скан
            # не найдёт банк.
            return False
        if table_idx < 0:
            return False

        protected = meta.get('protected_records') or []
        record_off = offsets[index]
        if isinstance(record_off, bool) or not isinstance(record_off, int):
            return False
        cur_addr = base + record_off
        if cur_addr in protected:
            return False

        size = len(trans_bytes) + 1
        dest = self._find_bank_free_block(
            segment, size, orig_abs=cur_addr, table_idx=table_idx)
        if dest is None:
            return False

        dest_rel = dest - base
        max_rel = meta.get('max_reloc_offset', 0x4000)
        if isinstance(max_rel, bool) or not isinstance(max_rel, int):
            return False
        if not (0 <= dest_rel < max_rel):
            return False

        for k in range(len(trans_bytes)):
            self.modified_data[dest + k] = trans_bytes[k]
        # Терминатор всегда влезает: _find_bank_free_block вернул pos с
        # pos+size <= ze без IndexError, size = len+1, значит
        # dest+len(trans_bytes) < len(modified_data) всегда (ветка иначе
        # недостижима).
        self.modified_data[dest + len(trans_bytes)] = 0x00

        if table_idx >= 0 and base + 4 * table_idx + 4 <= len(self.modified_data):
            struct.pack_into('<I', self.modified_data, base + 4 * table_idx,
                             dest_rel)
        self.logger.debug(
            f"Record {index} relocated to 0x{dest:06X} "
            f"(+0x{dest_rel:X}), size {size}")
        return True

    def _occupied_intervals(self) -> list[tuple[int, int]]:
        """Занятые интервалы банков в модифицированном ROM.

        Собирается из актуальных offsets, прочитанных из таблиц в
        current modified_data (не из bank_meta), чтобы после relocate
        одной записи следующая не заняла её прежнее место.

        Возвращает отсортированный список (start, end) адресуемых записей.
        """
        occupied: list[tuple[int, int]] = []
        for segment in self._bank_segments:
            if not isinstance(segment, dict):
                continue
            meta = segment.get('bank_meta') or {}
            if not meta:
                continue
            cc = meta.get('control_codes') or {}
            base = segment.get('start')
            table_count = meta.get('table_count') or 0
            end = meta.get('record_end') or segment.get('end')
            zone_end = meta.get('zone_end', end)
            if (isinstance(base, bool) or not isinstance(base, int)
                    or isinstance(table_count, bool) or not isinstance(table_count, int)
                    or isinstance(end, bool) or not isinstance(end, int)
                    or isinstance(zone_end, bool) or not isinstance(zone_end, int)):
                continue
            for idx in range(table_count):
                slot = base + 4 * idx
                if slot < 0 or slot + 4 > len(self.modified_data):
                    continue
                v = struct.unpack_from('<I', self.modified_data, slot)[0]
                s = base + v
                if s < 0 or s >= len(self.modified_data):
                    continue
                bound_end = zone_end if s >= end else end
                e = self._bank_record_bound(self.modified_data, s, bound_end, cc)
                if e <= s:
                    continue
                occupied.append((s, e))
        occupied.sort()
        return occupied

    def _find_bank_free_block(self, segment, size: int, *,
                              orig_abs: int, table_idx: int) -> int | None:
        """Адрес свободного 0xFF-блока длины size для relocate записи.

        Учитывает зоны bank_meta['free_zones'], занятые интервалы из
        актуальных таблиц и сохранённые dest блоки (этот сегмент).
        """
        meta = segment.get('bank_meta') or {}
        free_zones = meta.get('free_zones') or []
        max_rel = meta.get('max_reloc_offset', 0x4000)
        base = segment['start']
        if not isinstance(max_rel, int) or isinstance(max_rel, bool) or max_rel < 0:
            return None
        if not isinstance(free_zones, list):
            return None

        occupied = self._occupied_intervals()
        occupied_all = occupied + getattr(self, '_taken_free_blocks', [])
        rom_len = len(self.modified_data)

        for zone in free_zones:
            try:
                zs, ze = int(zone[0]), int(zone[1])
            except (ValueError, TypeError, IndexError):
                continue
            zs = max(0, zs)
            ze = min(ze, base + max_rel + 1, rom_len)
            if zs >= ze:
                continue
            pos = zs
            while pos + size <= ze:
                if all(self.modified_data[p] == 0xFF
                       for p in range(pos, pos + size)):
                    if self._interval_free((pos, pos + size), occupied_all,
                                           orig_abs):
                        taken = self._taken_free_blocks
                        taken.append((pos, pos + size))
                        self._taken_free_blocks = taken
                        return pos
                pos += 1
        return None

    def _interval_free(self, span: tuple[int, int],
                       occupied: list[tuple[int, int]],
                       orig_abs: int) -> bool:
        """True, если span не пересекается с занятыми интервалами.

        orig_abs исключается из проверки (свою же старую запись можно
        перезаписать, её адрес мы больше не используем после relocate).
        """
        s, e = span
        for os_, oe in occupied:
            if orig_abs == os_:
                continue
            if s < oe and os_ < e:
                return False
        return True

    def _bank_record_bound(self, data: bytes | bytearray, start: int, end: int,
                           control_codes: dict[int, int] | None = None) -> int:
        """Конец записи банка: первая 0x00 вне контрольных кодов."""
        control_codes = control_codes or {}
        i = start
        while i < end:
            byte = data[i]
            if byte == 0x00:
                return i
            if byte in control_codes:
                i += 1 + control_codes[byte]
                continue
            i += 1
        return end

    def _extract_bank_messages(self, segment) -> list[dict]:
        """Оригинальные сообщения банка по актуальной таблице offsets.

        Адрес каждой записи читается из ЖИВОЙ таблицы в modified_data
        (слот base+4*offsets_idx[i]) — после relocate таблица указывает
        на новое место, и повторная инъекция не должна писать по старому.
        Если indexes отсутствуют или слот нечитаем, берётся offset из meta.

        Записи, перенесённые в свободную зону, лежат за record_end —
        для них граница берётся по zone_end (конец зоны этого банка).
        """
        meta = segment.get('bank_meta') or {}
        offsets = meta.get('offsets') or []
        offsets_idx = meta.get('offsets_idx') or list(range(len(offsets)))
        control_codes = meta.get('control_codes') or {}
        start = segment['start']
        end = segment['end']
        zone_end = meta.get('zone_end', end)
        data = self.modified_data
        decoder = segment['decoder']

        msgs: list[dict] = []
        for i, rel0 in enumerate(offsets):
            rel = rel0
            idx = offsets_idx[i] if i < len(offsets_idx) else i
            slot = start + 4 * idx
            if slot + 4 <= len(data):
                v = struct.unpack_from('<I', data, slot)[0]
                if v < len(data):
                    rel = v
            msg_start = start + rel
            if msg_start >= len(data):
                continue
            bound_end = zone_end if msg_start >= end else end
            msg_end = min(self._bank_record_bound(
                data, msg_start, bound_end, control_codes), len(data))
            msg_len = msg_end - msg_start
            if msg_len > 0:
                try:
                    if hasattr(decoder, '_decode_one'):
                        text = decoder._decode_one(data, msg_start, msg_end)
                    else:
                        # CharMapDecoder не имеет _decode_one; банковые сегменты
                        # обычно используют TMCTextDecoder, но подстраховываемся
                        text = decoder.decode(data, msg_start, msg_len)
                except Exception:
                    self.logger.exception(
                        "Bank message decode failed for rel=%#x msg_start=%#x",
                        rel, msg_start,
                    )
                    text = ""
                msgs.append({
                    'offset': rel,
                    'length': msg_len,
                    'text': text,
                })
        return msgs

    def _ensure_decoder(self, segment):
        """Гарантирует, что у сегмента есть decoder"""
        if not segment.get('decoder'):
            try:
                from core.decoder import CharMapDecoder
                from core.scanner import auto_detect_charmap
                charmap = auto_detect_charmap(self.rom.data, segment['start'],
                                              prefer_lang=segment.get('lang'))
                segment['decoder'] = CharMapDecoder(charmap)
            except Exception as exc:
                self.logger.debug(f"Decoder autodetect failed: {exc}")
                segment['decoder'] = None

    def _align_translations_to_manifest(self, segment: dict, translations: list) -> list | None:
        """Выравнивает переводы по манифесту через пустые слоты (ромхаки).

        Непустые слоты потребляют переводы по порядку манифеста (= порядку
        экстрактора), пустые получают "" (добить пустой слот переводом
        нельзя — только через прямую запись). Пустота определяется
        декодированием pristine rom.data (не modified_data) с лимитом
        max_decode_len сегмента (дефолт 320, как у экстрактора).
        Несогласованность (лишние переводы или нехватка) → None.
        Пустой вход при пустом выходе → [].
        """
        manifest = segment.get('manifest') or []
        decoder = segment.get('decoder')
        if decoder is None or not isinstance(translations, (list, tuple)):
            return None
        if not isinstance(manifest, list):
            return None
        data = self.rom.data
        aligned: list = []
        pending = list(translations)
        for entry in manifest:
            if not isinstance(entry, dict):
                return None
            addr = entry.get('target')
            room = entry.get('free_after', 0)
            if isinstance(room, bool) or not isinstance(room, int):
                return None
            text = ""
            if isinstance(addr, int) and not isinstance(addr, bool) and 0 <= addr < len(data) and room > 0:
                try:
                    max_decode = segment.get('max_decode_len', 320)
                    if isinstance(max_decode, bool) or not isinstance(max_decode, int):
                        max_decode = 320
                    max_decode = min(max_decode, room, len(data) - addr)
                    # Декодируем ТОЧНО так же, как экстрактор: полный буфер и
                    # абсолютный адрес. Раньше здесь передавался срез
                    # `data[addr:addr+n]` с нулевым смещением, и у декодеров с
                    # контекстной разметкой (Pokemon смотрит на байты вокруг
                    # адреса) результат отличался от извлечения. Расхождение
                    # означало, что запись, пропущенная экстрактором, здесь
                    # считалась непустой — и ВСЕ ПОСЛЕДУЮЩИЕ переводы сдвигались
                    # на одну позицию, попадая в чужие адреса.
                    text = decoder.decode(data, addr, max_decode)
                except Exception as exc:
                    self.logger.debug(f"Align decode failed at {addr:#x}: {exc}")
                    text = ""
            if not text.strip():
                aligned.append("")
            elif not pending:
                return None
            else:
                aligned.append(pending.pop(0))
        if pending:
            return None
        return aligned

    def _inject_pointer_dialogues(self, segment, translations: list[str],
                                    skip_long: bool,
                                    relocate: bool | None = None) -> bool:
        """Вставка в pointer-пул диалогов: in-place + релокация длинных.

        ORDER: плагин держит entries в манифесте отсортированными, экстрактор
        отдаёт сообщения в том же порядке — translations зипуются 1:1.
        Ромхаки с зачищенными (пустыми) слотами: extractor пропускает их,
        поэтому translations короче manifest — такие слоты выравниваются ""
        через _align_translations_to_manifest; прочий mismatch — отказ.
        Перевод длиннее room (free_after): при relocate — перенос в свободный
        00-run с патчем указателей из entry['slots'] (LE, +0x08000000);
        иначе пропуск при skip_long (иначе False). Пропущенные попадают
        в self.last_overflow_report (видимый отчёт GUI).
        relocate=None — пытаться, если слоты известны, иначе пропуск
        (старое поведение — только при relocate=False).
        Хвост окна за новым терминатором НЕ перезаписывается (там лежат
        исходные 0xFF-пады/соседние данные — их зануление вешало загрузку).
        Пропуск — только когда окно УЖЕ показывает перевод: байты совпали
        с payload либо живой декод окна равен переводу (вариантные написания
        одного текста тоже пропускаются — diff минимален).
        True = «без отказов» (idempotent: all-identity тоже True).
        Хвост опирается на терминатор — путь только для терминированных
        окон; пропуск резервирует окно в _tracked_spans, повторная запись
        того же окна в сессии — conflict/skip.
        """
        decoder = segment.get('decoder')
        self.last_overflow_report = []
        self.last_relocate_report = []
        self.last_overlap_report = []
        # Обнуляется здесь, а не выше: гейт `empty_translation` ниже пишет
        # именно в этот отчёт. Раньше он не сбрасывался на этом пути, и
        # отчёт предыдущего сегмента протекал бы в следующий.
        self.last_affix_report = []
        if decoder is None:
            return False
        manifest = segment.get('manifest') or []
        if not isinstance(manifest, list):
            return False
        if not isinstance(translations, (list, tuple)):
            return False
        if len(translations) != len(manifest):
            aligned = self._align_translations_to_manifest(segment, translations)
            if aligned is None:
                return False
            translations = aligned
        if not translations:
            return True
        snapshot = bytes(self.modified_data)
        spans_mark = len(self._tracked_spans())
        relocate_mark = len(self.last_relocate_report)

        def _fail() -> bool:
            self.modified_data[:] = snapshot
            del self._tracked_spans()[spans_mark:]
            del self.last_relocate_report[relocate_mark:]
            # Кэш начал прогонов держит ссылку на список из сотен тысяч пар
            # (~130 МБ на 16 МБ ROM), а gui держит инжектор живым всю сессию.
            # На любом пути выхода он обязан быть сброшен.
            self._free_starts_cache: dict | None = None
            return False

        def _track(span: tuple[int, int]) -> None:
            spans = self._tracked_spans()
            if span not in spans:
                spans.append(span)

        injected = 0
        skipped = 0
        encoder = segment.get('pointer_encoder')
        if encoder is None:
            encoder = decoder.encode
        # Пад этого сегмента нужен гейту ниже: окно считается «пустым» только
        # если в нём нет байтов, отличных от пада.
        pad_byte = _resolve_pad(segment, 0x00)
        free_runs: list[tuple[int, int]] | None = None
        foreign_idx = self._foreign_index()
        for entry, translation in zip(manifest, translations,
                                        strict=False):
            if not isinstance(entry, dict):
                if skip_long:
                    skipped += 1
                    continue
                return _fail()
            addr = entry.get('target')
            room = entry.get('free_after')
            if (isinstance(addr, bool) or not isinstance(addr, int)
                    or isinstance(room, bool) or not isinstance(room, int)):
                if skip_long:
                    skipped += 1
                    continue
                return _fail()
            if not isinstance(translation, str):
                if skip_long:
                    skipped += 1
                    continue
                return _fail()
            # Гейт ниже ловит перевод, который в pristine ROM занимал
            # ненулевой слот: ' the ' -> ' ' писалось как `20 00 00 00 00 00`.
            #
            # Гейт срабатывает ТОЛЬКО если слот непустой в pristine ROM.
            # У ROM-хаков со сдвигом окон пустой слот — легитимная запись
            # (`_align_translations_to_manifest` сам подставляет "" в пустые
            # слоты), и её пустой перевод стирать нечего.
            if not translation.strip():
                pristine = self.rom.data[addr:addr + max(room, 0)]
                # Слот пуст не только когда в нём один байт заполнения: у
                # pointer-сегментов хвост заполнен ТЕРМИНАТОРАМИ (0x00, 0xFF),
                # а не байтом заполнения. Слот `FF FF` читается как пустая
                # запись — стирать нечего.
                voids = {pad_byte}
                for term in segment.get('terminators') or ():
                    if (isinstance(term, int) and not isinstance(term, bool)
                            and 0 <= term <= 255):
                        voids.add(term)
                # `terminator` (многобайтовый) — тоже пустота: слот `FF FF`
                # не содержит текста и стирать его нечего.
                payload_term = segment.get('terminator')
                if isinstance(payload_term, (bytes, bytearray)):
                    voids.update(payload_term)
                if pristine.strip(bytes(sorted(voids))):
                    self.last_affix_report.append({
                        'segment': segment.get('name'),
                        'offset': addr,
                        'length': len(translation),
                        'room': room,
                        'reason': 'empty_translation',
                        'text': translation,
                    })
                    if skip_long:
                        skipped += 1
                        continue
                    return _fail()
            try:
                trans_bytes = encoder(translation)
            except TypeError:
                # Энкодер, которому нужно текущее состояние буфера
                # (Oracle of Seasons сжимает против СОДЕРЖИМОГО словаря):
                # без живых данных он ссылался бы на старое содержимое и
                # после перевода словаря развернулся бы в чужой текст.
                try:
                    trans_bytes = encoder(translation, self.modified_data)
                except TypeError:
                    if skip_long:
                        skipped += 1
                        continue
                    return _fail()
                except (ValueError, KeyError, IndexError):
                    if skip_long:
                        skipped += 1
                        continue
                    return _fail()
            except (ValueError, KeyError, IndexError):
                if skip_long:
                    skipped += 1
                    continue
                return _fail()
            if not isinstance(trans_bytes, (bytes, bytearray)):
                if skip_long:
                    skipped += 1
                    continue
                return _fail()
            trans_bytes = bytes(trans_bytes)
            payload_terminator = segment.get('terminator', b'\xff')
            if not isinstance(payload_terminator, (bytes, bytearray)):
                self.last_overflow_report.append({
                    'target': addr,
                    'free_after': room,
                    'length': -1,
                    'text': translation if isinstance(translation, str) else '',
                })
                if skip_long:
                    skipped += 1
                    continue
                return _fail()
            payload_terminator = bytes(payload_terminator)
            payload = trans_bytes + payload_terminator
            if addr < 0 or room < 0 or addr + room > len(self.modified_data):
                if skip_long:
                    skipped += 1
                    continue
                return _fail()
            if len(payload) > room:
                relocated = False
                if (relocate is None or relocate) and len(payload_terminator) > 0:
                    if free_runs is None:
                        free_runs = self._scan_free_space_runs(self.modified_data)
                    relocated = self._relocate_dialogue(
                        manifest, entry, addr, payload, free_runs,
                        own_name=segment.get('name') if isinstance(segment, dict) else None)
                if relocated:
                    injected += 1
                    continue
                self.last_overflow_report.append({
                    'target': addr,
                    'free_after': room,
                    'length': len(payload),
                    'text': translation,
                })
                if skip_long:
                    skipped += 1
                    continue
                return _fail()
            live = bytes(self.modified_data[addr:addr + len(payload)])
            if live == payload:
                _track((addr, addr + room))
                injected += 1
                continue
            max_decode = segment.get('max_decode_len', 320)
            if isinstance(max_decode, bool) or not isinstance(max_decode, int):
                max_decode = 320
            max_decode = min(max_decode, room, len(self.modified_data) - addr)
            try:
                live_text = decoder.decode(
                    self.modified_data, addr, max_decode)
            except Exception as exc:
                # Best-effort пропуск: любой сбой живого декода ведёт
                # на обычный путь записи (там свои strict-гейты).
                self.logger.debug(f"Dialogue @{addr:#x} live-decode failed: {exc}")
                live_text = None
            if isinstance(live_text, str) and live_text == translation:
                _track((addr, addr + room))
                injected += 1
                continue
            if segment.get('tail_pad') and len(payload) < room:
                _pad = _resolve_pad(segment, 0x00)
                full = payload + bytes([_pad]) * (room - len(payload))
            else:
                full = payload + bytes(
                    self.modified_data[addr + len(payload):addr + room])
            # Алиасы той же записи отсечены внутри `_foreign_hit`
            # (по `alias_of` + окну внутри своего окна), поэтому здесь
            # обычная проверка пересечения.
            foreign_hit = self._foreign_hit(
                foreign_idx, segment.get('name'), segment, addr, len(full))
            if self._check_write_overlap(addr, full) == 'conflict' \
                    or foreign_hit:
                overlap_log = getattr(self, 'last_overlap_report', None)
                if overlap_log is None:
                    overlap_log = self.last_overlap_report = []
                entry = {
                    'segment': segment.get('name', '?'), 'target': addr,
                    'length': room, 'room': room,
                }
                if foreign_hit:
                    # Помечаем явно: иначе в отчёте не отличить «пересеклась
                    # предыдущая запись» от «пересекся чужой сегмент».
                    entry['foreign'] = True
                overlap_log.append(entry)
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Dialogue @{addr:#x} overlaps a previous write, skipping")
                    continue
                return _fail()
            if not self._safe_inject_message(addr, full, room, 0x00):
                if skip_long:
                    skipped += 1
                    continue
                return _fail()
            _track((addr, addr + room))
            injected += 1
        # Кэш начал прогонов нужен только на время этого прохода (см. _fail).
        self._free_starts_cache = None
        self.logger.info(
            f"[pointer_dialogues] injected {injected}, skipped {skipped}")
        return injected > 0

    def _relocate_dialogue(self, manifest, entry, addr: int,
                           payload: bytes,
                           free_runs: list[tuple[int, int]] | None = None,
                           own_name: str | None = None) -> bool:
        """Перенос длинного перевода в свободный 00-run + патч указателей.

        entry['slots'] — ячейки LE-указателей (target + 0x08000000).
        Патчатся только ячейки, указывающие на addr сейчас; остальные
        (мусор манифеста другой ревизии) не трогаются и попадают в отчёт
        как skipped. Если НИ ОДНА не указывает на addr — отказ, кроме
        idempotent-случая: все указывают на одну цель с этим же payload
        (повторный инжект после релокейта) — успех без записи.
        Свободное место — верхний 00-run вне окон манифеста, ячеек таблицы
        и уже записанного (runs сканируются один раз на вызов и сплитятся
        по мере аллокаций); старое окно не затирается (остаётся как было,
        движок его больше не читает). Зеркальные указатели (0x09..., не
        HEADER_BASE) не поддерживаются — только 0x08 LE.
        Успех пишется в last_relocate_report. Возвращает True при успехе
        (всё записано целиком) иначе False без частичных записей.
        Прямой вызов обходит терминатор-гард вызывающей стороны:
        пустой payload отклоняется здесь же.
        """
        from core.pointer_table import HEADER_BASE
        log = self.logger
        if not isinstance(payload, (bytes, bytearray)) or not payload \
                or not isinstance(manifest, list) or not isinstance(entry, dict):
            log.debug("Relocate refused: bad payload/manifest/entry")
            return False
        if isinstance(addr, bool) or not isinstance(addr, int) or addr < 0:
            log.debug(f"Relocate refused: bad addr {addr!r}")
            return False
        slots = entry.get('slots')
        if not isinstance(slots, (list, tuple)) or not slots:
            log.debug(f"Dialogue @{addr:#x}: no pointer slots, no relocate")
            return False
        rom_len = len(self.modified_data)
        if addr >= rom_len:
            log.debug("Relocate refused: target outside ROM")
            return False
        # РЕЖИМ АДРЕСАЦИИ. GBA: 32-битный указатель 0x08+addr в слоте.
        # GB/GBC: 16-битное значение, отсчитанное от базы группы, плюс банк
        # выбирается индексом записи, а не этим значением. Поэтому для
        # GB/GBC перенос допустим ТОЛЬКО внутри того же банка.
        slot_size = entry.get('slot_size', 4)
        if isinstance(slot_size, bool) or slot_size not in (2, 4):
            log.debug(f"Dialogue @{addr:#x}: bad slot_size {slot_size!r}")
            return False
        raw_base = entry.get('reloc_base')
        gbc = slot_size == 2
        reloc_base = 0
        if gbc:
            if isinstance(raw_base, bool) or not isinstance(raw_base, int):
                log.debug(f"Dialogue @{addr:#x}: 16-bit slot without base")
                return False
            # Приводим к int здесь: дальше база участвует в арифметике адресов,
            # и Optional здесь означал бы роняющий инжектор TypeError.
            reloc_base = int(raw_base)
            wanted = addr - reloc_base
        else:
            wanted = (addr + HEADER_BASE) & 0xFFFFFFFF
        if gbc and not 0 <= wanted <= 0xFFFF:
            log.debug(f"Dialogue @{addr:#x}: offset {wanted} outside 16-bit window")
            return False
        if gbc:
            origin = entry.get('target')
            if isinstance(origin, bool) or not isinstance(origin, int):
                log.debug(f"Dialogue @{addr:#x}: 16-bit slot without target")
                return False
            if _gb_bank_of(addr) != _gb_bank_of(origin):
                log.debug(f"Dialogue @{addr:#x}: base bank differs, refuse")
                return False
        # Слоты делятся на «указывает сюда» и «указывает куда-то ещё».
        # Вторые НЕ патчатся: на Odyssey в списке слотов манифеста попадаются
        # байты ARM-кода (например 0x09064B74 в слоте 0x3E02B8 записи
        # 0x417E50), и перезапись такого «указателя» сломала бы код. Такие
        # записи теряют перенос — см. ROADMAP.
        cells: list[int] = []
        skipped_cells: list[int] = []
        for cell in slots:
            if isinstance(cell, bool) or not isinstance(cell, int):
                log.debug(f"Dialogue @{addr:#x}: bad slot {cell!r}")
                return False
            if not 0 <= cell or cell + slot_size > rom_len:
                log.debug(f"Dialogue @{addr:#x}: slot @{cell:#x} out of range")
                return False
            if cell in cells or cell in skipped_cells:
                continue
            current = int.from_bytes(
                self.modified_data[cell:cell + slot_size], 'little')
            if current == wanted:
                cells.append(cell)
            else:
                skipped_cells.append(cell)
        reserved: list[tuple[int, int]] = []
        for ent in manifest:
            if not isinstance(ent, dict):
                continue
            base = ent.get('target')
            size = ent.get('free_after')
            if isinstance(base, int) and not isinstance(base, bool) \
                    and isinstance(size, int) and not isinstance(size, bool) \
                    and base >= 0 and size > 0 and base + size <= rom_len:
                reserved.append((base, base + size))
        for cell in cells:
            reserved.append((cell, cell + slot_size))
        if not cells and skipped_cells and len({int.from_bytes(
                self.modified_data[c:c + slot_size], 'little')
                for c in skipped_cells}) == 1:
            other = int.from_bytes(
                self.modified_data[skipped_cells[0]:skipped_cells[0] + slot_size],
                'little')
            other = other - reloc_base if gbc else other - HEADER_BASE
            owned = any(a <= other and other + len(payload) <= b
                        for a, b in self._tracked_spans())
            # len>4: короткие совпадения (нули/FF) слишком вероятны случайно.
            if 0 <= other and other + len(payload) <= rom_len \
                    and (owned or (len(payload) > 4 and not any(
                        other < b and a < other + len(payload)
                        for a, b in reserved))) \
                    and bytes(self.modified_data[other:other + len(payload)]) == payload:
                new_spans = [(other, other + len(payload))] + \
                    [(cell, cell + slot_size) for cell in skipped_cells]
                for span in new_spans:
                    if span not in self._tracked_spans():
                        self._tracked_spans().append(span)
                self.last_relocate_report.append(
                    {'target': addr, 'dest': other,
                     'pointers': list(skipped_cells), 'relocated': False})
                return True
            log.debug(f"Dialogue @{addr:#x}: pointers moved elsewhere, refuse")
            return False
        if not cells:
            log.debug(f"Dialogue @{addr:#x}: pointers disagree, refuse")
            return False
        occupied: list[tuple[int, int]] = list(reserved)
        occupied.extend(self._tracked_spans())
        occupied.extend(self._foreign_ranges(own_name))
        free_runs_owned_here = free_runs is None
        if free_runs is None:
            free_runs = self._scan_free_space_runs(self.modified_data)
        if not isinstance(free_runs, list):
            return False
        payload_len = len(payload)
        dest = None
        try:
            starts, ends = self._disjoint_intervals(occupied)
            for start, stop in reversed(free_runs):
                if stop - start < payload_len:
                    continue
                if start < 0 or stop > rom_len or start >= stop:
                    continue
                cand = stop - payload_len
                if cand < 0:
                    continue
                if not self._hits_disjoint(starts, ends, cand,
                                            cand + payload_len):
                    dest = cand
                    break
        except (ValueError, TypeError):
            log.debug(f"Dialogue @{addr:#x}: bad free_runs entry")
            return False
        if dest is None or dest + payload_len > rom_len:
            log.debug(f"Dialogue @{addr:#x}: no free run for {payload_len} bytes")
            return False
        if self._check_write_overlap(dest, payload) == 'conflict':
            log.debug(f"Dialogue @{addr:#x}: dest @{dest:#x} conflicts, refuse")
            return False
        if gbc:
            dest_value = dest - reloc_base
            if not 0 <= dest_value <= 0xFFFF:
                log.debug(f"Dialogue @{addr:#x}: dest outside 16-bit window")
                return False
            if _gb_bank_of(dest) != _gb_bank_of(addr):
                log.debug(f"Dialogue @{addr:#x}: dest in another bank, refuse")
                return False
        else:
            dest_value = (dest + HEADER_BASE) & 0xFFFFFFFF
        patched = dest_value.to_bytes(slot_size, 'little')
        for cell in cells:
            if self._check_write_overlap(cell, patched) == 'conflict':
                log.debug(f"Dialogue @{addr:#x}: slot @{cell:#x} conflicts, refuse")
                return False
        # Пометка relocated_from НЕ выставляется: extractor читает её как
        # «цель уже разрешена вызывающим» и пропускает разбор слота, а манифест
        # лежит в кэше сегментов инжектора — пометка пережила бы инъекцию и
        # ломала обратное извлечение в том же процессе.
        self.modified_data[dest:dest + len(payload)] = payload
        for cell in cells:
            self.modified_data[cell:cell + slot_size] = patched
        # Старый блок освобождаем. Он больше не адресуем (все его слоты
        # переписаны выше), поэтому оставленный там оригинал — это просто
        # мусор, который ещё и МАСКИРУЕТ перенос: обратное извлечение по
        # статическому манифесту читает target и видит оригинал вместо
        # перевода. Нули в старом блоке — надёжный признак «здесь был
        # перенос», в отличие от эвристики «похоже на текст?», которая
        # ломалась и на хаках, и на блоках, начинающихся с 0x00/0xFF.
        # Границу берём ту же, что инжектор уже считает своей для записи
        # на место (room = free_after): если region перекрывал бы чужие
        # данные, in-place вставка давно бы их испортила.
        room_old = entry.get('free_after')
        freed = 0
        if isinstance(room_old, int) and not isinstance(room_old, bool) \
                and 0 < room_old and addr + room_old <= len(self.modified_data):
            self.modified_data[addr:addr + room_old] = bytes(room_old)
            freed = room_old
        _track = self._tracked_spans()
        spans = [(dest, dest + payload_len)]
        if freed:
            spans.append((addr, addr + freed))
        spans.extend((cell, cell + 4) for cell in cells)
        for span in spans:
            if span not in _track:
                _track.append(span)
        if not self._consume_free_run(free_runs, dest, payload_len):
            # Недостижимо: dest = stop - payload_len, значит содержащий его
            # прогон есть и bisect указывает ровно на него. Но молчание здесь
            # сделало бы будущую регрессию невидимой — цена отказа лишь потеря
            # учёта места, порчи тут быть не может: запись уже учтена в
            # _tracked_spans, а _check_write_overlap отработал выше.
            self.logger.warning(
                f"Dialogue @{addr:#x}: dest @{dest:#X} вне учёта прогонов")
        if free_runs_owned_here:
            self._free_starts_cache = None
        self.last_relocate_report.append(
            {'target': addr, 'dest': dest,
             'pointers': list(cells), 'skipped_pointers': list(skipped_cells),
             'relocated': True})
        self.logger.info(
            f"Dialogue @{addr:#x} relocated to 0x{dest:X} "
            f"({len(cells)} pointer(s))")
        return True

    @staticmethod
    def _disjoint_intervals(
            intervals: list) -> tuple[list[int], list[int]]:
        """Занятые интервалы как непересекающиеся, отсортированные по началу.

        `_relocate_dialogue` спрашивает «есть ли интервал, пересекающий
        `[a, b)`» по несколько тысяч раз на каждый перенос, и линейный
        `any()` по всем занятым окнам делал это квадратичным: на Emerald это
        ~2 млрд сравнений на 2089 переносов. После слияния пересекающихся
        интервалов ответ даётся двумя бисектами.

        Мусор во входе (не-пара, не-целые, пустой или инвертированный
        интервал) ВЫБРАСЫВАЕТСЯ, а не пропускается: раньше такой вход ронял
        `any()` в TypeError, и `_relocate_dialogue` отказывался переносить.
        Молча выбросить «чужое» окно значило бы разрешить запись поверх
        игровых данных — единственный барьер здесь один, `_check_write_overlap`
        чужие диапазоны не видит.
        """
        pairs: list
        try:
            pairs = sorted(intervals)
        except TypeError as exc:
            raise ValueError(f'bad occupied interval: {exc}') from exc
        starts: list[int] = []
        ends: list[int] = []
        try:
            for a, b in pairs:
                if not a < b:
                    raise ValueError(f'bad occupied interval: {a!r}, {b!r}')
                if ends and a <= ends[-1]:
                    if b > ends[-1]:
                        ends[-1] = b
                else:
                    starts.append(a)
                    ends.append(b)
        except TypeError as exc:
            raise ValueError(f'bad occupied interval: {exc}') from exc
        return starts, ends

    @staticmethod
    def _hits_disjoint(starts: list[int], ends: list[int],
                       a: int, b: int) -> bool:
        """Пересекает ли `[a, b)` один из непересекающихся интервалов."""
        i = bisect_right(starts, a) - 1
        if i >= 0 and ends[i] > a:
            return True  # интервал накрывает начало записи
        j = i + 1
        return j < len(starts) and starts[j] < b

    def _consume_free_run(self, free_runs: list, dest: int,
                          payload_len: int) -> bool:
        """Учитывает, что место `[dest, ...)` в `free_runs` занято.

        Кандидат всегда выбирается как `stop - len(payload)`, то есть запись
        идёт в САМЫЙ ВЕРХ прогона, и правый остаток невозможен: остаётся
        только левый `[start, dest)`. Поэтому список не требует ни вставок,
        ни `del`, а исходный линейный проход по всем прогонам (на Emerald
        это 966 899 прогонов × 2089 переносов = 2 млрд итераций) заменяется
        бисектом.

        Список после правки остаётся отсортированным по началу — в отличие от
        прежнего кода, который удалял элемент из середины и дописывал остатки
        в конец, ломая порядок. Поэтому `reversed(free_runs)` и дальше
        означает «от самого высокого адреса», а выбор места становится
        предсказуемым; корректность от этого не зависит: кандидат в любом
        случае проверяется на пересечение с занятыми интервалами.

        Список, не отсортированный по началу (его может прислать внешний
        вызывающий), обрабатывается исходным линейным проходом.
        """
        try:
            starts = self._free_starts(free_runs)
            if starts is None:
                for i, (start, stop) in enumerate(free_runs):
                    if start <= dest and dest + payload_len <= stop:
                        self._shrink_free_run(free_runs, None, i, start, stop,
                                              dest, payload_len)
                        return True
                return False
            i = bisect_right(starts, dest) - 1
            if 0 <= i < len(starts):
                start, stop = free_runs[i]
                if start == starts[i] and start <= dest \
                        and dest + payload_len <= stop:
                    self._shrink_free_run(free_runs, starts, i, start, stop,
                                          dest, payload_len)
                    return True
        except (ValueError, TypeError, IndexError):
            self.logger.debug(f"bad free_runs entry near {dest:#x}")
        return False

    @staticmethod
    def _shrink_free_run(free_runs: list, starts: list[int] | None, i: int,
                         start: int, stop: int, dest: int,
                         payload_len: int) -> None:
        """Укорачивает прогон `i` до `[start, dest)` и добавляет правый остаток.

        Кандидат всегда `stop - len(payload)`, поэтому правый остаток на
        практике пуст (ветка ниже недостижима из `_relocate_dialogue`), но
        метод публично принимает список прогонов, и потеря свободного места
        была бы тихой. Вставка идёт по индексу, а не в конец, — сортировка
        списка сохраняется.
        """
        free_runs[i] = (start, dest) if start < dest else (start, start)
        if dest + payload_len < stop:
            right = (dest + payload_len, stop)
            if starts is None:
                # Порядок чужой: сортировку не поддерживаем, но и не теряем
                # место — порядок всё равно будет перечитан.
                free_runs.append(right)
            else:
                free_runs.insert(i + 1, right)
                starts.insert(i + 1, right[0])

    def _free_starts(self, free_runs: list) -> list[int] | None:
        """Начала прогонов по возрастанию, либо None если порядок чужой.

        Кэш по САМОМУ объекту списка: `id()` переиспользуется, и новый список
        с тем же id получил бы чужие начала (та же ошибка, что была с индексом
        чужих диапазонов). Список мы правим на месте, поэтому пересчёт не
        нужен — меняется только конец прогона, а не порядок.
        """
        cache = getattr(self, '_free_starts_cache', None)
        if cache is not None and cache.get('src') is free_runs:
            cached: list[int] | None = cache.get('starts')
            return cached
        starts: list[int] | None
        ordered = True
        prev = -1
        try:
            for pair in free_runs:
                a = pair[0]
                if a < prev:
                    ordered = False
                    break
                prev = a
            starts = [pair[0] for pair in free_runs] if ordered else None
        except (TypeError, IndexError, KeyError):
            starts = None
        self._free_starts_cache = {'src': free_runs, 'starts': starts}
        return starts

    @staticmethod
    def _scan_free_space_runs(data: bytes | bytearray) -> list[tuple[int, int]]:
        """Все 00-run'ы ROM сверху вниз для последовательных аллокаций."""
        import re
        buf = bytes(data)
        return [(m.start(), m.end()) for m in re.finditer(b"\x00+", buf)]

    @staticmethod
    def _dialogue_record_ranges(seg: dict, rom_size: int) -> list[tuple[int, int]]:
        """Окна отдельных записей диалогового пула из его манифеста."""
        out: list[tuple[int, int]] = []
        manifest = seg.get('manifest')
        if not isinstance(manifest, list):
            return out
        for entry in manifest:
            if not isinstance(entry, dict):
                continue
            start = entry.get('target')
            room = entry.get('free_after')
            if isinstance(start, bool) or not isinstance(start, int):
                continue
            if isinstance(room, bool) or not isinstance(room, int) or room <= 0:
                continue
            if 0 <= start and start + room <= rom_size:
                out.append((start, start + room))
        return out

    def _foreign_index(self) -> list:
        """Индекс чужих диапазонов: отсортированные окна всех сегментов.

        Строится ОДИН раз на неизменный состав сегментов. Раньше
        `_foreign_ranges` пересобирал весь список на КАЖДЫЙ сегмент: на
        Golden Sun это 10863 × 10863 окон, то есть 118 млн вызовов
        `_coarse_range` и 711 секунд на один тест. Теперь перебор делается
        один раз, а запрос идёт через bisect.

        Признак «состав не изменился» — САМИ списки сегментов (сравнение по
        `is`, ссылки удерживаются в `_foreign_index_src`), а не их `id`:
        `id()` освобождённого списка переиспользуется, и новый список с тем
        же id и той же длиной получал бы чужой индекс. Плюс в признак входит
        размер буфера, потому что от него зависят `_coarse_range` и
        `_dialogue_record_ranges`. Сброса нет намеренно.

        Элемент индекса: `(start, end, owner_id, owner_name, is_readonly,
        alias_of, is_pool, seg_start, seg_end, prefix_max_end)`, отсортированный
        по началу. `seg_start`/`seg_end` — окно СЕГМЕНТА владельца: у пула
        диалогов в индексе лежат по-записные окна, а «тот же сегмент» нужно
        отсекать по окну сегмента, а не по окну записи. `is_readonly`
        (`injectable is False`) и `is_pool` нужны, чтобы предикат алиаса
        совпадал с `_foreign_ranges` дословно. Диалоговые пулы разворачиваются
        в позаписные окна здесь — иначе coarse-блок пула заблокировал бы всех
        соседей, а без манифеста остаётся fail-closed на coarse-блоке.

        Инвалидация по составу ловит новый список сегментов, новый ключ кэша
        и рост буфера. НЕ ловится подмена элемента списка на другой объект
        той же длины и мутация полей, влияющих на окно (`start`, `end`,
        `kind`, `injectable`, `alias_of`, `manifest`), на месте: в `core/` и
        `gui/` таких присваиваний нет — все окна строятся на свежих dict-ах.
        `segment['decoder']` мутируется, но на индекс не влияет. Защита
        опирается на этот инвариант плагинов, а не на кэш.
        """
        # Признак «состав сегментов не изменился» — САМИ списки, а не их id:
        # id освобождённого списка переиспользуется, и новый список с тем же
        # id и той же длиной получал бы чужой индекс (проверяется тестом на
        # двух одноимённых сегментах). Ссылки удерживаются в _foreign_index_src.
        try:
            srcs = tuple(self._segment_cache.values())
        except Exception:
            srcs = ()
        prev = getattr(self, '_foreign_index_src', None)
        sig = (len(self.modified_data),
               tuple(len(segs) if isinstance(segs, list) else -1
                     for segs in srcs))
        same = (prev is not None and len(prev) == len(srcs)
                and all(a is b for a, b in zip(prev, srcs, strict=True))
                and getattr(self, '_foreign_index_sig', None) == sig)
        cached: list | None = getattr(self, '_foreign_index_cache', None)
        if cached is not None and same:
            return cached
        entries: list[tuple] = []
        try:
            caches = list(self._segment_cache.values())
        except Exception:
            caches = []
        rom_size = len(self.modified_data)
        for segs in caches:
            if not isinstance(segs, list):
                continue
            for s in segs:
                if not isinstance(s, dict):
                    continue
                if s.get('kind') == 'pointer_dialogues':
                    is_pool = True
                    windows = self._dialogue_record_ranges(s, rom_size)
                    if not windows:
                        # fail-closed: без манифеста позаписных окон нет, и
                        # молчаливое «не защищено» повторило бы ровно тот баг,
                        # ради которого написан гард.
                        windows = self._coarse_range(s)
                else:
                    is_pool = False
                    windows = self._coarse_range(s)
                if not windows:
                    continue
                name = s.get('name')
                name = name if isinstance(name, str) else ''
                # `injectable is False` — часть предиката алиаса в
                # `_foreign_ranges`; без него индекс был fail-open для
                # сегмента с `alias_of`, но инжектируемым.
                is_readonly = s.get('injectable') is False
                alias_of = s.get('alias_of')
                alias_of = alias_of if isinstance(alias_of, str) else None
                owner = id(s)
                # Окно СЕГМЕНТА нужно для правила «тот же сегмент»: у пула
                # диалогов в индексе лежат по-записные окна, и сравнивать их
                # с окном сегмента нельзя — а исключать «тот же сегмент,
                # переданный копией» по ним надо.
                seg_start = s.get('start')
                seg_end = s.get('end')
                seg_start = seg_start if isinstance(seg_start, int) else -1
                seg_end = seg_end if isinstance(seg_end, int) else -1
                for a, b in windows:
                    entries.append((a, b, owner, name, is_readonly, alias_of,
                                      is_pool, seg_start, seg_end))
        entries.sort()
        # Префиксный максимум концов: pmax[i] = max(end[0..i]). Он не
        # убывает, поэтому «pmax[i] <= base» означает, что и все более
        # ранние элементы кончаются левее base — обратный проход можно
        # прервать.
        running = -1
        for i, entry in enumerate(entries):
            if entry[1] > running:
                running = entry[1]
            entries[i] = (*entry, running)
        self._foreign_index_cache = entries
        self._foreign_index_sig = sig
        self._foreign_index_src = srcs
        return entries

    @staticmethod
    def _own_span(segment: dict) -> tuple:
        """Границы «своих байтов» для исключения алиасов.

        Применимо только к сегменту, который САМ является одной записью
        (FF4/FF5 отдают по сегменту на запись): там окно сегмента — это ровно
        запись, и алиас, указывающий в её середину или хвост, лежит внутри.

        Неприменимо к:
          - пулу диалогов (`pointer_dialogues`) — окно занимает весь блок, и
            правило разрешило бы запись в чужую запись внутри пула;
          - fixed-width каталогам (Pokemon names/abilities/attacks) — окно
            это сетка из многих слотов, и правило разрешило бы запись
            поверх чужого диалога, попавшего в ту же сетку (ровно тот случай,
            что закрыт на Odyssey).
        """
        if not isinstance(segment, dict):
            return (None, None)
        if segment.get('kind') == 'pointer_dialogues':
            return (None, None)
        if segment.get('fixed_width') is not None:
            return (None, None)
        if segment.get('bank_meta'):
            return (None, None)
        start = segment.get('start')
        end = segment.get('end')
        if isinstance(start, int) and isinstance(end, int) \
                and not isinstance(start, bool) and not isinstance(end, bool):
            return (start, end)
        return (None, None)

    @staticmethod
    def _foreign_hit(index: list, own_name: str | None,
                     own_segment: dict | None, base: int, length: int,
                     own_start: int | None = None,
                     own_end: int | None = None) -> bool:
        """Есть ли чужое окно, пересекающее `[base, base + length)`.

        Диапазоны отсортированы по началу, поэтому достаточно просмотреть
        назад от бисектной позиции и остановиться, как только максимальный
        конец среди просмотренных уже не дотягивает до `base`.

        Индекс — только ускорение: предикат ниже ДОСЛОВНО повторяет
        `_foreign_ranges`, иначе оптимизация меняла бы смысл защиты. Отсюда
        все четыре условия исключения алиаса (своё окно, `injectable is
        False`, `alias_of == own_name`, окно внутри своего окна) и отдельная
        ветка для пулов диалогов: там `_foreign_ranges` делает `continue` до
        правила алиаса, и алиасом пула считаться не может.

        Три класса, где предикат раньше был слабее эталона (все fail-open),
        закрыты и закреплены `test_index_matches_full_scan_oracle`:
        алиас с окном ВНЕ окна хозяина; `alias_of` на инжектируемом сегменте;
        пул диалогов с сегментом, у которого `alias_of` равен имени пула.

        `own_start`/`own_end` — окно ПИШУЩЕГО сегмента (`_own_span`), а в
        кортеже индекса окно его владельца лежит под другими именами:
        `entry_seg_start`/`entry_seg_end`. Пересечение имён здесь означало
        бы, что обычная уборка в цикле тихо поменяет смысл правил.

        При `own_segment=None` своё окно НЕ исключается (эталон исключает по
        имени): расхождение строго в сторону fail-closed. Все четыре
        продакн-вызова передают сегмент.

        Ещё два класса, где индекс не совпадает с эталоном, оба безвредны:
        запись нулевой длины (`length <= 0`) не пишет байтов и возвращает
        `False`, а эталон на strictly-содержащем окне дал бы `True`; нестроковый
        `alias_of` нормализуется в `None`, то есть трактуется как «не алиас»
        (fail-open), но оба создателя алиасов пишут туда имя канонической
        записи.
        """
        if length <= 0 or not index:
            return False
        end = base + length
        own_window = TextInjector._window_pair(own_start, own_end)
        lo, hi = 0, len(index)
        while lo < hi:  # bisect по start: первый элемент с start >= end
            mid = (lo + hi) // 2
            if index[mid][0] < end:
                lo = mid + 1
            else:
                hi = mid
        own_id = id(own_segment) if own_segment is not None else None
        my_start = own_segment.get('start') if isinstance(own_segment, dict) \
            else None
        my_end = own_segment.get('end') if isinstance(own_segment, dict) \
            else None
        for i in range(lo - 1, -1, -1):
            (a, b, owner, name, is_readonly, alias_of, is_pool,
             entry_seg_start, entry_seg_end, pmax) = index[i]
            if pmax <= base:
                # Ни этот, ни любой более ранний элемент не дотягивает до
                # base — можно прервать (массив отсортирован по началу,
                # поэтому по одному b <= base прерывать нельзя).
                break
            if owner == own_id:
                continue
            # Тот же сегмент, но другой объект: вызывающий код мог передать
            # копию (`segments=[...]`, собранный заново). Прежний
            # `_foreign_ranges` отсекал по паре «имя + окно СЕГМЕНТА», и на
            # этом стоят тесты с двумя одноимёнными сегментами.
            if (own_id is not None and name == own_name
                    and entry_seg_start == my_start
                    and entry_seg_end == my_end):
                continue
            # Алиас ЭТОЙ записи — ровно те же четыре условия, что и в
            # `_foreign_ranges`. Одного `alias_of` мало: алиас с окном за
            # пределами хозяина, `alias_of` на инжектируемом сегменте и
            # алиас пула — это не «те же байты», и молча пропускать их
            # нельзя.
            if (own_window and not is_pool and is_readonly
                    and alias_of == own_name
                    and a >= own_window[0] and b <= own_window[1]):
                continue
            if a < end and b > base:
                return True
        return False

    def _foreign_ranges(self, own_name: str | None,
                        own_start: int | None = None,
                        own_end: int | None = None,
                        own_segment: dict | None = None
                        ) -> list[tuple[int, int]]:
        """Диапазоны чужих сегментов из кэша (защита от пересекающихся окон).

        Манифесты разных сегментов могут пересекаться (диалог указывает
        внутрь таблицы имён и т.п.): запись в чужой диапазон — пропуск,
        а не порча. Best-effort по кэшу (чего не видели — не защищаем).

        Свой сегмент исключается по ИДЕНТИЧНОСТИ, когда передан
        own_segment: имена сегментов не уникальны (два экземпляра плагина
        на одном ROM держат сегменты с одинаковым именем и разными окнами),
        и исключение по имени выбросило бы из защиты чужое окно.

        own_start/own_end — окно пишущего сегмента; исключаются алиасы:
        read-only сегмент, у которого alias_of указывает на пишущий сегмент
        и окно целиком лежит внутри его окна. Это запись, указывающая в
        середину или в хвост той же самой записи FF4/FF5, а не чужой сегмент.
        Проверка по alias_of, а не «любой read-only внутри окна»: широкий
        пишущий сегмент (на Odyssey — 1014 байт) иначе снимал бы защиту с
        любого read-only каталога внутри него.
        """
        out: list[tuple[int, int]] = []
        own_window = self._window_pair(own_start, own_end)
        try:
            cached = list(self._segment_cache.values())
        except Exception:
            return out
        for segs in cached:
            if not isinstance(segs, list):
                continue
            for s in segs:
                if not isinstance(s, dict):
                    continue
                if self._is_own_segment(s, own_name, own_segment):
                    continue
                # Для пула диалогов coarse [start, end) — это ВЕСЬ блок,
                # включая промежутки между записями. Если отдать его как
                # «чужой диапазон», любой соседний сегмент (например, блок
                # способностей) будет отвергнут целиком. Поэтому берём
                # реальные окна записей из манифеста: защищаем именно их.
                if s.get('kind') == 'pointer_dialogues':
                    # Владение здесь НЕоднозначно, и приоритет отдавать
                    # каталогу нельзя: на Odyssey та же запись манифеста
                    # 0x250026 — настоящий диалог, и запись каталога
                    # затирала его ('AW' вместо перевода). Приоритет каталогу
                    # чинит FireRed/Emerald (40 и 37 записей), но возвращает
                    # порчу диалога на Odyssey. Порча хуже непереведённой
                    # строки, поэтому бан симметричный: не пишет никто.
                    # See ROADMAP: снятие банa с каталогов без разбора
                    # владельца по конкретной игре.
                    records = self._dialogue_record_ranges(
                        s, len(self.modified_data))
                    if not records:
                        # fail-closed: без манифеста позаписных окон нет,
                        # и молчаливое «не защищено» повторило бы ровно тот
                        # баг, который этот метод чинит.
                        records = self._coarse_range(s)
                    out.extend(records)
                    continue
                windows = self._coarse_range(s)
                if not windows:
                    continue
                a, b = windows[0]
                if own_window and s.get('injectable') is False \
                        and s.get('alias_of') == own_name \
                        and a >= own_window[0] and b <= own_window[1]:
                    continue  # алиас той же записи, не чужой сегмент
                out.append((a, b))
        return out

    @staticmethod
    def _is_own_segment(s: dict, own_name: str | None,
                        own_segment: dict | None) -> bool:
        """Свой ли это сегмент (исключаем из чужих диапазонов).

        По ИДЕНТИЧНОСТИ, когда передан сам сегмент: имена не уникальны —
        два экземпляра плагина держат сегменты с одинаковым именем и
        разными окнами, и исключение по имени выбросило бы чужое окно из
        защиты. Но вызывающий код может передать КОПИЮ сегмента (например,
        `segments=[...]` собранный заново), поэтому идентичности мало:
        с тем же именем и тем же окном — тоже свой.
        """
        if s is own_segment:
            return True
        if own_segment is None:
            return s.get('name') == own_name
        if s.get('name') != own_name:
            return False
        return (s.get('start') == own_segment.get('start')
                and s.get('end') == own_segment.get('end'))

    @staticmethod
    def _window_pair(start, end) -> tuple[int, int] | None:
        """Валидированная пара (start, end) или None (bool/мусор — не окно)."""
        if (isinstance(start, int) and not isinstance(start, bool)
                and isinstance(end, int) and not isinstance(end, bool)
                and 0 <= start < end):
            return (start, end)
        return None

    def _coarse_range(self, s: dict) -> list[tuple[int, int]]:
        """Валидированное окно [start, end) сегмента или пустой список."""
        start = s.get('start')
        end = s.get('end')
        rom_size = len(self.modified_data)
        if (isinstance(start, int) and not isinstance(start, bool)
                and isinstance(end, int) and not isinstance(end, bool)
                and 0 <= start < end <= rom_size):
            return [(start, end)]
        return []

    @staticmethod
    def _preview(value) -> str:
        """Безопасный срез для отчётов (не-строки через repr, не краш)."""
        return (value if isinstance(value, str) else repr(value))[:60]

    @staticmethod
    def _segment_lang(segment: dict) -> str | None:
        """Язык сегментa: ключ 'lang' либо legacy-парсинг имени cvas_<lang>_idx."""
        lang = segment.get('lang')
        if isinstance(lang, str):
            return lang
        name = segment.get('name')
        if isinstance(name, str) and name.startswith('cvas_'):
            return name.removeprefix('cvas_').rsplit('_', 1)[0]
        return None

    @staticmethod
    def _valid_segments(segments):
        """Проверенные сегменты: list из dict, иначе None (fail-closed).

        Один битый вызов (не-список) травил бы _segment_cache для всех
        следующих — валидация здесь, до кэширования и использования.
        """
        if not isinstance(segments, list):
            return None
        # Список валидируется ОДИН раз на объект: проверка на каждый вызов
        # стоила 118 млн isinstance на Golden Sun (10863 сегмента × 10863
        # вызова). Возвращаем ИСХОДНЫЙ список: идентичность используется как
        # признак «состав не изменился» (кэш индекса чужих диапазонов), и
        # копия на каждый вызов этот кэш ломала.
        for segment in segments:
            if not isinstance(segment, dict):
                return None
        return segments

    @staticmethod
    def _consume_tokens(enc, run, rest, window_bytes, from_start):
        """Съедает совпадающий префикс (суффикс) run из rest.

        Возвращает (rest, fatal): fatal=True — fail-closed отказ
        (байт-несоответствие, пустой enc, исключение: stateful или
        дропающий энкодер). Текст-несоответствие — обычный стоп
        (fatal=False): перевод просто не содержит токен.
        """
        from core.decoder import iter_raw_tokens
        tokens = list(iter_raw_tokens(run))
        if not from_start:
            tokens.reverse()
        offset = 0 if from_start else len(window_bytes)
        for token in tokens:
            if len(token) > len(rest):
                break
            head = rest[:len(token)] if from_start else rest[len(rest) - len(token):]
            if head.lower() != token.lower():
                break
            try:
                token_bytes = enc(token)
            except (ValueError, KeyError, IndexError, TypeError):
                return rest, True
            if not token_bytes:
                return rest, True
            if from_start:
                pos = offset
                offset += len(token_bytes)
                rest = rest[len(token):]
            else:
                pos = offset - len(token_bytes)
                offset -= len(token_bytes)
                rest = rest[:len(rest) - len(token)]
            if pos < 0 or window_bytes[pos:pos + len(token_bytes)] != token_bytes:
                return rest, True
        return rest, False

    def _drop_junk_windows(self, windows: list[dict]) -> tuple[list[dict] | None, int]:
        """Убирает token-only окна (сырые токены/пустота), сохраняя порядок.

        Экстрактор такие фрагменты сообщениями не показывает (ведущие/
        хвостовые прогоны дропаются, одиночные не создаются), поэтому
        соответствие переводов окнам — только через этот фильтр.
        Пробельные окна НЕ трогаются (экстрактор их показывает: '   ' —
        сообщение, '' — нет). None-текст (провал декода) → (None, 0):
        молча дропать неизвестное содержимое нельзя.
        Возвращает (mapped, dropped_count).
        """
        from core.decoder import remove_raw_tokens
        mapped: list[dict] = []
        for pos, window in enumerate(windows):
            text = window.get('text')
            if not isinstance(text, str):
                self.logger.warning(f"Мусорное окно #{pos} дропает весь список")
                return None, 0
            if remove_raw_tokens(text) == '':
                continue
            mapped.append(window)
        return mapped, len(windows) - len(mapped)

    @staticmethod
    def _ends_with_raw_token(effective: str, window_text: str) -> bool:
        """Заканчивается ли записываемый текст raw-токеном, которого нет в конце
        исходного окна.

        Экстрактор отбрасывает хвостовой token-only прогон из отображения, поэтому
        такой перевод не переживёт round-trip. Если исходное окно УЖЕ заканчивалось
        тем же токеном, всё в порядке: токен будет отброшен с обеих сторон, и
        побайтовая проверка окна остаётся зелёной.
        """
        from core.decoder import iter_raw_tokens
        tokens = list(iter_raw_tokens(effective))
        if not tokens:
            return False
        last = tokens[-1]
        if not effective.rstrip().endswith(last):
            return False
        # Отказ только если исходное окно НЕ заканчивается тем же токеном.
        # Если заканчивается — токен отбрасывается с обеих сторон, и
        # побайтовая проверка окна остаётся зелёной. Сравниваем именно
        # СУФФИКС, а не «последний токен в списке»: в `in[F6]a!` токен
        # [F6] единственный, но стоит он в середине.
        return not window_text.rstrip().endswith(last)

    def _compressed_original_text(self, segment: dict) -> str | None:
        """Исходный текст сжатого окна: так же, как его читает экстрактор.

        `None`, если окно не декодируется — тогда гейт не применяется,
        и решение остаётся за поведением энкодера. Это осознанно: лучше не отказывать, чем
        отказывать по неполному сравнению.
        """
        raw_text = segment.get('raw_text')
        if isinstance(raw_text, str):
            return raw_text
        decoder = segment.get('decoder')
        if decoder is None:
            return None
        try:
            data = bytes(self.rom.data[segment['start']:segment['end']])
        except Exception:
            return None
        compression = segment.get('compression')
        if compression:
            handler = None
            if isinstance(compression, str):
                from core.compression import get_compression_handler
                handler = get_compression_handler(compression)
            elif callable(compression):
                handler = compression
            if handler is None:
                return None
            try:
                data, _consumed = handler.decompress(data, segment['start'])
            except Exception:
                return None
        decode = getattr(decoder, 'decode', None)
        if decode is None:
            return None
        try:
            text = decode(data, 0, len(data))
        except Exception:
            return None
        return text if isinstance(text, str) else None

    def _affix_region(self, segment: dict, original: dict, window_text: str, enc, translation: str = ''):
        """Свободная середина окна + эффективный текст для записи.

        Предположение: encoder stateless и префиксно-стабилен (повторные
        вызовы на частях дают те же байты; все in-tree энкодеры
        generic-пути таковы; stateful Huffman/DTE-сегменты идут
        compressed-путём и сюда не попадают). Нарушение — отказ, не порча.
        Ведущий/хвостовой прогон обязан перекодироваться в те же НЕПУСТЫЕ
        байты префикса/суффикса (пустой enc = дропающий энкодер → отказ).
        Перевод потребляет совпавшие токены поштучно (без дублей);
        токены середины обязаны идти в переводе тем же порядком
        (подпоследовательность; переупорядочивание контролов —
        смена поведения игры). Возвращает (base, room, effective).
        """
        from core.decoder import (
            raw_token_leading_run,
            raw_token_trailing_run,
            remove_raw_tokens,
        )
        start = segment['start'] + original['offset']
        length = original['length']
        window_bytes = bytes(self.rom.data[start:start + length])
        # Токен-на-токен: писать нечего (байты уже на месте либо чужие) —
        # skip сохраняет их в обе стороны.
        if remove_raw_tokens(window_text) == '' and remove_raw_tokens(translation) == '':
            return None, None, None
        lead = raw_token_leading_run(window_text)
        trail = raw_token_trailing_run(window_text)
        # Верификационные encode не должны шуметь в last_unmapped_chars.
        decoder = getattr(enc, '__self__', None)
        noisy = decoder is not None and isinstance(
            getattr(decoder, 'last_unmapped_chars', None), list)
        before = list(decoder.last_unmapped_chars) if decoder is not None and noisy else None
        try:
            return self._affix_region_inner(
                segment, original, window_text, enc, translation,
                start, length, window_bytes, lead, trail)
        finally:
            if decoder is not None and noisy:
                decoder.last_unmapped_chars = before

    def _affix_region_inner(self, segment: dict, original: dict, window_text: str, enc,
                            translation: str, start: int, length: int,
                            window_bytes: bytes, lead: str, trail: str):
        """Тело _affix_region без шумоподавления (см. выше)."""
        from core.decoder import iter_raw_tokens
        try:
            lead_bytes = enc(lead) if lead else b''
            trail_bytes = enc(trail) if trail else b''
        except (ValueError, KeyError, IndexError, TypeError):
            return None, None, None
        if (lead and not lead_bytes) or (trail and not trail_bytes):
            return None, None, None
        if not window_bytes.startswith(lead_bytes):
            return None, None, None
        if trail_bytes and not window_bytes.endswith(trail_bytes):
            return None, None, None
        rest, fatal = self._consume_tokens(enc, lead, translation, window_bytes, True)
        if fatal:
            return None, None, None
        rest, fatal = self._consume_tokens(enc, trail, rest, window_bytes, False)
        if fatal:
            return None, None, None
        middle = window_text[len(lead):len(window_text) - len(trail) if trail else None]
        need = [token.lower() for token in iter_raw_tokens(middle)]
        have = [token.lower() for token in iter_raw_tokens(rest)]
        if not self._is_subsequence(have, need):
            return None, None, None
        room = length - len(lead_bytes) - len(trail_bytes)
        if room < 0:
            return None, None, None
        return start + len(lead_bytes), room, rest

    @staticmethod
    def _is_subsequence(have: list, need: list) -> bool:
        """need идёт в have по порядку (лишнее в have разрешено)."""
        iterator = iter(have)
        return all(any(item == target for item in iterator) for target in need)

    def _tracked_spans(self) -> list[tuple[int, int]]:
        """История записей сессии ( лениво: тесты конструируют через __new__)."""
        spans = getattr(self, '_written_spans', None)
        if spans is None:
            spans = []
            self._written_spans = spans
        return spans

    def _check_write_overlap(self, base: int, full: bytes) -> str:
        """Классифицирует запись [base, base+len) против истории сессии.

        'identical' — байты уже на месте (идемпотентный повтор);
        'conflict' — пересечение с прошлой записью другим содержимым
        (первый писатель выигрывает, иначе каша из двух переводов);
        'ok' — чисто. История живёт весь инстанс (один рабочий ROM).
        """
        end = base + len(full)
        current = bytes(self.modified_data[base:end])
        if current == full:
            return 'identical'
        for start, stop in self._tracked_spans():
            if base < stop and start < end:
                return 'conflict'
        return 'ok'

    def _safe_inject_message(self, rom_offset, data, orig_len: int, pad_byte: int) -> bool:
        """Запись с гардами типов и границ: битый адрес/размер → False.

        Ловит ValueError (OOB из _inject_message), TypeError/IndexError
        (битые типы) — GUI-путь возвращает bool, а не роняет tkinter.
        """
        if (isinstance(rom_offset, bool) or not isinstance(rom_offset, int)
                or not isinstance(data, (bytes, bytearray))
                or isinstance(orig_len, bool) or not isinstance(orig_len, int) or orig_len < 0
                or isinstance(pad_byte, bool) or not isinstance(pad_byte, int)):
            return False
        try:
            self._inject_message(rom_offset, bytes(data), orig_len, pad_byte)
        except (ValueError, TypeError, IndexError) as exc:
            self.logger.debug(f"Write refused: {exc}")
            return False
        return True

    def _extract_original_messages(self, segment) -> list[dict]:
        """
        Извлекает оригинальные сообщения из сегмента, считая смещения в БАЙТАХ.
        Разделители: 0x00, 0xFF, 0xFE, 0x0D, 0x0A (терминаторы/переводы строки).
        Битый сегмент → [] (fail-closed выше по стеку).
        """
        try:
            start = segment['start']
            end = segment['end']
            decoder = segment['decoder']
        except (KeyError, TypeError, AttributeError):
            return []
        if (isinstance(start, bool) or not isinstance(start, int)
                or isinstance(end, bool) or not isinstance(end, int)):
            return []
        rom_len = len(self.rom.data)
        if not 0 <= start <= end <= rom_len:
            return []
        data = self.rom.data[start:end]
        if not isinstance(data, (bytes, bytearray)):
            return []

        if segment.get('fixed_width'):
            width = segment['fixed_width']
            count = segment['record_count'] if 'record_count' in segment else (
                len(data) // width if width else 0)
            max_len = segment.get('max_length', width - 1 if isinstance(width, int) else 0)
            if (isinstance(width, bool) or not isinstance(width, int) or width <= 0
                    or isinstance(count, bool) or not isinstance(count, int) or count < 0
                    or isinstance(max_len, bool) or not isinstance(max_len, int)):
                return []
            count = min(count, len(data) // width)
            fixed_msgs = []
            for i in range(count):
                slot_offset = i * width
                if slot_offset + width > len(data):
                    break
                slot_bytes = bytes(data[slot_offset:slot_offset + width])
                try:
                    text = decoder.decode(slot_bytes, 0, len(slot_bytes))
                except Exception as exc:
                    self.logger.warning(
                        f"Слот 0x{start + slot_offset:X}: сбой декодирования ({exc}), пропущен")
                    text = ""
                if text.strip("-? ") == "":
                    continue
                fixed_msgs.append({
                    'offset': slot_offset,
                    'length': width,
                    'text': text,
                    'max_length': max_len,
                })
            return fixed_msgs

        msgs: list[dict] = []
        i = 0
        n = len(data)
        generic = {0x00, 0xFF, 0xFE, 0x0D, 0x0A}
        raw_terms = segment.get('terminators')
        if isinstance(raw_terms, bool) or not isinstance(raw_terms, (list, tuple, set)):
            terminators = generic
        else:
            terminators = {t for t in raw_terms
                           if isinstance(t, int) and not isinstance(t, bool)} or generic

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
                except Exception as exc:
                    self.logger.debug(f"Window decode failed at +{msg_start:#x}: {exc}")
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


    def _inject_message(self, rom_offset: int, data: bytes, orig_len: int, pad_byte: int = 0x20):
        """Внедряет байты перевода в ROM, не затрагивая терминатор. Паддинг до прежней длины."""

        # Выход за границы ROM — признак битого манифеста/адреса, не должны молча усекать текст
        if rom_offset < 0 or rom_offset + max(len(data), orig_len) > len(self.modified_data):
            raise ValueError(
                f"Смещение {rom_offset:#x} + длина {max(len(data), orig_len)} выходит за размер ROM "
                f"({len(self.modified_data)} байт)"
            )

        # Заменяем оригинальные байты
        for i, byte in enumerate(data):
            self.modified_data[rom_offset + i] = byte

        # Если перевод короче оригинала — дополняем pad_byte до orig_len
        pad_len = orig_len - len(data)
        if pad_len > 0:
            for k in range(pad_len):
                self.modified_data[rom_offset + len(data) + k] = pad_byte

    def save(self, output_path: str):
        """Сохраняет модифицированный ROM, пересчитав header/global checksum."""
        self.rom.recalculate_checksums(self.modified_data)
        with open(output_path, 'wb') as f:
            f.write(self.modified_data)
