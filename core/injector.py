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

from core.rom import GameBoyROM


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
        self.last_unmapped_chars: list[str] = []
        self.logger = logging.getLogger('gb2text.injector')

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
            self._segment_cache[plugin] = plugin.get_text_segments(self.rom)
        segments = self._segment_cache[plugin]
        self._sync_bank_segments(segments)
        return segments

    def _sync_bank_segments(self, segments: list) -> None:
        """Фиксирует банковые сегменты для _occupied_intervals.

        Вызывается при каждом получении сегментов (включая ручную передачу
        в inject_segment), чтобы перед relocate был актуальный список
        таблиц всех банков.
        """
        bank_segs = [s for s in segments if s.get('bank_meta')]
        if bank_segs and self._bank_segments != bank_segs:
            self._bank_segments = bank_segs
            self._taken_free_blocks = []

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
            relocate: переносить ли слишком длинные записи банка в свободные
                зоны (None — брать из bank_meta['relocate'])

        Returns:
            True если хотя бы одно сообщение было внедрено
        """
        if not plugin:
            return False

        self.last_overflow_report = []

        if segments is None:
            segments = self._get_segments(plugin)
        else:
            self._segment_cache[plugin] = segments
            self._sync_bank_segments(segments)
        segment = next((s for s in segments if s['name'] == segment_name), None)

        if not segment:
            return False

        if segment.get('injectable') is False:
            self.logger.info(
                f"Сегмент '{segment_name}' не поддерживает вставку (extract-only)")
            return False

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
            pad_byte = segment.get('pad_byte', 0x00)

            trans_bytes = None
            try:
                trans_bytes = enc(translation)
            except (ValueError, KeyError, IndexError) as e:
                self.logger.debug(f"Could not recompress: {e}")
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

            self._inject_message(segment['start'], trans_bytes,
                                 original_length, pad_byte)
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
            return self._inject_pointer_dialogues(segment, translations, skip_long)

        # Проверяем, что переводы не длиннее оригинального текста
        original_messages = self._extract_original_messages(segment)

        if len(translations) != len(original_messages):
            return False

        # Пустой список переводов = нет сообщений = OK
        if len(translations) == 0:
            return True

        injected = 0
        skipped = 0
        enc = segment['decoder'].encode
        max_len = segment.get(
            'max_length',
            segment['fixed_width'] - 1 if segment.get('fixed_width') else None)
        for i, (original, translation) in enumerate(zip(original_messages, translations, strict=False)):
            try:
                trans_bytes = enc(translation)
            except (ValueError, KeyError, IndexError):
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: cannot encode translation, skipping")
                    continue
                return False
            # Сравниваем длину в байтах (для fixed_width — окно слота без 0xFF)
            if len(trans_bytes) > original['length']:
                if skip_long:
                    skipped += 1
                    self.logger.debug(f"Message {i}: translation too long ({len(trans_bytes)} > {original['length']}), skipping")
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
                return False

            # Внедряем перевод
            self._inject_message(segment['start'] + original['offset'],
                                 trans_bytes, original['length'],
                                 segment.get('pad_byte', 0x20))
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
        meta = plugin.get_pointer_table_meta() if hasattr(plugin, 'get_pointer_table_meta') else None
        if not meta or not isinstance(meta, dict):
            return False
        if 'index_of' in meta and 'lang_slots' in meta and not meta.get('blocks'):
            return self.inject_interleaved_language(lang, texts, plugin, segments=segments)
        table_offset = meta.get('table')
        count = meta.get('count')
        blocks = meta.get('blocks') or []
        if not isinstance(table_offset, int) or not isinstance(count, int) or not blocks:
            return False

        if segments is None:
            segments = self._get_segments(plugin)
        else:
            self._segment_cache[plugin] = segments

        block = next((b for b in blocks if b[2] == lang), None)
        if block is None:
            return False
        idx_from, idx_to, _ = block
        segs = [
            s for s in segments
            if s['name'].startswith('cvas_')
            and s['name'].removeprefix('cvas_').rsplit('_', 1)[0] == lang
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
            try:
                records.append(encoder.encode(text))
            except ValueError:
                return False

        from core.pointer_table import assemble_block, find_free_space, patch_pointer_range

        ranges = self._block_ranges(blocks, segments, targets, count, len(self.rom.data))
        block_index = next(
            (i for i, b in enumerate(blocks) if b[2] == lang), None)
        if block_index is None:
            return False
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
        patch_pointer_range(self.modified_data, table_offset,
                            idx_from, idx_to, record_offsets)
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
            low = targets[bs]
            if be < count:
                high = targets[be]
            else:
                end = None
                for seg in segments:
                    seg_lang = seg['name'].removeprefix('cvas_').rsplit('_', 1)[0]
                    if seg_lang == blang:
                        end = seg['end'] if end is None else max(end, seg['end'])
                high = end if end is not None else min(low + 1, rom_size)
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
        вне всех записей всех языков и таблицы.
        """
        meta = plugin.get_pointer_table_meta() if hasattr(plugin, 'get_pointer_table_meta') else None
        if not meta or not isinstance(meta, dict):
            return False
        table_offset = meta.get('table')
        count = meta.get('count')
        lang_slots = meta.get('lang_slots')
        index_of = meta.get('index_of')
        if not isinstance(table_offset, int) or not isinstance(count, int):
            return False
        if not isinstance(lang_slots, dict) or lang not in lang_slots:
            return False
        if not callable(index_of):
            return False
        slot = lang_slots[lang]

        if segments is None:
            segments = self._get_segments(plugin)
        else:
            self._segment_cache[plugin] = segments

        by_idx: dict[int, dict] = {}
        for s in segments:
            if s.get('lang') == lang:
                by_idx.setdefault(s.get('index'), s)

        # переводов должно быть ровно count
        if len(texts) != count:
            return False
        if count == 0:
            return False

        encoder = plugin.make_text_encoder() if hasattr(plugin, 'make_text_encoder') else None
        if encoder is None:
            return False

        # занятые диапазоны: все записи всех языков + сама таблица
        occupied = [(s['start'], s['end']) for s in segments if s.get('start') is not None]
        occupied.append((table_offset, table_offset + 4 * count * len(lang_slots)))

        try:
            records: dict[int, bytes] = {}
            for idx in range(count):
                seg = by_idx.get(idx)
                if seg is None:
                    return False
                if not seg.get('injectable', True):
                    continue
                try:
                    records[idx] = encoder.encode(texts[idx])
                except ValueError:
                    return False
        except Exception:
            return False

        from core.pointer_table import find_free_space
        changed = False
        for idx, new in records.items():
            seg = by_idx[idx]
            start, end = seg['start'], seg['end']
            if len(new) <= end - start:
                self.modified_data[start:end] = new + b'\x00' * (end - start - len(new))
                changed = True
                continue
            dest = find_free_space(self.modified_data, len(new), occupied)
            if dest is None:
                if not expand_if_full:
                    return False
                dest = self._expand_rom(len(new))
                changed = True
            self.modified_data[start:end] = b'\x00' * (end - start)
            self.modified_data[dest:dest + len(new)] = new
            occupied.append((dest, dest + len(new)))
            self._patch_one_pointer(table_offset + 4 * index_of(idx, slot), dest)
            changed = True

        self.logger.info(
            f"Внедрён блок '{lang}': {len(records)} записей пересобрано"
            f" (каталогов пропущено: {count - len(records)})")
        return changed

    def _patch_one_pointer(self, absolute_offset: int, target: int) -> None:
        """Записывает GBA-указатель (база 0x08000000) в absolute_offset."""
        from core.pointer_table import HEADER_BASE
        self.modified_data[absolute_offset:absolute_offset + 4] = (
            (HEADER_BASE + target) & 0xFFFFFFFF).to_bytes(4, 'little')

    def _expand_rom(self, size: int) -> int:
        """Расширяет modified_data в конец блоком 0x00 начиная с выровненного
        (0x100) смещения, гарантируя >= size байт свободного места, и
        возвращает это (выровненное) смещение."""
        align = 0x100
        orig = len(self.modified_data)
        dest = ((orig + align - 1) // align) * align
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
        if len(original_messages) != len(translations):
            return False

        decoder = segment['decoder']
        pad_byte = segment.get('pad_byte', 0x00)
        injected = 0
        skipped = 0
        for i, (orig, translation) in enumerate(
                zip(original_messages, translations, strict=False)):
            try:
                trans_bytes = decoder.encode(translation)
            except (ValueError, KeyError, IndexError):
                if skip_long:
                    skipped += 1
                    self.logger.debug(
                        f"Message {i}: cannot encode translation, skipping")
                    continue
                return False
            if len(trans_bytes) > orig['length']:
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
            self._inject_message(segment['start'] + orig['offset'],
                                 trans_bytes, orig['length'], pad_byte)
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
        offsets_idx = meta.get('offsets_idx') or list(range(len(offsets)))
        if index < 0 or index >= len(offsets):
            return False
        table_idx = offsets_idx[index]
        base = segment['start']

        if table_idx == 0:
            # Слот 0 таблицы хранит N*4 (сигнатура банка) — он одновременно
            # offset первой записи. Менять его нельзя, иначе повторный скан
            # не найдёт банк.
            return False

        protected = meta.get('protected_records') or []
        cur_addr = base + offsets[index]
        if cur_addr in protected:
            return False

        size = len(trans_bytes) + 1
        dest = self._find_bank_free_block(
            segment, size, orig_abs=cur_addr, table_idx=table_idx)
        if dest is None:
            return False

        dest_rel = dest - base
        if not (0 <= dest_rel < meta.get('max_reloc_offset', 0x4000)):
            return False

        for k in range(len(trans_bytes)):
            self.modified_data[dest + k] = trans_bytes[k]
        if dest + len(trans_bytes) < len(self.modified_data):
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
            meta = segment.get('bank_meta') or {}
            if not meta:
                continue
            cc = meta.get('control_codes') or {}
            base = segment['start']
            table_count = meta.get('table_count') or 0
            end = meta.get('record_end') or segment['end']
            zone_end = meta.get('zone_end', end)
            for idx in range(table_count):
                slot = base + 4 * idx
                if slot + 4 > len(self.modified_data):
                    continue
                v = struct.unpack_from('<I', self.modified_data, slot)[0]
                s = base + v
                if s >= len(self.modified_data):
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

        occupied = self._occupied_intervals()
        occupied_all = occupied + getattr(self, '_taken_free_blocks', [])

        for zone in free_zones:
            zs, ze = int(zone[0]), int(zone[1])
            ze = min(ze, base + max_rel + 1)
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
            except Exception:
                segment['decoder'] = None

    def _inject_pointer_dialogues(self, segment, translations: list[str],
                                  skip_long: bool) -> bool:
        """In-place вставка в pointer-пул диалогов (запись + 0xFF + 0x00-падинг).

        ORDER: плагин держит entries в манифесте отсортированными, экстрактор
        отдаёт сообщения в том же порядке — translations зипуются 1:1.
        Перевод длиннее room (free_after) → пропуск при skip_long, иначе False.
        Пропущенные попадают в self.last_overflow_report (видимый отчёт GUI).
        """
        decoder = segment.get('decoder')
        if decoder is None:
            return False
        manifest = segment.get('manifest') or []
        if len(translations) != len(manifest):
            return False
        if not translations:
            return True
        self.last_overflow_report = []
        injected = 0
        skipped = 0
        encoder = segment.get('pointer_encoder')
        if encoder is None:
            encoder = decoder.encode
        for entry, translation in zip(manifest, translations, strict=False):
            addr = entry['target']
            room = entry['free_after']
            raw = entry.get('raw')
            if isinstance(raw, (bytes, bytearray)) and \
                    translation == entry.get('original'):
                trans_bytes = bytes(raw)
            else:
                try:
                    trans_bytes = encoder(translation)
                except (ValueError, KeyError, IndexError):
                    if skip_long:
                        skipped += 1
                        continue
                    return False
            payload = trans_bytes + segment.get('terminator', b'\xff')
            if len(payload) > room:
                self.last_overflow_report.append({
                    'target': addr,
                    'free_after': room,
                    'length': len(payload),
                    'text': translation,
                })
                if skip_long:
                    skipped += 1
                    continue
                return False
            self._inject_message(addr, payload, room, 0x00)
            injected += 1
        self.logger.info(
            f"[pointer_dialogues] injected {injected}, skipped {skipped}")
        return injected > 0

    def _extract_original_messages(self, segment) -> list[dict]:
        """
        Извлекает оригинальные сообщения из сегмента, считая смещения в БАЙТАХ.
        Разделители: 0x00, 0xFF, 0xFE, 0x0D, 0x0A (терминаторы/переводы строки).
        """
        start = segment['start']
        end = segment['end']
        data = self.rom.data[start:end]
        decoder = segment['decoder']

        if segment.get('fixed_width'):
            width = segment['fixed_width']
            count = segment['record_count'] if 'record_count' in segment else (
                len(data) // width if width else 0)
            max_len = segment.get('max_length', width - 1)
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
        terminators = set(segment.get('terminators') or generic)

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
