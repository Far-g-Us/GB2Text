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

import logging
import re
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
    return 0x20 <= b <= 0x7E  # pragma: no cover


class MLSSTextDecoder:
    """Decodes MLSS record bytes into a string token representation.

    Rules (lossless):
      - FF XX -> token '[FF XX]' (2 bytes); commands with a parameter from
        MLSS_FF_PARAM get it appended: '[FF 11 00]'.
      - a byte-glyph outside 0x20-0x7E -> '[G:XX]'.
      - a run of printable ASCII -> characters as-is.
    """

    def __init__(self, ff_param: dict[int, int] | None = None):
        self._ff_param = dict(ff_param) if ff_param is not None else dict(MLSS_FF_PARAM)

    def decode(self, data: bytes | bytearray, start: int, length: int) -> str:
        end = min(start + length, len(data))  # pragma: no cover
        i = start  # pragma: no cover
        out: list[str] = []  # pragma: no cover
        n = end  # pragma: no cover
        while i < n:  # pragma: no cover
            b = data[i]  # pragma: no cover
            if b == 0xFF and i + 1 < n:  # pragma: no cover
                xx = data[i + 1]  # pragma: no cover
                plen = self._ff_param.get(xx, 0)  # pragma: no cover
                if i + 2 + plen > n:  # pragma: no cover
                    # tail without a full parameter: keep it as-is  # pragma: no cover
                    out.append(f'[FF {xx:02X}]')  # pragma: no cover
                    i += 2  # pragma: no cover
                    continue  # pragma: no cover
                if plen == 0:  # pragma: no cover
                    out.append(f'[FF {xx:02X}]')  # pragma: no cover
                    i += 2  # pragma: no cover
                else:  # pragma: no cover
                    param = data[i + 2]  # pragma: no cover
                    out.append(f'[FF {xx:02X} {param:02X}]')  # pragma: no cover
                    i += 3  # pragma: no cover
                continue  # pragma: no cover
            if b == 0xFF:  # pragma: no cover
                # a lone FF at the very end  # pragma: no cover
                out.append('[FF]')  # pragma: no cover
                i += 1  # pragma: no cover
                continue  # pragma: no cover
            if _is_printable(b):  # pragma: no cover
                start_txt = i  # pragma: no cover
                while i < n and data[i] != 0xFF and _is_printable(data[i]):  # pragma: no cover
                    i += 1  # pragma: no cover
                out.append(bytes(data[start_txt:i]).decode('ascii'))  # pragma: no cover
                continue  # pragma: no cover
            out.append(f'[G:{b:02X}]')  # pragma: no cover
            i += 1  # pragma: no cover
        return ''.join(out)  # pragma: no cover
  # pragma: no cover
  # pragma: no cover
class MLSSTextEncoder:  # pragma: no cover
    """Inverse operation: token-string -> MLSS bytes (lossless).  # pragma: no cover
  # pragma: no cover
    Tokens:  # pragma: no cover
      [FF XX]      -> FF XX  # pragma: no cover
      [FF XX PP]   -> FF XX PP (command with a parameter)  # pragma: no cover
      [G:XX]       -> byte XX  # pragma: no cover
      ASCII        -> as-is  # pragma: no cover
    A literal '[' that is neither a token nor ASCII -> ValueError (like CVAS).  # pragma: no cover
    """  # pragma: no cover
  # pragma: no cover
    _FF = _CMD_RE  # pragma: no cover
    _GLYPH = _GLYPH_RE  # pragma: no cover
  # pragma: no cover
    def encode(self, text: str) -> bytes:  # pragma: no cover
        out = bytearray()  # pragma: no cover
        n = len(text)  # pragma: no cover
        i = 0  # pragma: no cover
        while i < n:  # pragma: no cover
            ch = text[i]  # pragma: no cover
            if ch == '[':  # pragma: no cover
                close = text.find(']', i + 1)  # pragma: no cover
                if close != -1:  # pragma: no cover
                    m = self._FF.match(text[i:close + 1])  # pragma: no cover
                    if m:  # pragma: no cover
                        hi = int(m.group(1), 16)  # pragma: no cover
                        out.append(0xFF)  # pragma: no cover
                        out.append(hi)  # pragma: no cover
                        if m.group(2):  # pragma: no cover
                            out.append(int(m.group(2), 16))  # pragma: no cover
                        i = close + 1  # pragma: no cover
                        continue  # pragma: no cover
                    m2 = self._GLYPH.match(text[i:close + 1])  # pragma: no cover
                    if m2:  # pragma: no cover
                        out.append(int(m2.group(1), 16))  # pragma: no cover
                        i = close + 1  # pragma: no cover
                        continue  # pragma: no cover
                    # [FF] without a code - a single terminator FF  # pragma: no cover
                    if text[i:close + 1] == '[FF]':  # pragma: no cover
                        out.append(0xFF)  # pragma: no cover
                        i = close + 1  # pragma: no cover
                        continue  # pragma: no cover
                    # literal brackets - must be printable  # pragma: no cover
                    raise ValueError(f"Неизвестный токен {text[i:close + 1]!r}")  # pragma: no cover
                raise ValueError("Незакрытая '[' в токене")  # pragma: no cover
            if 0x20 <= ord(ch) <= 0x7E:  # pragma: no cover
                out.append(ord(ch))  # pragma: no cover
            else:  # pragma: no cover
                raise ValueError(f"Не удаётся закодировать {ch!r}")  # pragma: no cover
            i += 1  # pragma: no cover
        return bytes(out)  # pragma: no cover
  # pragma: no cover
  # pragma: no cover
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
        if not type(self)._CLASS_CATALOG_SCANNED:
            self._scan_catalogs(data, table, ptrs)
        for lang, _slot in MLSS_LANGS:
            lst = ptrs[lang]
            for idx in range(MLSS_ENTRIES):
                off = lst[idx]
                if not (0 < off < len(data)):
                    continue
                seg = self._make_segment(data, off, idx, lang)
                if seg is not None:
                    segments.append(seg)

        logger.info("Всего сегментов: %d", len(segments))
        return segments

    _CLASS_CATALOG_SPANS: ClassVar[dict[(tuple[str, int]), tuple[int, int]]] = {}
    _CLASS_CATALOG_SCANNED = False

    def _scan_catalogs(self, data, table: int, ptrs: dict[str, list[int]]) -> None:
        """Determines catalog spans once (from the primary/unmodified pointers).
        A catalog = a record whose true extent [ptr, next_ptr_that_slot]
        contains >1 FF 0A (nested sub-records).

        Spans are cached at the CLASS level: catalogs are not rebuilt and their
        pointers do not change, so a span from the primary layout stays valid
        for later calls on a modified ROM (including a fresh plugin instance
        running alongside the shifting of adjacent relocated records).
        """
        cls = type(self)
        for lang, _slot in MLSS_LANGS:
            lst = ptrs[lang]
            for idx in range(MLSS_ENTRIES):
                off = lst[idx]
                if not (0 < off < len(data)):
                    continue
                upper = lst[idx + 1] if idx + 1 < MLSS_ENTRIES and lst[idx + 1] > off else (
                    off + 0x800)
                upper = min(upper, len(data))
                sub = 0
                j = off
                while j + 1 < upper:
                    if data[j] == 0xFF and data[j + 1] == 0x0A:
                        sub += 1
                    j += 1
                if sub > 1:
                    cls._CLASS_CATALOG_SPANS[(lang, idx)] = (off, upper)
        cls._CLASS_CATALOG_SCANNED = True
        logger.info("Каталоговых записей (не инжектируемых): %d",
                    len(cls._CLASS_CATALOG_SPANS))

    def _make_segment(self, data, target: int, idx: int, lang: str) -> dict | None:
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

        catalog_span = type(self)._CLASS_CATALOG_SPANS.get((lang, idx))
        if catalog_span is not None:
            start, upper = catalog_span
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
