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
Плагин для Pokémon Emerald/Ruby/Sapphire (GBA)

Game codes: AXPE (Emerald USA), AXSE (Emerald Spain), BPEE (Emerald Europe)
             AXRE (Ruby USA), AXRS (Ruby USA v1.1), AXRI (Ruby Italy)
             AXVE (Sapphire USA), AXVS (Sapphire Spain), AXVI (Sapphire Italy)

Text encoding: Custom (0x00-0xFF maps to game-specific tile indices)
Known facts:
- Pokémon games use a custom text encoding with control codes
- Pointer tables are located at known offsets in ROM banks
- Text is terminated by specific byte sequences

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.gba_support import GBALZ77Handler
from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.pokemon_gba')

# Pokémon GBA charmap (EXACT from Pret pokeemerald decomp)
# Source: https://raw.githubusercontent.com/pret/pokeemerald/master/charmap.txt
# This is the ACTUAL encoding used in Pokémon Emerald/Ruby/Sapphire
CHARMAP_POKEMON_GBA: dict[int, str] = {
    # Space and accented characters
    0x00: ' ',
    0x01: 'À', 0x02: 'Á', 0x03: 'Â', 0x04: 'Ç', 0x05: 'È',
    0x06: 'É', 0x07: 'Ê', 0x08: 'Ë', 0x09: 'Ì', 0x0A: 'Î',
    0x0B: 'Ï', 0x0C: 'Ò', 0x0D: 'Ó', 0x0E: 'Ô', 0x0F: 'Œ',
    0x10: 'Ù', 0x11: 'Ú', 0x12: 'Û', 0x13: 'Ñ', 0x14: 'ß',
    0x15: 'à', 0x16: 'á', 0x17: 'ç', 0x18: 'è', 0x19: 'é',
    0x1A: 'ê', 0x1B: 'ë', 0x1C: 'ì', 0x1D: 'î', 0x1E: 'ï',
    0x1F: 'ò', 0x20: 'ó', 0x21: 'ô', 0x22: 'œ', 0x23: 'ù',
    0x24: 'ú', 0x25: 'û', 0x26: 'ñ', 0x27: 'º', 0x28: 'ª',
    0x2C: 'SUPER_ER',  # Multi-byte: 2C
    0x2D: '&', 0x2E: '+',
    0x34: 'LV',
    0x35: '=', 0x36: ';', 0x51: '¿', 0x52: '¡',

    # Pokemon markers (PKMN = 53 54)
    0x53: 'PK',
    0x54: 'MN',

    # POKEBLOCK (5 bytes: 55 56 57 58 59)
    0x5A: 'Í', 0x5B: '%', 0x5C: '(', 0x5D: ')',
    0x68: 'â', 0x6F: 'í',
    0x77: 'UNK_SPACER',
    0x79: '↑', 0x7A: '↓', 0x7B: '←', 0x7C: '→',
    0x84: 'ᵉ',  # SUPER_E
    0x85: '<', 0x86: '>',
    0xA0: 'ʳ',  # SUPER_RE

    # Numbers 0-9
    0xA1: '0', 0xA2: '1', 0xA3: '2', 0xA4: '3', 0xA5: '4',
    0xA6: '5', 0xA7: '6', 0xA8: '7', 0xA9: '8', 0xAA: '9',

    # Punctuation
    0xAB: '!', 0xAC: '?', 0xAD: '.', 0xAE: '-',
    0xAF: '·', 0xB0: '…',
    0xB1: '\u201c', 0xB2: '\u201d',  # Left/right double quotes
    0xB3: '\u2018', 0xB4: '\u2019',  # Left/right single quotes
    0xB5: '♂', 0xB6: '♀',
    0xB7: '¥', 0xB8: ',', 0xB9: '×', 0xBA: '/',

    # Uppercase A-Z
    0xBB: 'A', 0xBC: 'B', 0xBD: 'C', 0xBE: 'D', 0xBF: 'E',
    0xC0: 'F', 0xC1: 'G', 0xC2: 'H', 0xC3: 'I', 0xC4: 'J',
    0xC5: 'K', 0xC6: 'L', 0xC7: 'M', 0xC8: 'N', 0xC9: 'O',
    0xCA: 'P', 0xCB: 'Q', 0xCC: 'R', 0xCD: 'S', 0xCE: 'T',
    0xCF: 'U', 0xD0: 'V', 0xD1: 'W', 0xD2: 'X', 0xD3: 'Y',
    0xD4: 'Z',

    # Lowercase a-z
    0xD5: 'a', 0xD6: 'b', 0xD7: 'c', 0xD8: 'd', 0xD9: 'e',
    0xDA: 'f', 0xDB: 'g', 0xDC: 'h', 0xDD: 'i', 0xDE: 'j',
    0xDF: 'k', 0xE0: 'l', 0xE1: 'm', 0xE2: 'n', 0xE3: 'o',
    0xE4: 'p', 0xE5: 'q', 0xE6: 'r', 0xE7: 's', 0xE8: 't',
    0xE9: 'u', 0xEA: 'v', 0xEB: 'w', 0xEC: 'x', 0xED: 'y',
    0xEE: 'z',

    # Special
    0xEF: '▶', 0xF0: ':',
    0xF1: 'Ä', 0xF2: 'Ö', 0xF3: 'Ü', 0xF4: 'ä', 0xF5: 'ö', 0xF6: 'ü',

    # Control codes
    0xF7: '[DYNAMIC]',  # Special 0xF7 character
    0xF8: '[BUTTON]',  # Button indicator (F8 00-F8 0C)
    0xF9: '[SYMBOL]',  # Symbol (F9 00-F9 FE)
    0xFA: '[SCROLL]',  # \l - scroll up window text
    0xFB: '[PARA]',     # \p - new paragraph
    0xFE: '[LINE]',     # \n - new line
    0xFF: '[END]',      # End of string
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

# FD subcommands (string placeholders)
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
    # Emojis (F9 D0-FE)
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

# Known pointer table locations for Pokémon GBA games
# These are addresses where pointer tables to text strings are located
# Source: Public ROM hacking documentation (GBATEK, PokeCommunity)
POKEMON_POINTER_TABLES = {
    'emerald': [
        # Main dialogue banks (approximate offsets)
        (0x08000000 + 0x1C0000, 0x08000000 + 0x1E0000),  # Dialogue 1
        (0x08000000 + 0x250000, 0x08000000 + 0x270000),  # Dialogue 2
        (0x08000000 + 0x3D0000, 0x08000000 + 0x3F0000),  # Menu/UI text
    ],
    'ruby': [
        (0x08000000 + 0x1A0000, 0x08000000 + 0x1C0000),
        (0x08000000 + 0x230000, 0x08000000 + 0x250000),
    ],
    'sapphire': [
        (0x08000000 + 0x1A0000, 0x08000000 + 0x1C0000),
        (0x08000000 + 0x230000, 0x08000000 + 0x250000),
    ],
}

# Text terminators for Pokémon GBA
# 0xFF = [END] (main terminator)
# 0x00 = space (NOT a terminator, but used as padding)
POKEMON_TERMINATORS = [0xFF]

# Control code prefixes that need special handling
POKEMON_CONTROL_PREFIXES = [0xFD, 0xFC, 0xF7]

# Game codes for detection
# USA: BPEE (Emerald), AXRE (Ruby), AXVE (Sapphire)
# Europe: BPEP (Emerald), AXRP (Ruby), AXVP (Sapphire)
# Japan: BPEJ (Emerald), AXRJ (Ruby), AXVJ (Sapphire)
POKEMON_GAME_CODES = {
    'BPEE': 'emerald', 'BPEP': 'emerald', 'BPEJ': 'emerald',
    'AXRE': 'ruby', 'AXRP': 'ruby', 'AXRJ': 'ruby',
    'AXVE': 'sapphire', 'AXVP': 'sapphire', 'AXVJ': 'sapphire',
}


class PokemonTextDecoder:
    """Декодер текста Pokemon, совместимый с интерфейсом экстрактора"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        """Декодирование данных с использованием charmap Pokemon"""
        return _decode_pokemon_text_static(data[start:start + length], self.charmap)


def _decode_pokemon_text_static(data: bytes, charmap: dict[int, str]) -> str:
    """Decode Pokemon GBA text using the exact Pret pokeemerald charmap"""
    result: list[str] = []
    i = 0
    while i < len(data):
        byte = data[i]

        # FE = new line
        if byte == 0xFE:
            result.append('\n')
            i += 1
            continue

        # FF = end of string
        if byte == 0xFF:
            break

        # FA = scroll up window text
        if byte == 0xFA:
            result.append('\n')
            i += 1
            continue

        # FB = new paragraph
        if byte == 0xFB:
            result.append('\n\n')
            i += 1
            continue

        # F8 = button indicator (2 bytes: F8 XX)
        if byte == 0xF8:
            if i + 1 < len(data):
                btn = data[i + 1]
                btn_name = F8_BUTTONS.get(btn, f'BTN_{btn:02X}')
                if btn_name:
                    result.append(f'[{btn_name}]')
                i += 2
            else:
                i += 1
            continue

        # F9 = symbol (2 bytes: F9 XX)
        if byte == 0xF9:
            if i + 1 < len(data):
                sym = data[i + 1]
                sym_char = F9_SYMBOLS.get(sym, f'[SYM_{sym:02X}]')
                result.append(sym_char)
                i += 2
            else:
                i += 1
            continue

        # FD = string placeholder (2 bytes: FD XX)
        if byte == 0xFD:
            if i + 1 < len(data):
                subcmd = data[i + 1]
                placeholder = FD_SUBCOMMANDS.get(subcmd, f'[VAR_{subcmd:02X}]')
                result.append(f'{{{placeholder}}}')
                i += 2
            else:
                i += 1
            continue

        # FC = command prefix (variable length)
        if byte == 0xFC:
            if i + 1 < len(data):
                subcmd = data[i + 1]
                cmd_name = FC_COMMANDS.get(subcmd, f'FC_{subcmd:02X}')

                # FC 06 (FONT) takes an extra byte
                if subcmd == 0x06 and i + 2 < len(data):
                    font_id = data[i + 2]
                    font_name = FONT_CONSTANTS.get(font_id, f'FONT_{font_id:02X}')
                    result.append(f'[{font_name}]')
                    i += 3
                # FC 01/02/03 (COLOR/HIGHLIGHT/SHADOW) take an extra byte
                elif subcmd in (0x01, 0x02, 0x03) and i + 2 < len(data):
                    color_id = data[i + 2]
                    color_name = COLOR_CONSTANTS.get(color_id, f'COLOR_{color_id:02X}')
                    result.append(f'[{cmd_name}:{color_name}]')
                    i += 3
                # FC 04 (COLOR_HIGHLIGHT_SHADOW) takes 3 extra bytes
                elif subcmd == 0x04 and i + 4 < len(data):
                    c = data[i + 2]
                    h = data[i + 3]
                    s = data[i + 4]
                    result.append(f'[CHS:{c:02X}_{h:02X}_{s:02X}]')
                    i += 5
                else:
                    result.append(f'[{cmd_name}]')
                    i += 2
            else:
                i += 1
            continue

        # F7 = dynamic character
        if byte == 0xF7:
            result.append('[DYN]')
            i += 1
            continue

        # Regular character from charmap
        if byte in charmap:
            char = charmap[byte]
            # Skip special markers that shouldn't appear in output
            if char not in ('SUPER_ER', 'UNK_SPACER', 'PK', 'MN', 'LV'):
                result.append(char)
            i += 1
            continue

        # Unknown byte - show as hex
        result.append(f'[{byte:02X}]')
        i += 1

    return ''.join(result)


class PokemonGBAPlugin(GamePlugin):
    """Плагин для Pokémon GBA игр (Emerald/Ruby/Sapphire)"""

    def __init__(self):
        super().__init__()
        self._lz77_handler = GBALZ77Handler()
        self._decoder = PokemonTextDecoder(CHARMAP_POKEMON_GBA)

    @property
    def game_id_pattern(self) -> str:
        # Match specific Pokémon game codes
        codes = '|'.join(POKEMON_GAME_CODES.keys())
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов Pokémon GBA"""
        logger.info("Извлечение текстовых сегментов для Pokémon GBA")

        # Определяем версию игры по game_code
        game_code = rom.header.get('game_code', '')
        version = POKEMON_GAME_CODES.get(game_code, 'emerald')

        segments = []

        # Search for LZ77 compressed text blocks
        segments.extend(self._find_lz77_text_blocks(rom, version))

        # Also search for raw text blocks (uncompressed)
        segments.extend(self._find_raw_text_blocks(rom, version))

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def _find_lz77_text_blocks(self, rom: GameBoyROM, version: str) -> list[dict]:
        """Поиск LZ77-сжатых текстовых блоков"""
        segments: list[dict] = []

        # Scan for LZ77 signatures in text banks
        scan_ranges = [
            (0x580000, 0x600000),  # Known text bank area
            (0x1A0000, 0x270000),  # Additional text banks
        ]

        for range_start, range_end in scan_ranges:
            if range_start >= len(rom.data):
                continue

            end = min(range_end, len(rom.data))
            offset = range_start

            while offset < end - 4:
                # Look for LZ77 signature (0x10)
                if rom.data[offset] == 0x10:
                    # Try to decompress
                    result = self._decompress_lz77(rom.data, offset)
                    if result is not None:
                        decompressed, consumed = result
                        if len(decompressed) >= 20:
                            # Check if decompressed data contains text
                            if self._has_text_content(decompressed):
                                seg_name = f'pokemon_{version}_lz77_{len(segments)}'
                                segments.append({
                                    'name': seg_name,
                                    'start': offset,
                                    'end': offset + consumed,  # Exact compressed size
                                    'decoder': self._decoder,
                                    'compression': 'gba_lz77',
                                    'charmap': CHARMAP_POKEMON_GBA,
                                    'terminators': POKEMON_TERMINATORS,
                                })
                                logger.info(f"Found LZ77 text block at 0x{offset:X}: {len(decompressed)} bytes decompressed")
                                # Skip past this block
                                offset += consumed
                                continue
                offset += 1

        return segments

    def _find_raw_text_blocks(self, rom: GameBoyROM, version: str) -> list[dict]:
        """Поиск несжатых текстовых блоков"""
        segments: list[dict] = []
        min_text_length = 10

        # Known raw text locations (from our investigation)
        # These are uncompressed text banks in Pokemon GBA
        raw_text_locations = [
            (0x599000, 0x59A000),  # Phrase book / common phrases
            (0x5ED000, 0x5EF000),  # Menu/UI text
            (0x280000, 0x2C0000),  # Dialogue bank (high text density)
            (0x560000, 0x580000),  # Pokedex descriptions
        ]

        for start, end in raw_text_locations:
            if start >= len(rom.data):
                continue

            end = min(end, len(rom.data))
            block = rom.data[start:end]

            # Try to decode as raw text
            if self._has_text_content(block):
                strings = self._extract_strings_from_block(block)
                if strings and any(len(s) >= min_text_length for s in strings):
                    seg_name = f'pokemon_{version}_raw_{len(segments)}'
                    segments.append({
                        'name': seg_name,
                        'start': start,
                        'end': end,
                        'decoder': self._decoder,
                        'compression': None,
                        'charmap': CHARMAP_POKEMON_GBA,
                        'terminators': POKEMON_TERMINATORS,
                    })
                    logger.info(f"Found raw text block at 0x{start:X}: {len(strings)} strings")

        return segments

    def _has_text_content(self, data: bytes | bytearray) -> bool:
        """Проверка, содержит ли данные текст"""
        if len(data) < 20:
            return False

        text_bytes = 0
        total = min(len(data), 200)

        for b in data[:total]:
            # Count bytes that are likely text
            if 0xBB <= b <= 0xEE:  # A-Z, a-z
                text_bytes += 1
            elif 0x01 <= b <= 0x28:  # Accented characters
                text_bytes += 1
            elif 0xAB <= b <= 0xBA:  # Numbers, punctuation
                text_bytes += 1
            elif b == 0x00:  # Space
                text_bytes += 1
            # Note: 0xFF (terminator) not counted to reduce false positives

        ratio = text_bytes / total
        return ratio >= 0.4

    def _decompress_lz77(self, rom_data: bytearray | bytes, offset: int) -> tuple[bytes, int] | None:
        """Распаковка LZ77 блока по указанному адресу

        Returns:
            Tuple of (decompressed_data, consumed_bytes) or None on failure
        """
        try:
            if offset >= len(rom_data):
                return None
            if rom_data[offset] != 0x10:
                return None
            decompressed, consumed = self._lz77_handler.decompress(rom_data, offset)
            return decompressed, consumed
        except Exception as e:
            logger.debug(f"LZ77 decompression failed at 0x{offset:X}: {e}")
            return None

    def _extract_strings_from_block(self, data: bytes | bytearray) -> list[str]:
        """Извлечение строк из блока данных"""
        strings: list[str] = []
        current: list[str] = []
        for b in data:
            if b == 0xFF:
                if current:
                    strings.append(''.join(current))
                    current = []
            elif b == 0x00:
                current.append(' ')
            elif 0xBB <= b <= 0xEE:
                current.append(CHARMAP_POKEMON_GBA.get(b, '?'))
            elif 0x01 <= b <= 0x28:
                current.append(CHARMAP_POKEMON_GBA.get(b, '?'))
            elif 0xAB <= b <= 0xBA:
                current.append(CHARMAP_POKEMON_GBA.get(b, '?'))
            elif 0xF1 <= b <= 0xF6:
                current.append(CHARMAP_POKEMON_GBA.get(b, '?'))
            elif b == 0xFD:
                current.append('[STR]')
            elif b == 0xFC:
                current.append('[FC]')
            elif b == 0xF7:
                current.append('[DYN]')
            else:
                current.append(f'[{b:02X}]')
        if current:
            strings.append(''.join(current))
        return strings

    def _heuristic_scan(self, rom: GameBoyROM, version: str) -> list[dict]:
        """Эвристический поиск текстовых блоков Pokemon"""
        segments: list[dict] = []
        block_size = 16

        # Scan known dialogue banks for Pokemon GBA
        scan_ranges = [
            (0x1A0000, 0x270000),  # Dialogue banks
            (0x3D0000, 0x3F0000),  # Menu/UI
        ]

        for range_start, range_end in scan_ranges:
            if range_start >= len(rom.data):
                continue

            end = min(range_end, len(rom.data))
            i = range_start

            while i + block_size <= end:
                if self._is_pokemon_text(rom.data, i, block_size):
                    seg_end = min(i + 0x1000, end)
                    segments.append({
                        'name': f'pokemon_{version}_heuristic_{len(segments)}',
                        'start': i,
                        'end': seg_end,
                        'decoder': self._decode_pokemon_text,
                        'compression': None,
                        'charmap': CHARMAP_POKEMON_GBA,
                        'terminators': POKEMON_TERMINATORS,
                    })
                    i = seg_end
                else:
                    i += block_size

        return segments

    def _is_pokemon_text(self, data: bytes, offset: int, size: int) -> bool:
        """Проверка, является ли блок данных текстом Pokemon"""
        if offset + size > len(data):
            return False

        chunk = data[offset:offset + size]

        # Count valid Pokemon text bytes
        valid_count = 0
        total = 0
        has_terminator = False

        for b in chunk:
            total += 1
            # Valid: space (0x00), accented (0x01-0x28), symbols, letters (0xBB-0xEE)
            if b == 0x00:  # space
                valid_count += 1
            elif 0x01 <= b <= 0x28:  # accented characters
                valid_count += 1
            elif 0x2C <= b <= 0x36:  # symbols
                valid_count += 1
            elif 0x51 <= b <= 0x5D:  # more symbols
                valid_count += 1
            elif 0x68 <= b <= 0x7C:  # arrows, spacers
                valid_count += 1
            elif 0x84 <= b <= 0x86:  # superscripts
                valid_count += 1
            elif 0xA0 <= b <= 0xBA:  # numbers, punctuation
                valid_count += 1
            elif 0xBB <= b <= 0xEE:  # A-Z, a-z
                valid_count += 1
            elif 0xF1 <= b <= 0xF6:  # German umlauts
                valid_count += 1
            elif b == 0xFF:  # terminator
                has_terminator = True
                valid_count += 1
            elif b in (0xFD, 0xFC, 0xF7):  # control codes
                valid_count += 1

        if total == 0:
            return False

        ratio = valid_count / total
        # Need at least 50% valid bytes and preferably a terminator
        return ratio >= 0.5 and (has_terminator or ratio >= 0.7)

    def get_terminators(self, segment_name: str) -> list[int]:
        """Байт-терминаторы для Pokémon GBA"""
        return POKEMON_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        """Pokémon GBA не использует сжатие для основного текста"""
        return None
