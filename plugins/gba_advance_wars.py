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
Plugin for Advance Wars (GBA)

Game codes: AWRE (USA)

Text encoding: plain ASCII (0x20-0x7E), 0x0A/0x0D line breaks,
0x00 string terminator. Dialogue/menu strings live in pools
referenced by 32-bit little-endian pointer tables
(ROM-mapped at 0x08000000 + file offset).

Table offsets verified against the USA ROM by decoding every
target: each entry must resolve inside the ROM to a
NUL-terminated printable ASCII run. Tables that fail validation
at runtime (other revisions) are skipped entry-wise, so a wrong
revision yields fewer segments instead of garbage.

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging
import struct

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.advance_wars')

GAME_CODES = ['AWRE']

HEADER_BASE = 0x08000000
MAX_DECODE_LEN = 320

CHARMAP_ADVANCE_WARS: dict[int, str] = {
    **{code: chr(code) for code in range(0x20, 0x7F)},
    0x0A: '\n',
    0x0D: '\r',
}

TABLES: list[tuple[int, int]] = [
    (0x57FC, 6),
    (0x5884, 5),
    (0x3FF68, 9),
    (0x5EE30, 7),
    (0x69A98, 5),
    (0x81968, 4),
    (0x81A20, 4),
    (0x8216C, 3),
    (0x287210, 3),
    (0x287220, 7),
    (0x28303C, 3),
    (0x2830AC, 3),
    (0x28311C, 3),
    (0x2831FC, 3),
    (0x28326C, 3),
    (0x2832DC, 3),
    (0x28342C, 3),
    (0x28349C, 3),
    (0x2835EC, 3),
    (0x28365C, 3),
    (0x2836CC, 3),
    (0x28373C, 3),
    (0x28381C, 3),
    (0x28388C, 3),
    (0x2838FC, 3),
    (0x28396C, 3),
    (0x2839DC, 3),
    (0x283A4C, 3),
    (0x28C054, 16),
    (0x2E6DD8, 3),
    (0x2E6E18, 3),
    (0x2E6E70, 3),
    (0x2E6EB0, 3),
    (0x2E6ED8, 3),
    (0x2E6EF0, 3),
    (0x2E6F18, 3),
    (0x2E6F58, 3),
    (0x2E6F98, 3),
    (0x2E7018, 3),
    (0x2E7058, 3),
    (0x2E7070, 3),
    (0x2E7098, 3),
    (0x2EA1B8, 18),
    (0x2ECB28, 7),
    (0x2ECB48, 4),
    (0x2ECB5C, 6),
    (0x2F1700, 19),
    (0x3B9450, 18),
    (0x3BAB04, 10),
]


class AdvanceWarsTextDecoder:
    def __init__(self, charmap: dict[int, str] | None = None):
        self.charmap = charmap if charmap is not None else CHARMAP_ADVANCE_WARS
        self.last_unmapped_chars: list[str] = []
        self._reverse: dict[str, int] = {}
        for byte, char in self.charmap.items():
            if char not in self._reverse:
                self._reverse[char] = byte

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        end = min(start + length, len(data))
        i = start
        while i < end:
            byte = data[i]
            if byte == 0x00:
                break
            char = self.charmap.get(byte)
            if char is None:
                result.append(f'[{byte:02X}]')
            else:
                result.append(char)
            i += 1
        return ''.join(result)

    def encode(self, text: str) -> bytes:
        out: list[int] = []
        for char in text:
            if char == '\n':
                out.append(0x0A)
                continue
            byte = self._reverse.get(char)
            if byte is None:
                if char not in self.last_unmapped_chars:
                    self.last_unmapped_chars.append(char)
                raise ValueError(f'char {char!r} not in Advance Wars charmap')
            out.append(byte)
        return bytes(out)


def _decode_at(data: bytes, target: int) -> str | None:
    """Читает запись по адресу; None — адрес не указывает на строку.

    Порог «>= 2 буквы», стоявший здесь раньше, удалён: он не инвариантен к
    переводу. Сокращение `'Map11'` → `'M'` даёт одну букву, запись выпадала из
    манифеста, и обратное извлечение теряло её — измерено 31 запись из 186.
    Критерий отбора не должен зависеть от длины текста (правило из
    KNOWN_ISSUES). Проверка байтовой допустимости выше остаётся: непечатный
    байт означает, что адрес указывает не на строку.
    """
    if not 0 <= target < len(data):
        return None
    end = target
    limit = min(target + MAX_DECODE_LEN, len(data))
    while end < limit and data[end] != 0x00:
        end += 1
    if end >= len(data) or data[end] != 0x00 or end == target:
        return None
    raw = data[target:end]
    if not all(b == 0x0A or b == 0x0D or 0x20 <= b < 0x7F for b in raw):
        return None
    # raw уже проверен: каждый байт — 0x0A, 0x0D или 0x20..0x7E,
    # поэтому decode('ascii') не может бросить UnicodeDecodeError.
    return raw.decode('ascii')


def _entries_for_rom(data: bytes) -> list[dict]:
    by_target: dict[int, dict] = {}
    for table_offset, count in TABLES:
        if table_offset < 0 or table_offset + 4 * count > len(data):
            continue
        for i in range(count):
            cell = table_offset + 4 * i
            target = struct.unpack_from('<I', data, cell)[0] - HEADER_BASE
            text = _decode_at(data, target)
            if text is None:
                continue
            entry = by_target.get(target)
            if entry is None:
                by_target[target] = {'target': target, 'text': text, 'slots': [cell]}
            elif cell not in entry['slots']:
                entry['slots'].append(cell)
    entries: list[dict] = []
    ordered = sorted(by_target)
    for k, target in enumerate(ordered):
        entry = by_target[target]
        room = len(entry['text'].encode('ascii')) + 1
        end = target + room
        while end < len(data) and data[end] == 0x00 and end - target < MAX_DECODE_LEN:
            end += 1
        room = end - target
        if k + 1 < len(ordered):
            room = min(room, ordered[k + 1] - target)
        if room < len(entry['text'].encode('ascii')) + 1:
            continue
        entries.append({'target': target, 'free_after': room, 'slots': entry['slots']})
    return entries


class AdvanceWarsPlugin(GamePlugin):
    _is_stub = True

    def __init__(self):
        super().__init__()

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        data = bytes(rom.data)
        manifest = _entries_for_rom(data)
        if not manifest:
            logger.info('Advance Wars: no pointer tables validated, returning empty list')
            self._is_stub = True
            return []
        self._is_stub = False
        targets = [e['target'] for e in manifest]
        rooms = [e['free_after'] for e in manifest]
        start = min(targets)
        end = max(t + r for t, r in zip(targets, rooms, strict=True))
        logger.info(f'Advance Wars: {len(manifest)} dialogue strings via pointer tables')
        return [{
            'name': 'advance_wars_dialogues',
            'kind': 'pointer_dialogues',
            'start': start,
            'end': end,
            'decoder': AdvanceWarsTextDecoder(),
            'compression': None,
            'charmap': dict(CHARMAP_ADVANCE_WARS),
            'terminators': [0x00],
            'terminator': b'\x00',
            'manifest': manifest,
        }]

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00]

    def get_compression_handler(self, segment_name: str):
        return None
