"""
GB Text Extraction Framework

COPYRIGHT WARNING:
This software tool is intended ONLY for the analysis of ROM files
lawfully owned by the user. Any use of this tool to
illegally copy, distribute, or modify copyrighted
material is strictly prohibited.

This project does NOT contain or distribute any ROM files or
copyrighted material. All ROM files must be
lawfully acquired by the user independently.

This tool is developed exclusively for research purposes,
education, and reverse engineering within the limits permitted by law.
"""

"""
Plugin for Mario & Luigi: Superstar Saga (GBA) - full extraction + insertion.

Game codes: A88E (USA), BTEJ (Japan), BTEP (Europe)
Text encoding: printable ASCII (0x20-0x7E) + FF tokens (commands/special glyphs)
  + inline icon glyphs (0x00-0x1F, incl. the 18/19/1E/1F buttons).

RE facts (confirmed by the mGBA Lua emulator and static analysis):
- Master pointer table @0x4EB000..0x4F0000: 5120 x 4-byte LE =
  1024 entries x 5 languages, slot-interleaved: table[idx*5 + slot],
  slot: 0=DE, 1=FR, 2=ES, 3=EN, 4=IT.
- A record (<1024 EN) starts with [2-byte speaker][FF 0B][01] (1024/1024 valid),
  then format codes, text, line break FF 00, windows FF 11 <win>, end FF 0A <00>.
- An FF-code token = FF + the next byte (command or special glyph; for commands
  FF 11/01/0A - 1 parameter byte). Tokenization keeps FF+byte as a single
  verbatim token - a lossless round-trip WITHOUT knowing each command's
  parameter length.
- Catalog records (the last slot record, and e888) contain >1 FF 0A -
  marked as non-rebuildable for injection (skip-with-warn).
"""

import bisect
import hashlib
import logging
import re
import threading
from typing import ClassVar

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.mario_luigi_ss')

MLSS_POINTER_TABLE = 0x4EB000
MLSS_ENTRIES = 1024
MLSS_GBA_BASE = 0x08000000

# (lang, slot); order matters for the blocks.
MLSS_LANGS = [
    ('de', 0), ('fr', 1), ('es', 2), ('en', 3), ('it', 4),
]
MLSS_DEFAULT_LANG = 'en'
MLSS_SLOT_EN = 3

# Record terminator: FF 0A (+ padding 00). Record boundaries are determined
# by scanning for FF 0A bounded by the next pointer OF THE SAME slot.
MLSS_TERMINATORS = [0xFF]

# FF XX commands with a known parameter count (besides XX itself).
# XX: number of extra parameter bytes. Unknown/printable FF codes -> 0 (verbatim).
# FF 0B (=paragraph, next byte 01 - a separate token), FF 03 - no parameter.
MLSS_FF_PARAM = {
    0x0A: 1, 0x11: 1, 0x01: 1, 0x0B: 0, 0x00: 0, 0x03: 0,
    0x04: 0, 0x0C: 0, 0x0D: 0, 0x0E: 0, 0x0F: 0, 0x05: 0, 0xFF: 1,
}
# Pool of forcibly-known (most frequent) ones: the remaining printable
# FF codes (0x20-0x7E) are parameterless special glyphs (a single FF XX token).

_CMD_RE = re.compile(r'^\[FF ([0-9A-Fa-f]{2})(?: ([0-9A-Fa-f]{2}))?\]$')
_GLYPH_RE = re.compile(r'^\[G:([0-9A-Fa-f]{2})\]$')


def _is_printable(b: int) -> bool:
    return 0x20 <= b <= 0x7E


class MLSSTextDecoder:
    """Decodes MLSS record bytes into a string token representation.

    Rules (lossless):
      - FF XX -> token '[FF XX]' (2 bytes); commands with a parameter from
        MLSS_FF_PARAM get it appended: '[FF 11 00]'.
      - a byte-glyph outside 0x20-0x7E -> '[G:XX]'.
      - a run of printable ASCII -> characters as-is.
    """

    def __init__(self, ff_param: dict[int, int] | None = None):
        # NOTE: параметры длиннее 1 байта не поддерживаются (читается
        # только первый): дефолтный словарь ограничен plen<=1.
        self._ff_param = dict(ff_param) if ff_param is not None else dict(MLSS_FF_PARAM)

    def decode(self, data: bytes | bytearray, start: int, length: int) -> str:
        end = min(start + length, len(data))
        i = start
        out: list[str] = []
        n = end
        while i < n:
            b = data[i]
            if b == 0xFF and i + 1 < n:
                xx = data[i + 1]
                plen = self._ff_param.get(xx, 0)
                if i + 2 + plen > n:
                    # tail without a full parameter: keep it as-is
                    out.append(f'[FF {xx:02X}]')
                    i += 2
                    continue
                if plen == 0:
                    out.append(f'[FF {xx:02X}]')
                    i += 2
                else:
                    param = data[i + 2]
                    out.append(f'[FF {xx:02X} {param:02X}]')
                    i += 3
                continue
            if b == 0xFF:
                # a lone FF at the very end
                out.append('[FF]')
                i += 1
                continue
            if _is_printable(b):
                start_txt = i
                while i < n and data[i] != 0xFF and _is_printable(data[i]):
                    i += 1
                out.append(bytes(data[start_txt:i]).decode('ascii'))
                continue
            out.append(f'[G:{b:02X}]')
            i += 1
        return ''.join(out)


class MLSSTextEncoder:
    """Inverse operation: token-string -> MLSS bytes (lossless).

    Tokens:
      [FF XX]      -> FF XX
      [FF XX PP]   -> FF XX PP (command with a parameter)
      [G:XX]       -> byte XX
      ASCII        -> as-is
    A literal '[' that is neither a token nor ASCII -> ValueError (like CVAS).
    """

    _FF = _CMD_RE
    _GLYPH = _GLYPH_RE

    def encode(self, text: str) -> bytes:
        out = bytearray()
        n = len(text)
        i = 0
        while i < n:
            ch = text[i]
            if ch == '[':
                close = text.find(']', i + 1)
                if close != -1:
                    m = self._FF.match(text[i:close + 1])
                    if m:
                        hi = int(m.group(1), 16)
                        out.append(0xFF)
                        out.append(hi)
                        if m.group(2):
                            out.append(int(m.group(2), 16))
                        i = close + 1
                        continue
                    m2 = self._GLYPH.match(text[i:close + 1])
                    if m2:
                        out.append(int(m2.group(1), 16))
                        i = close + 1
                        continue
                    # [FF] without a code - a single terminator FF
                    if text[i:close + 1] == '[FF]':
                        out.append(0xFF)
                        i = close + 1
                        continue
                    # literal brackets - must be printable
                    raise ValueError(f"Неизвестный токен {text[i:close + 1]!r}")
                raise ValueError("Незакрытая '[' в токене")
            if 0x20 <= ord(ch) <= 0x7E:
                out.append(ord(ch))
            else:
                raise ValueError(f"Не удаётся закодировать {ch!r}")
            i += 1
        return bytes(out)


class MarioLuigiSSPlugin(GamePlugin):  # pragma: no cover
    """Plugin for Mario & Luigi: Superstar Saga (GBA)"""  # pragma: no cover
  # pragma: no cover
    def __init__(self):  # pragma: no cover
        super().__init__()  # pragma: no cover
        self._decoder = MLSSTextDecoder()  # pragma: no cover
        self._encoder = MLSSTextEncoder()  # pragma: no cover
  # pragma: no cover
    @property  # pragma: no cover
    def game_id_pattern(self) -> str:  # pragma: no cover
        return r'^GBA_(A88E|BTEJ|BTEP)$'  # pragma: no cover
  # pragma: no cover
    def make_text_encoder(self) -> MLSSTextEncoder:  # pragma: no cover
        return self._encoder  # pragma: no cover
  # pragma: no cover
    def get_pointer_table_meta(self) -> dict:  # pragma: no cover
        return {  # pragma: no cover
            'table': MLSS_POINTER_TABLE,  # pragma: no cover
            'count': MLSS_ENTRIES,
            'langs': [lang for lang, _ in MLSS_LANGS],
            'lang_slots': dict(MLSS_LANGS),
            'default_lang': MLSS_DEFAULT_LANG,
            'index_of': lambda idx, slot: idx * 5 + slot,
            'record_terminator': (0xFF, 0x0A),
            'record_pad': 0x00,
        }

    def get_pointer_slot_of(self, lang: str) -> int:
        return dict(MLSS_LANGS)[lang]

    def _languages_set(self):
        return [lang for lang, _ in MLSS_LANGS]

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract segments via the master pointer table (all languages)."""
        logger.info("Извлечение сегментов Mario & Luigi: Superstar Saga (master table)")
        data = rom.data
        table = MLSS_POINTER_TABLE
        if table + 4 * MLSS_ENTRIES * 5 > len(data):
            logger.warning("Таблица указателей выходит за пределы ROM")
            return []

        # target offsets in the slot-interleaved layout
        ptrs: dict[str, list[int]] = {}
        for lang, _slot in MLSS_LANGS:
            ptrs[lang] = []
            for idx in range(MLSS_ENTRIES):
                p = table + 4 * (idx * 5 + _slot)
                val = int.from_bytes(data[p:p + 4], 'little')
                off = val - MLSS_GBA_BASE
                ptrs[lang].append(off)

        segments: list[dict] = []
        table_end = table + 4 * MLSS_ENTRIES * 5
        cls = type(self)
        # The detection knobs belong to the key: the spans depend on them, so a
        # patched threshold must not reuse the spans of a previous scan.
        rom_key = (len(data), hashlib.sha1(data[table:table_end]).hexdigest(),
                   cls._CATALOG_MAX_ZERO_RUN)
        # The lock guards publication only; readers must not read the shared dict
        # afterwards. Another thread may rescan its own ROM and republish between
        # our publication and our reads, which handed this ROM the spans of
        # another one (all nine catalog segments with foreign start/end/raw_text,
        # no exception). So the snapshot is taken here and passed down
        # explicitly; _make_segment never touches the class attribute.
        with cls._CATALOG_CACHE_LOCK:
            if not cls._CLASS_CATALOG_SCANNED or cls._CLASS_CATALOG_ROMKEY != rom_key:
                cls._CLASS_CATALOG_SPANS = self._scan_catalogs(data, ptrs)
                cls._CLASS_CATALOG_ROMKEY = rom_key
                cls._CLASS_CATALOG_SCANNED = True
            spans = cls._CLASS_CATALOG_SPANS
        for lang, _slot in MLSS_LANGS:
            lst = ptrs[lang]
            for idx in range(MLSS_ENTRIES):
                off = lst[idx]
                if not (0 < off < len(data)):
                    continue
                seg = self._make_segment(data, off, idx, lang, spans)
                if seg is not None:
                    segments.append(seg)

        logger.info("Всего сегментов: %d", len(segments))
        return segments

    _CLASS_CATALOG_SPANS: ClassVar[dict[tuple[str, int], tuple[int, int]]] = {}
    # Подзаписи каталога физически идут подряд, поэтому длинный прогон нулей
    # означает, что окно ушло за пределы самой записи — в пустоту пула или в
    # свободное место после релокации. Порог выбран с запасом по обе стороны
    # от измерений на реальном ROM: максимальный прогон нулей внутри
    # структурных окон настоящих каталогов = 5, в свободном месте = 1000+.
    # Без отсечки обычная запись, перенесённая в свободное место, брала верхнюю
    # границу по следующему указателю своей колонки (~2 МБ), набирала >1 FF 0A
    # и читалась как каталог на 10 млн символов.
    _CATALOG_MAX_ZERO_RUN: ClassVar[int] = 64
    _CLASS_CATALOG_ROMKEY: ClassVar[tuple[int, str, int] | None] = None
    _CLASS_CATALOG_SCANNED: ClassVar[bool] = False
    # Spans are shared class state while get_text_segments runs from background
    # threads (gui/main_window.py, api/server.py ThreadingHTTPServer), so the
    # check-then-scan-publish sequence has to be atomic: two concurrent parses of
    # two different MLSS ROMs used to interleave and hand one ROM the spans of
    # the other. The scan itself is serialised; publication is a single
    # assignment of a fully built dict, never a mutated one.
    _CATALOG_CACHE_LOCK: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def reset_class_cache(cls) -> None:
        """Drop the shared catalog cache (tests that patch detection knobs)."""
        with cls._CATALOG_CACHE_LOCK:
            cls._CLASS_CATALOG_SPANS = {}
            cls._CLASS_CATALOG_ROMKEY = None
            cls._CLASS_CATALOG_SCANNED = False

    def _scan_catalogs(self, data,
                       ptrs: dict[str, list[int]],
                       ) -> dict[tuple[str, int], tuple[int, int]]:
        """Determines catalog spans once (from the primary/unmodified pointers).
        A catalog = a record whose structural extent [ptr, next_ptr_that_column)
        contains >1 FF 0A (nested sub-records).

        Detection uses the STRUCTURAL extent (same column, as before). The
        stored read span is additionally clamped to the first record start
        after this one across ALL language columns, because the pools are
        physically interleaved: without the clamp a read-only catalog span
        swallowed the neighbouring columns' writable records (~90 KB for
        de_889), their writes changed the blob and the catalog then decoded
        to garbage. Clamping only the stored span keeps detection intact —
        clamping the detection window instead would reclassify a real
        catalog as an ordinary injectable record and silently orphan its
        sub-records.

        Spans are cached at the CLASS level and recomputed whenever the
        pointer table changes (see get_text_segments), so a relocated layout
        is re-scanned rather than reused.

        A catalog's sub-records are physically contiguous, so the detection
        window is cut at the first run of zeros longer than
        _CATALOG_MAX_ZERO_RUN. Without that cut a relocated record borrowed the
        next pointer of its own column as its window (~2 MB of dialogue pool),
        collected more than one FF 0A and was decoded as a catalog of 10M
        characters. The threshold is chosen with margin on both sides of the
        measurement (5 inside real catalogs, 1000+ in free space), and no
        size-based salvage is applied afterwards: a relocated record of
        0x800 bytes or more must stay injectable, otherwise a long
        translation is silently dropped instead of written.
        """
        cls = type(self)
        spans: dict[tuple[str, int], tuple[int, int]] = {}
        all_starts = sorted({
            off for lst in ptrs.values() for off in lst if 0 < off < len(data)
        })
        for lang, _slot in MLSS_LANGS:
            lst = ptrs[lang]
            for idx in range(MLSS_ENTRIES):
                off = lst[idx]
                if not (0 < off < len(data)):
                    continue
                structural = lst[idx + 1] if idx + 1 < MLSS_ENTRIES and lst[idx + 1] > off else (
                    off + 0x800)
                sub = 0
                zeros = 0
                j = off
                limit = min(structural, len(data))
                while j + 1 < limit:
                    if data[j] == 0x00:
                        zeros += 1
                        if zeros > cls._CATALOG_MAX_ZERO_RUN:
                            limit = j - zeros + 1
                            break
                    else:
                        zeros = 0
                    if data[j] == 0xFF and data[j + 1] == 0x0A:
                        sub += 1
                    j += 1
                if sub <= 1:
                    continue
                upper = limit
                pos = bisect.bisect_right(all_starts, off)
                if pos < len(all_starts):
                    upper = min(upper, all_starts[pos])
                # Решение о каталоге принимается по СОХРАНЁННОМУ спану: если
                # после клампа терминатор остался один, запись обычная и
                # обязана быть переводимой (иначе она выпала бы из вставки
                # обоих путей). Проверено на реальном ROM: es_889.
                kept = 0
                j = off
                while j + 1 < upper:
                    if data[j] == 0xFF and data[j + 1] == 0x0A:
                        kept += 1
                    j += 1
                if kept <= 1:
                    continue
                spans[(lang, idx)] = (off, upper)
        logger.info("Каталоговых записей (не инжектируемых): %d", len(spans))
        return spans

    def _make_segment(self, data, target: int, idx: int, lang: str,
                      spans: dict[tuple[str, int], tuple[int, int]]) -> dict | None:
        """Segment of a single record.

        A normal record is self-terminating: exactly one FF 0A (terminator),
        so the boundary = first FF 0A + 2 WITHOUT depending on neighbouring
        pointers (correct even after relocation into free space). Catalog records
        are read in full from the stored primary span (not injectable).
        """
        if not (0 < target < len(data)):
            return None
        # self-validation: speaker (2 bytes) + FF 0B 01
        if target + 4 >= len(data):
            return None
        if data[target + 2] != 0xFF or data[target + 3] != 0x0B:
            return None
        head = data[target:target + 2]

        catalog_span = spans.get((lang, idx))
        if catalog_span is not None:
            start, upper = catalog_span
            # Defence in depth: a stale or foreign span must not walk off the
            # end of the ROM (it used to raise IndexError on data[e - 1]).
            if not (0 < start < len(data)) or not (start < upper <= len(data)):
                logger.warning(
                    'Каталоговый спан вне ROM: %s_%d (%d, %d) - запись пропущена',
                    lang, idx, start, upper)
                return None
            target = start
            end = upper
            # strip the trailing 0x00 padding
            e = end
            while e > target and data[e - 1] == 0x00:
                e -= 1
            raw = self._decoder.decode(data, target, e - target)
            return {
                'name': f'mlss_{lang}_{idx}',
                'start': target,
                'end': e,
                'decoder': self._decoder,
                'compression': None,
                'charmap': None,
                'terminators': MLSS_TERMINATORS,
                'injectable': False,
                'raw_text': raw,
                'kind': 'record',
                'lang': lang,
                'index': idx,
                'head': head,
            }

        # normal record: first FF 0A + 2 = terminator (self-terminating)
        i = target
        end_ff: int | None = None
        n = len(data)
        while i + 1 < n:
            if data[i] == 0xFF and data[i + 1] == 0x0A:
                end_ff = i + 2
                break
            i += 1
        if end_ff is None:
            end_ff = min(target + 0x800, n)
        e = end_ff
        while e > target and data[e - 1] == 0x00:
            e -= 1
        raw = self._decoder.decode(data, target, e - target)

        return {
            'name': f'mlss_{lang}_{idx}',
            'start': target,
            'end': e,
            'decoder': self._decoder,
            'compression': None,
            'charmap': None,
            'terminators': MLSS_TERMINATORS,
            'injectable': True,
            'raw_text': raw,
            'kind': 'record',
            'lang': lang,
            'index': idx,
            'head': head,
        }

    def get_terminators(self, segment_name: str) -> list[int]:
        return MLSS_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None

    def lang_segments(self, segments: list[dict], lang: str) -> list[dict]:
        return [s for s in segments if s.get('lang') == lang]

    def injectable_masks(self, segments: list[dict], lang: str) -> list[bool]:
        """True/False per index: whether the record can be rebuilt."""
        segs = self.lang_segments(segments, lang)
        by_idx = {s['index']: s for s in segs}
        return [bool(by_idx.get(i) and by_idx[i].get('injectable')) for i in range(MLSS_ENTRIES)]
