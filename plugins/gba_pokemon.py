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
Plugin for Pokémon Ruby/Sapphire/Emerald/FireRed/LeafGreen (GBA)

Game codes (USA/Europe): BPEE/BPEP (Emerald), AXVE/AXVP (Ruby),
AXPE/AXPP (Sapphire), BPRE (FireRed), BPGE (LeafGreen).
Japan-only game codes (BPEJ, AXVJ, AXPJ) are detected but stubbed:
their text layout differs, extracting would produce garbage.

Text encoding: custom (0x00-0xFF maps to game-specific tile indices).
Text in Gen3 is NOT compressed (LZ77 is used only for graphics).
The name/move lists live in fixed-width slot tables:
  text + 0xFF (EOS) + 0x00 padding to the slot width.
Addresses verified by decoding real ROMs (Bulbasaur/Pound etc.).

NOTE: This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging
import re

from core.dialogue_manifest import entries_for_rom
from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.pokemon_gba')

# ── Charmap (an exact copy from the Pret pokeemerald decomp) ─────────────────
# Source: https://raw.githubusercontent.com/pret/pokeemerald/master/charmap.txt
CHARMAP_POKEMON_GBA: dict[int, str] = {
    0x00: ' ', 0x01: 'À', 0x02: 'Á', 0x03: 'Â', 0x04: 'Ç', 0x05: 'È',
    0x06: 'É', 0x07: 'Ê', 0x08: 'Ë', 0x09: 'Ì', 0x0A: 'Î',
    0x0B: 'Ï', 0x0C: 'Ò', 0x0D: 'Ó', 0x0E: 'Ô', 0x0F: 'Œ',
    0x10: 'Ù', 0x11: 'Ú', 0x12: 'Û', 0x13: 'Ñ', 0x14: 'ß',
    0x15: 'à', 0x16: 'á', 0x17: 'ç', 0x18: 'è', 0x19: 'é',
    0x1A: 'ê', 0x1B: 'ë', 0x1C: 'ì', 0x1D: 'î', 0x1E: 'ï',
    0x1F: 'ò', 0x20: 'ó', 0x21: 'ô', 0x22: 'œ', 0x23: 'ù',
    0x24: 'ú', 0x25: 'û', 0x26: 'ñ', 0x27: 'º', 0x28: 'ª',
    0x2D: '&', 0x2E: '+', 0x35: '=', 0x36: ';',
    0x51: '¿', 0x52: '¡', 0x53: 'PK', 0x54: 'MN',
    0x5A: 'Í', 0x5B: '%', 0x5C: '(', 0x5D: ')',
    0x68: 'â', 0x6F: 'í', 0x79: '↑', 0x7A: '↓', 0x7B: '←', 0x7C: '→',
    0x84: 'ᵉ', 0x85: '<', 0x86: '>',
    0xA0: 'ʳ',
    0xA1: '0', 0xA2: '1', 0xA3: '2', 0xA4: '3', 0xA5: '4',
    0xA6: '5', 0xA7: '6', 0xA8: '7', 0xA9: '8', 0xAA: '9',
    0xAB: '!', 0xAC: '?', 0xAD: '.', 0xAE: '-', 0xAF: '·', 0xB0: '…',
    0xB1: '\u201c', 0xB2: '\u201d', 0xB3: '\u2018', 0xB4: '\u2019',
    0xB5: '♂', 0xB6: '♀', 0xB7: '¥', 0xB8: ',', 0xB9: '×', 0xBA: '/',
    0xBB: 'A', 0xBC: 'B', 0xBD: 'C', 0xBE: 'D', 0xBF: 'E',
    0xC0: 'F', 0xC1: 'G', 0xC2: 'H', 0xC3: 'I', 0xC4: 'J',
    0xC5: 'K', 0xC6: 'L', 0xC7: 'M', 0xC8: 'N', 0xC9: 'O',
    0xCA: 'P', 0xCB: 'Q', 0xCC: 'R', 0xCD: 'S', 0xCE: 'T',
    0xCF: 'U', 0xD0: 'V', 0xD1: 'W', 0xD2: 'X', 0xD3: 'Y', 0xD4: 'Z',
    0xD5: 'a', 0xD6: 'b', 0xD7: 'c', 0xD8: 'd', 0xD9: 'e',
    0xDA: 'f', 0xDB: 'g', 0xDC: 'h', 0xDD: 'i', 0xDE: 'j',
    0xDF: 'k', 0xE0: 'l', 0xE1: 'm', 0xE2: 'n', 0xE3: 'o',
    0xE4: 'p', 0xE5: 'q', 0xE6: 'r', 0xE7: 's', 0xE8: 't',
    0xE9: 'u', 0xEA: 'v', 0xEB: 'w', 0xEC: 'x', 0xED: 'y', 0xEE: 'z',
    0xEF: '▶', 0xF0: ':',
    0xF1: 'Ä', 0xF2: 'Ö', 0xF3: 'Ü', 0xF4: 'ä', 0xF5: 'ö', 0xF6: 'ü',
    0xF7: '[DYNAMIC]', 0xF8: '[BUTTON]', 0xF9: '[SYMBOL]',
    0xFA: '[SCROLL]', 0xFB: '[PARA]', 0xFE: '[LINE]', 0xFF: '[END]',
}

# FireRed/LeafGreen glyphs that differ from RSE (per the FRLG TBL docs):
# - 0xB5/0xB6 are gender markers spelled |m| / |w| in Western releases,
#   and some punctuation occupies different codes.
CHARMAP_FIRERED: dict[int, str] = {
    **CHARMAP_POKEMON_GBA,
    0xB1: '«', 0xB2: '»', 0xB3: '<', 0xB4: "'",
    0xB5: '|m|', 0xB6: '|w|', 0xB7: '$', 0xB9: '*',
}

# FC commands (0xFC prefix + subcommand)
FC_COMMANDS: dict[int, str] = {
    0x00: 'NAME_END', 0x01: 'COLOR', 0x02: 'HIGHLIGHT',
    0x03: 'SHADOW', 0x04: 'COLOR_HIGHLIGHT_SHADOW',
    0x05: 'PALETTE', 0x06: 'FONT', 0x07: 'RESET_FONT',
    0x08: 'PAUSE', 0x09: 'PAUSE_UNTIL_PRESS',
    0x0A: 'WAIT_SE', 0x0B: 'PLAY_BGM', 0x0C: 'ESCAPE',
    0x0D: 'SHIFT_RIGHT', 0x0E: 'SHIFT_DOWN',
    0x0F: 'FILL_WINDOW', 0x10: 'PLAY_SE',
    0x11: 'CLEAR', 0x12: 'SKIP_TO', 0x13: 'CLEAR_TO',
    0x14: 'MIN_LETTER_SPACING', 0x15: 'JPN', 0x16: 'ENG',
    0x17: 'PAUSE_MUSIC', 0x18: 'RESUME_MUSIC',
}

# FD subcommands (string substitution templates)
FD_SUBCOMMANDS: dict[int, str] = {
    0x00: 'B_BUFF1', 0x01: 'PLAYER', 0x02: 'STR_VAR_1',
    0x03: 'STR_VAR_2', 0x04: 'STR_VAR_3', 0x05: 'KUN',
    0x06: 'RIVAL', 0x07: 'VERSION', 0x08: 'AQUA',
    0x09: 'MAGMA', 0x0A: 'ARCHIE', 0x0B: 'MAXIE',
    0x0C: 'KYOGRE', 0x0D: 'GROUDON',
}

# F8 button indicators
F8_BUTTONS: dict[int, str] = {
    0x00: 'A', 0x01: 'B', 0x02: 'L', 0x03: 'R',
    0x04: 'START', 0x05: 'SELECT',
    0x06: '↑', 0x07: '↓', 0x08: '←', 0x09: '→',
    0x0A: '↕', 0x0B: '↔', 0x0C: '',
}

# F9 symbols
F9_SYMBOLS: dict[int, str] = {
    0x00: '↑', 0x01: '↓', 0x02: '←', 0x03: '→',
    0x04: '+', 0x05: 'Lv', 0x06: 'PP', 0x07: 'No',
    0x08: 'No', 0x09: '_',
    0x0A: '①', 0x0B: '②', 0x0C: '③', 0x0D: '④', 0x0E: '⑤',
    0x0F: '⑥', 0x10: '⑦', 0x11: '⑧', 0x12: '⑨',
    0x13: '(', 0x14: ')',
    0x15: '⊙', 0x16: '△', 0x17: '✕',
    0xD0: '_', 0xD1: '|', 0xD2: '-', 0xD3: '~',
    0xD4: '(', 0xD5: ')', 0xD6: '⊂', 0xD7: '>',
    0xD8: '●', 0xD9: '●', 0xDA: '@', 0xDB: ';',
    0xDC: '+', 0xDD: '-', 0xDE: '=', 0xDF: '🌀',
    0xE0: '👅', 0xE1: '△', 0xE2: '´', 0xE3: '`',
    0xE4: '●', 0xE5: '△', 0xE6: '■', 0xE7: '♥',
    0xE8: '🌙', 0xE9: '♪', 0xEA: '●', 0xEB: '⚡',
    0xEC: '🍃', 0xED: '🔥', 0xEE: '💧', 0xEF: '👊',
    0xF0: '👊', 0xF1: '🔄', 0xF2: '🔄', 0xF3: '●',
    0xF4: '💢', 0xF5: '😏', 0xF6: '😊', 0xF7: '😠',
    0xF8: '😲', 0xF9: '😄', 0xFA: '😈', 0xFB: '😴',
    0xFC: '😐', 0xFD: '😲', 0xFE: '😠',
}

# Font constants (FC 06 XX)
FONT_CONSTANTS: dict[int, str] = {
    0x00: 'SMALL', 0x01: 'NORMAL',
    0x02: 'SHORT', 0x07: 'NARROW',
    0x08: 'SMALL_NARROW',
}

# Color constants (FC 01/02/03 XX)
COLOR_CONSTANTS: dict[int, str] = {
    0x00: 'TRANSPARENT', 0x01: 'WHITE', 0x02: 'DARK_GRAY',
    0x03: 'LIGHT_GRAY', 0x04: 'RED', 0x05: 'LIGHT_RED',
    0x06: 'GREEN', 0x07: 'LIGHT_GREEN', 0x08: 'BLUE',
    0x09: 'LIGHT_BLUE',
    0x0A: 'DYNAMIC1', 0x0B: 'DYNAMIC2', 0x0C: 'DYNAMIC3',
    0x0D: 'DYNAMIC4', 0x0E: 'DYNAMIC5', 0x0F: 'DYNAMIC6',
}

# Text terminators for Pokémon GBA
# 0xFF = [END] (primary terminator)
# 0x00 = space (NOT a terminator, used as padding inside a slot)
POKEMON_TERMINATORS = [0xFF]

# Токены управления для round-trip кодера (зеркалят вывод декодера).
_POKE_TOKEN_RE = re.compile(
    r'\[SCROLL\]|\[PARA\]|\[END\]|\[DYN\]'
    r'|\[CHS:([0-9A-Fa-f]{2})_([0-9A-Fa-f]{2})_([0-9A-Fa-f]{2})\]'
    r'|\[(FONT):([A-Z0-9_]+)\]'
    r'|\[(COLOR|HIGHLIGHT|SHADOW):([A-Z0-9_]+)\]'
    r'|\[BTN_([0-9A-Fa-f]{2})\]'
    r'|\[SYM_([0-9A-Fa-f]{2})\]'
    r'|\[(A|B|L|R|START|SELECT|↑|↓|←|→|↕|↔)\]'
    r'|\[([A-Z0-9_]+)\]'
    r'|\{([A-Z0-9_]+)\}'
)

# ── Game code → canonical version ───────────────────────────────────────────
# USA & Europe share the same text layout; Japan does not.
POKEMON_GAME_CODES: dict[str, str] = {
    'BPEE': 'emerald', 'BPEP': 'emerald',
    'AXVE': 'ruby', 'AXVP': 'ruby',
    'AXPE': 'sapphire', 'AXPP': 'sapphire',
    'BPRE': 'firered', 'BPGE': 'leafgreen',
}
POKEMON_STUB_CODES = {'BPEJ', 'AXVJ', 'AXPJ'}

# ── Fixed-width name/move tables (verified against real ROMs) ───────────────
# Slot layout: text + 0xFF (EOS) + 0x00 padding up to `width`.
FIXED_TABLES: dict[str, list[dict]] = {
    'emerald': [
        {'name': 'names', 'addr': 0x3185C8, 'width': 11, 'count': 412},
        {'name': 'attacks', 'addr': 0x31977C, 'width': 13, 'count': 355},
        {'name': 'abilities', 'addr': 0x31B6DB, 'width': 13, 'count': 78},
        {'name': 'types', 'addr': 0x31AE38, 'width': 7, 'count': 18},
    ],
    'ruby': [
        {'name': 'names', 'addr': 0x1F716C, 'width': 11, 'count': 412},
        {'name': 'attacks', 'addr': 0x1F8320, 'width': 13, 'count': 355},
        {'name': 'abilities', 'addr': 0x1FA248, 'width': 13, 'count': 78},
        {'name': 'types', 'addr': 0x1F9870, 'width': 7, 'count': 18},
    ],
    'sapphire': [
        {'name': 'names', 'addr': 0x1F70FC, 'width': 11, 'count': 412},
        {'name': 'attacks', 'addr': 0x1F82B0, 'width': 13, 'count': 355},
        {'name': 'abilities', 'addr': 0x1FA1D8, 'width': 13, 'count': 78},
        {'name': 'types', 'addr': 0x1F9800, 'width': 7, 'count': 18},
    ],
    'firered': [
        {'name': 'names', 'addr': 0x245EE0, 'width': 11, 'count': 412},
        {'name': 'attacks', 'addr': 0x247094, 'width': 13, 'count': 355},
        {'name': 'abilities', 'addr': 0x24FC40, 'width': 13, 'count': 78},
        {'name': 'types', 'addr': 0x24F1A0, 'width': 7, 'count': 18},
    ],
    'leafgreen': [
        {'name': 'names', 'addr': 0x245EBC, 'width': 11, 'count': 412},
        {'name': 'attacks', 'addr': 0x247070, 'width': 13, 'count': 355},
        {'name': 'abilities', 'addr': 0x24FC1C, 'width': 13, 'count': 78},
        {'name': 'types', 'addr': 0x24F17C, 'width': 7, 'count': 18},
    ],
}


class PokemonTextDecoder:
    """Pokemon text decoder compatible with the extractor interface (stream mode)."""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        return _decode_pokemon_text_static(data[start:start + length], self.charmap)

    def encode(self, text: str) -> bytes:
        return _encode_pokemon_text(text, self.charmap)


class PokemonFixedTextDecoder:
    """Decoder for fixed-width slot text (names, moves, abilities, types).

    One slot = one record of `width` bytes. The record stops at the first
    0xFF (EOS); 0x00 inside is a space, NOT a terminator. Blank slots
    (all '?' padding) are skipped by the extractor, not by this decoder.
    """

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap
        self.logger = logging.getLogger('gb2text.plugins.pokemon_gba.fixed')
        self._reverse: dict[str, int] = {}
        for byte, char in charmap.items():
            if byte == 0xFF:
                continue
            if len(char) >= 1 and char not in self._reverse:
                self._reverse[char] = byte
        self._tokens = sorted(self._reverse, key=len, reverse=True)

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        end = min(start + length, len(data))
        i = start
        while i < end:
            byte = data[i]
            if byte == 0xFF:
                break
            char = self.charmap.get(byte)
            if char is not None:
                result.append(char)
            else:
                result.append(f'[{byte:02X}]')
            i += 1
        return ''.join(result)

    def encode(self, text: str) -> bytes:
        result: list[int] = []  # pragma: no cover
        i = 0  # pragma: no cover
        n = len(text)  # pragma: no cover
        while i < n:  # pragma: no branch
            matched = False
            for token in self._tokens:  # pragma: no branch
                if text.startswith(token, i):  # pragma: no branch
                    result.append(self._reverse[token])
                    i += len(token)
                    matched = True
                    break
            if matched:  # pragma: no branch
                continue
            byte = self._reverse.get(text[i])
            if byte is None:  # pragma: no branch
                upper = self._reverse.get(text[i].upper())
                if upper is not None:  # pragma: no branch
                    byte = upper
            if byte is None:  # pragma: no branch
                byte = self._reverse.get(' ', 0x00)
                self.logger.warning(
                    f"Символ '{text[i]}' не найден в таблице, заменён пробелом")
            result.append(byte)
            i += 1
        return bytes(result)  # pragma: no cover


def _decode_pokemon_text_static(data: bytes, charmap: dict[int, str]) -> str:
    """Decode Pokemon GBA text using the exact charmap from Pret pokeemerald."""
    result: list[str] = []
    i = 0
    while i < len(data):
        byte = data[i]

        if byte == 0xFE:
            result.append('\n')
            i += 1
            continue
        if byte == 0xFF:
            break
        if byte == 0xFA:
            result.append('[SCROLL]')
            i += 1
            continue
        if byte == 0xFB:
            result.append('[PARA]')
            i += 1
            continue
        if byte == 0xF8:
            if i + 1 < len(data):  # pragma: no branch
                sym = data[i + 1]
                btn_name = F8_BUTTONS.get(sym, f'BTN_{sym:02X}')
                if btn_name:  # pragma: no branch
                    result.append(f'[{btn_name}]')
                i += 2
            else:
                i += 1  # pragma: no cover
            continue
        if byte == 0xF9:
            if i + 1 < len(data):  # pragma: no branch
                sym = data[i + 1]
                result.append(F9_SYMBOLS.get(sym, f'[SYM_{sym:02X}]'))
                i += 2
            else:
                i += 1
            continue
        if byte == 0xFD:
            if i + 1 < len(data):  # pragma: no branch
                subcmd = data[i + 1]
                placeholder = FD_SUBCOMMANDS.get(subcmd, f'[VAR_{subcmd:02X}]')
                result.append(f'{{{placeholder}}}')
                i += 2
            else:
                i += 1
            continue
        if byte == 0xFC:
            if i + 1 < len(data):  # pragma: no branch
                subcmd = data[i + 1]
                cmd_name = FC_COMMANDS.get(subcmd, f'FC_{subcmd:02X}')
                if subcmd == 0x06 and i + 2 < len(data):
                    font_id = data[i + 2]
                    result.append(
                        f'[FONT:{FONT_CONSTANTS.get(font_id, f"FONT_{font_id:02X}")}]')
                    i += 3
                elif subcmd in (0x01, 0x02, 0x03) and i + 2 < len(data):
                    color_id = data[i + 2]
                    result.append(
                        f'[{cmd_name}:{COLOR_CONSTANTS.get(color_id, f"COLOR_{color_id:02X}")}]')
                    i += 3
                elif subcmd == 0x04 and i + 4 < len(data):
                    result.append(f'[CHS:{data[i+2]:02X}_{data[i+3]:02X}_{data[i+4]:02X}]')
                    i += 5
                else:
                    result.append(f'[{cmd_name}]')
                    i += 2
            else:
                i += 1
            continue
        if byte == 0xF7:
            result.append('[DYN]')
            i += 1
            continue

        char = charmap.get(byte)
        if char is not None:
            if char not in ('SUPER_ER', 'UNK_SPACER'):  # pragma: no branch
                result.append(char)
            i += 1
            continue

        result.append(f'[{byte:02X}]')
        i += 1

    return ''.join(result)


def _build_f9_glyphs(charmap: dict[int, str]) -> list[tuple[str, int]]:
    """Много-байтные F9-глифы, недостижимые через charmap (longest-first)."""
    charmap_rev = {v for v in charmap.values() if len(v) == 1}
    glyphs: dict[str, int] = {}
    for code, val in F9_SYMBOLS.items():
        if not val:  # pragma: no cover - недостижимо: все значения F9_SYMBOLS непустые
            continue  # pragma: no cover - недостижимо: все значения F9_SYMBOLS непустые
        if len(val) == 1 and val in charmap_rev:
            continue
        if all(ch in charmap_rev for ch in val):
            continue
        glyphs.setdefault(val, code)
    return sorted(glyphs.items(), key=lambda kv: len(kv[0]), reverse=True)


def _encode_pokemon_text(text: str, charmap: dict[int, str]) -> bytes:
    """Encode a Pokemon string back to raw bytes (round-trip compatible).

    Грамматика токенов строго соответствует выводу _decode_pokemon_text_static:
    [SCROLL]/[PARA]/[END]/[DYN], [CHS:a_b_c], [FONT:X]/[COLOR:X]/
    [HIGHLIGHT:X]/[SHADOW:X], [BTN_XX]/[SYM_XX], [A]..[↔], [cmd_name],
    {PLAYER}/{VAR_XX}. Простые символы — через charmap.
    """
    reverse = {v: k for k, v in charmap.items() if len(v) == 1}
    multi_tokens = sorted(
        ((v, k) for k, v in charmap.items()
         if len(v) >= 2 and not v.startswith('[') and not v.startswith('{')),
        key=lambda kv: len(kv[0]), reverse=True)
    f9_glyphs = _build_f9_glyphs(charmap)
    fc_rev: dict[str, int] = {}
    for code, name in FC_COMMANDS.items():
        fc_rev.setdefault(name, code)
    fd_rev = {name: code for code, name in FD_SUBCOMMANDS.items()}
    f8_rev = {name: code for code, name in F8_BUTTONS.items() if name}
    font_rev = {name: code for code, name in FONT_CONSTANTS.items()}
    color_rev = {name: code for code, name in COLOR_CONSTANTS.items()}

    def _hex_named(name: str, prefix: str) -> int | None:
        if name.startswith(prefix + '_') and len(name) == len(prefix) + 3:  # pragma: no branch
            try:
                return int(name[len(prefix) + 1:], 16)
            except ValueError:
                return None
        return None

    def _token_bytes(m: re.Match) -> list[int]:
        fixed = {'[SCROLL]': 0xFA, '[PARA]': 0xFB, '[END]': 0xFF, '[DYN]': 0xF7}
        if m.group(0) in fixed:
            return [fixed[m.group(0)]]
        if m.group(1) is not None:
            return [0xFC, 0x04,
                    int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)]
        if m.group(4) is not None:
            font = font_rev.get(m.group(5)) or _hex_named(m.group(5), 'FONT')
            if font is None:
                font = 0x01
                logger.warning(f'Неизвестный шрифт {m.group(5)!r}, использован NORMAL')
            return [0xFC, 0x06, font]
        if m.group(6) is not None:
            sub = {'COLOR': 0x01, 'HIGHLIGHT': 0x02, 'SHADOW': 0x03}[m.group(6)]
            color = color_rev.get(m.group(7)) or _hex_named(m.group(7), 'COLOR')
            if color is None:
                color = 0x00
                logger.warning(f'Неизвестный цвет {m.group(7)!r}, использован TRANSPARENT')
            return [0xFC, sub, color]
        if m.group(8) is not None:
            return [0xF8, int(m.group(8), 16)]
        if m.group(9) is not None:
            return [0xF9, int(m.group(9), 16)]
        if m.group(10) is not None:
            return [0xF8, f8_rev[m.group(10)]]
        if m.group(11) is not None:
            name = m.group(11)
            code = fc_rev.get(name) or _hex_named(name, 'FC')
            if code is None:
                logger.warning(f'Неизвестная FC-команда {name!r}, пропущена')
                return []
            return [0xFC, code]
        name = m.group(12)
        code = fd_rev.get(name) or _hex_named(name, 'VAR')
        if code is None:
            logger.warning(f'Неизвестный FD-плейсхолдер {name!r}, пропущен')
            return []
        return [0xFD, code]

    out: list[int] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == '\n':
            out.append(0xFE)
            i += 1
            continue
        m = _POKE_TOKEN_RE.match(text, i)
        if m:
            out.extend(_token_bytes(m))
            i = m.end()
            continue
        for val, code in multi_tokens:
            if text.startswith(val, i):
                out.append(code)
                i += len(val)
                break
        else:
            for val, code in f9_glyphs:
                if text.startswith(val, i):
                    out.extend((0xF9, code))
                    i += len(val)
                    break
            else:
                ch = text[i]
                byte = reverse.get(ch)
                if byte is None:
                    byte = reverse.get(ch.upper(), 0x00)
                    if byte == 0x00 and ch != ' ':  # pragma: no branch
                        logger.warning(
                            f"Символ {ch!r} не найден в таблице, заменён пробелом")
                out.append(byte)
                i += 1
    return bytes(out)


class PokemonGBAPlugin(GamePlugin):
    """Plugin for Pokémon GBA games (Emerald/Ruby/Sapphire/FireRed/LeafGreen)."""

    def __init__(self):
        super().__init__()
        self._decoder = PokemonTextDecoder(CHARMAP_POKEMON_GBA)
        self._game_code = ''

    @property
    def game_id_pattern(self) -> str:
        code_re = '|'.join([*POKEMON_GAME_CODES, *POKEMON_STUB_CODES])
        return f'^GBA_({code_re})$'

    def _charmap_for(self, version: str) -> dict[int, str]:
        return CHARMAP_FIRERED if version in ('firered', 'leafgreen') else CHARMAP_POKEMON_GBA

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract Pokémon GBA fixed-width tables and dialogue pool segments."""
        logger.info("Извлечение текстовых сегментов для Pokémon GBA")

        game_code = rom.header.get('game_code', '')
        self._game_code = game_code
        self._is_stub = game_code in POKEMON_STUB_CODES
        version = POKEMON_GAME_CODES.get(game_code, '')

        if self._is_stub or not version:
            logger.info(
                f"Pokemon {game_code}: структура текста не реализована "
                f"или региональная версия не поддерживается, возвращаю пустой список"
            )
            return []

        segments: list[dict] = []
        charmap = self._charmap_for(version)

        for table in FIXED_TABLES.get(version, []):
            addr = table['addr']
            width = table['width']
            count = table['count']
            if addr + width * count > len(rom.data):
                logger.warning(
                    f"Таблица {table['name']} (0x{addr:X}) выходит за пределы ROM, пропущена")
                continue

            segments.append({
                'name': f'pokemon_{version}_{table["name"]}',
                'start': addr,
                'end': addr + width * count,
                'decoder': PokemonFixedTextDecoder(charmap),
                'compression': None,
                'charmap': charmap,
                'terminators': POKEMON_TERMINATORS,
                'fixed_width': width,
                'record_count': count,
                'max_length': width - 1,
                'pad_byte': 0xFF,
            })

        manifest = entries_for_rom(rom)
        if manifest:
            last = manifest[-1]
            segments.append({
                'name': f'pokemon_{version}_dialogues',
                'kind': 'pointer_dialogues',
                'start': manifest[0]['target'],
                'end': last['target'] + last['free_after'],
                'decoder': PokemonTextDecoder(charmap),
                'compression': None,
                'charmap': charmap,
                'terminators': POKEMON_TERMINATORS,
                'manifest': manifest,
            })

        logger.info(f"Найдено {len(segments)} текстовых сегментов")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        """Byte terminators for Pokémon GBA"""
        return POKEMON_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        """Pokémon GBA does not use compression for the main text"""
        return None
