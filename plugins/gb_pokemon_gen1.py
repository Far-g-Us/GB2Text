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
Plugin for Pokemon Gen1 (Red/Blue/Green/Yellow) — GB/GBC

Text encoding: custom charmap from pret/pokered.
Source: https://raw.githubusercontent.com/pret/pokered/master/constants/charmap.asm

Tables extracted:
  - ItemNames:    variable-length, 0x50-terminated strings
  - MonsterNames: fixed-width (10 bytes/slot), 0x50 = terminator/padding
  - MoveNames:    variable-length, 0x50-terminated strings

Addresses verified against real ROMs.
Red/Blue/Green share the same layout (verified on "Pokemon Red/Blue/Green
Version (USA, Europe).gb"); Yellow uses its own offsets (verified on
"Pokemon Yellow Version - Special Pikachu Edition (USA, Europe).gb").

NOTE: This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.pokemon_gen1')

# ── Charmap (from pret/pokered constants/charmap.asm) ───────────────────────

CHARMAP_GEN1: dict[int, str] = {
    # Control characters
    0x49: '[PAGE]', 0x4a: '[PKMN]', 0x4b: '[_CONT]', 0x4c: '[SCROLL]',
    0x4e: '[NEXT]', 0x4f: '[LINE]', 0x50: '@',  # string terminator
    0x51: '[PARA]', 0x52: '[PLAYER]', 0x53: '[RIVAL]',
    0x54: '#',  # "POKé" glyph
    0x55: '[CONT]', 0x56: '[……]', 0x57: '[DONE]', 0x58: '[PROMPT]',
    0x59: '[TARGET]', 0x5a: '[USER]', 0x5b: '[PC]', 0x5c: '[TM]',
    0x5d: '[TRAINER]', 0x5e: '[ROCKET]', 0x5f: '[DEXEND]',

    # Box drawing
    0x79: '┌', 0x7a: '─', 0x7b: '┐', 0x7c: '│', 0x7d: '└', 0x7e: '┘',
    0x7f: ' ',

    # Uppercase A-Z
    0x80: 'A', 0x81: 'B', 0x82: 'C', 0x83: 'D', 0x84: 'E', 0x85: 'F',
    0x86: 'G', 0x87: 'H', 0x88: 'I', 0x89: 'J', 0x8a: 'K', 0x8b: 'L',
    0x8c: 'M', 0x8d: 'N', 0x8e: 'O', 0x8f: 'P', 0x90: 'Q', 0x91: 'R',
    0x92: 'S', 0x93: 'T', 0x94: 'U', 0x95: 'V', 0x96: 'W', 0x97: 'X',
    0x98: 'Y', 0x99: 'Z',

    # Punctuation
    0x9a: '(', 0x9b: ')', 0x9c: ':', 0x9d: ';', 0x9e: '[', 0x9f: ']',

    # Lowercase a-z
    0xa0: 'a', 0xa1: 'b', 0xa2: 'c', 0xa3: 'd', 0xa4: 'e', 0xa5: 'f',
    0xa6: 'g', 0xa7: 'h', 0xa8: 'i', 0xa9: 'j', 0xaa: 'k', 0xab: 'l',
    0xac: 'm', 0xad: 'n', 0xae: 'o', 0xaf: 'p', 0xb0: 'q', 0xb1: 'r',
    0xb2: 's', 0xb3: 't', 0xb4: 'u', 0xb5: 'v', 0xb6: 'w', 0xb7: 'x',
    0xb8: 'y', 0xb9: 'z',

    # Special multi-char tokens
    0xba: 'é', 0xbb: "'d", 0xbc: "'l", 0xbd: "'s", 0xbe: "'t", 0xbf: "'v",

    # More punctuation
    0xe0: "'", 0xe1: '<PK>', 0xe2: '<MN>', 0xe3: '-',
    0xe4: "'r", 0xe5: "'m",
    0xe6: '?', 0xe7: '!', 0xe8: '.',

    # Misc
    0xed: '▶', 0xef: '♂', 0xf0: '¥', 0xf1: '×',
    0xf3: '/', 0xf4: ',', 0xf5: '♀',

    # Digits
    0xf6: '0', 0xf7: '1', 0xf8: '2', 0xf9: '3', 0xfa: '4',
    0xfb: '5', 0xfc: '6', 0xfd: '7', 0xfe: '8', 0xff: '9',
}

# Known Gen1 titles. Blue/Green share the Red layout; Yellow uses its own.
# Gold/Silver/Crystal (Gen2) are NOT Gen1.
GEN1_TITLES = {'POKEMON RED', 'POKEMON BLUE', 'POKEMON GREEN',
               'POKEMON YELLOW'}

# Gen1 text terminators
GEN1_TERMINATORS = [0x50]

# Fixed tables for Pokemon Gen1.
# Red/Blue/Green (USA, Europe) — verified by decoding real ROMs.
# Yellow — device layout (item 0x45B7, monster 0xE8000, move 0xBC000),
# verified on "Pokemon Yellow Version - Special Pikachu Edition (USA, Europe).gb".
GEN1_TABLES: dict[str, list[dict]] = {
    'POKEMON RED': [
        {'name': 'item_names', 'start': 0x472B, 'end': 0x4A92},
        {'name': 'monster_names', 'start': 0x1C21E, 'end': 0x1C98A,
         'fixed_width': 10},
        {'name': 'move_names', 'start': 0xB0000, 'end': 0xB060F},
    ],
    'POKEMON BLUE': [
        {'name': 'item_names', 'start': 0x472B, 'end': 0x4A92},
        {'name': 'monster_names', 'start': 0x1C21E, 'end': 0x1C98A,
         'fixed_width': 10},
        {'name': 'move_names', 'start': 0xB0000, 'end': 0xB060F},
    ],
    'POKEMON GREEN': [
        {'name': 'item_names', 'start': 0x472B, 'end': 0x4A92},
        {'name': 'monster_names', 'start': 0x1C21E, 'end': 0x1C98A,
         'fixed_width': 10},
        {'name': 'move_names', 'start': 0xB0000, 'end': 0xB060F},
    ],
    'POKEMON YELLOW': [
        {'name': 'item_names', 'start': 0x45B7, 'end': 0x491E},
        {'name': 'monster_names', 'start': 0xE8000, 'end': 0xE876C,
         'fixed_width': 10},
        {'name': 'move_names', 'start': 0xBC000, 'end': 0xBC60F},
    ],
}


class Gen1TextDecoder:
    """Decoder for variable-length Gen1 text (ItemNames, MoveNames).

    Decodes the full byte range; 0x50 → '[END]' for _split_messages.
    """

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap
        self.logger = logging.getLogger('gb2text.plugins.pokemon_gen1.decoder')
        self._multi = sorted(
            ((v, k) for k, v in charmap.items() if len(v) >= 2),
            key=lambda kv: len(kv[0]), reverse=True)
        self._single = {v: k for k, v in charmap.items() if len(v) == 1}

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        end = min(start + length, len(data))
        i = start
        while i < end:
            byte = data[i]
            if byte == 0x50:
                result.append('[END]')
                i += 1
                continue
            char = self.charmap.get(byte)
            if char is not None:
                result.append(char)
                i += 1
                continue
            result.append(f'[{byte:02X}]')
            i += 1
        return ''.join(result)

    def encode(self, text: str) -> bytes:
        out: list[int] = []
        i = 0
        n = len(text)
        while i < n:
            if text[i:i + 5] == '[END]':
                i += 5
                continue
            if (text[i] == '[' and i + 3 < len(text) and text[i + 3] == ']'
                    and all(c in '0123456789ABCDEFabcdef'
                            for c in text[i + 1:i + 3])):
                i += 4
                continue
            matched = False
            for val, code in self._multi:
                if text.startswith(val, i):
                    out.append(code)
                    i += len(val)
                    matched = True
                    break
            if matched:
                continue
            ch = text[i]
            byte = self._single.get(ch) or self._single.get(ch.upper())
            if byte is None:
                self.logger.warning(
                    f"Symbol {ch!r} not found in Gen1 charmap, skipped")
                i += 1
                continue
            out.append(byte)
            i += 1
        return bytes(out)


class Gen1FixedDecoder:
    """Decoder for fixed-width Gen1 text (MonsterNames).

    One slot = 10 bytes. The name occupies the first N bytes;
    the rest is 0x50 padding. Decoder stops at the first 0x50.
    """

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap
        self.logger = logging.getLogger('gb2text.plugins.pokemon_gen1.fixed')
        self._reverse = {v: k for k, v in charmap.items()}
        self._tokens = sorted(self._reverse, key=len, reverse=True)

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        end = min(start + length, len(data))
        i = start
        while i < end:
            byte = data[i]
            if byte == 0x50:
                break
            char = self.charmap.get(byte)
            if char is not None:
                result.append(char)
            else:
                result.append(f'[{byte:02X}]')
            i += 1
        return ''.join(result)

    def encode(self, text: str) -> bytes:
        out: list[int] = []
        i = 0
        n = len(text)
        while i < n:
            if (text[i] == '[' and i + 3 < len(text) and text[i + 3] == ']'
                    and all(c in '0123456789ABCDEFabcdef'
                            for c in text[i + 1:i + 3])):
                i += 4
                continue
            matched = False
            for token in self._tokens:
                if text.startswith(token, i):
                    out.append(self._reverse[token])
                    i += len(token)
                    matched = True
                    break
            if matched:
                continue
            ch = text[i]
            byte = self._reverse.get(ch) or self._reverse.get(ch.upper())
            if byte is None:
                byte = self._reverse.get(' ')
                if byte is None:
                    raise ValueError(
                        f"No replacement byte for symbol {ch!r}")
                self.logger.warning(
                    f"Symbol {ch!r} not found, replaced with space")
            out.append(byte)
            i += 1
        return bytes(out)


class PokemonGen1Plugin(GamePlugin):
    """Plugin for Pokemon Gen1 games (Red/Blue/Green/Yellow) on GB/GBC."""

    def __init__(self):
        super().__init__()
        self._decoder = Gen1TextDecoder(CHARMAP_GEN1)
        self._fixed_decoder = Gen1FixedDecoder(CHARMAP_GEN1)

    @property
    def game_id_pattern(self) -> str:
        return r'^(GB|GBC)_POKEMON'

    def validate_rom(self, rom: GameBoyROM) -> bool:
        title = rom.header.get('title', '')
        if title.upper().strip() not in GEN1_TITLES:
            return False
        if len(rom.data) not in (0x100000, 0x200000):
            return False
        return True

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        logger.info("Extracting text segments for Pokemon Gen1")

        title = rom.header.get('title', '')
        safe_title = title.upper().strip()

        tables = GEN1_TABLES.get(safe_title)
        if tables is None:
            self._is_stub = True
            logger.info(
                f"Pokemon Gen1 '{safe_title}': table layout not implemented, "
                f"returning empty list")
            return []
        self._is_stub = False

        segments: list[dict] = []
        for table in tables:
            start = table['start']
            end = table['end']
            if end > len(rom.data):
                logger.warning(
                    f"Table {table['name']} (0x{start:X}-0x{end:X}) "
                    f"exceeds ROM size, skipped")
                continue

            fw = table.get('fixed_width')
            if fw:
                record_count = (end - start) // fw
                seg = {
                    'name': f'gen1_{table["name"]}',
                    'start': start,
                    'end': start + record_count * fw,
                    'decoder': self._fixed_decoder,
                    'compression': None,
                    'charmap': CHARMAP_GEN1,
                    'terminators': GEN1_TERMINATORS,
                    'fixed_width': fw,
                    'record_count': record_count,
                    'max_length': fw,
                    'pad_byte': 0x50,
                }
            else:
                seg = {
                    'name': f'gen1_{table["name"]}',
                    'start': start,
                    'end': end,
                    'decoder': self._decoder,
                    'compression': None,
                    'charmap': CHARMAP_GEN1,
                    'terminators': GEN1_TERMINATORS,
                    'pad_byte': 0x50,
                }
            segments.append(seg)

        logger.info(f"Found {len(segments)} text segments")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return GEN1_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None
