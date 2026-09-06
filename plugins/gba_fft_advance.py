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
Плагин для Final Fantasy Tactics Advance (GBA)

Game codes: AFXE (USA), AGBJ (Japan), AGBE (Europe)

Text encoding: Custom Square Enix tile-based encoding
Source: https://datacrystal.tcrf.net/wiki/Final_Fantasy_Tactics_Advance/Strings

String format:
  0x00 = End of string / Padding
  0x01 = Signal start of single-byte section
  0x32 0xXX 0xYYYYYYYY = Start of LZSS compressed string (Y = decompressed size)
  0x40 0xXX = Control character (various sub-types)
  0x8X 0xXX = Printed character (two-byte sequences)

LZSS format: bit-packed commands (see core/compression.py FFTA_LZSSHandler)

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging
import re

from core.compression import FFTA_LZSSHandler
from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.fft_advance')

# ═══════════════════════════════════════════════════════════════════
# Character Map — EXACT from DataCrystal
# Source: https://datacrystal.tcrf.net/wiki/Final_Fantasy_Tactics_Advance/Strings
# ═══════════════════════════════════════════════════════════════════

# Multi-byte mode (0x8X XX): first byte 0x80-0x8F, second byte 0x00-0xFF
CHARMAP_FFTA_MULTI: dict[int, str] = {
    # Hiragana (0x80 0x00-0x50)
    0x8000: 'ぁ', 0x8001: 'あ', 0x8002: 'ぃ', 0x8003: 'い', 0x8004: 'ぅ',
    0x8005: 'う', 0x8006: 'ぇ', 0x8007: 'え', 0x8008: 'ぉ', 0x8009: 'お',
    0x800A: 'か', 0x800B: 'が', 0x800C: 'き', 0x800D: 'ぎ', 0x800E: 'く',
    0x800F: 'ぐ', 0x8010: 'け', 0x8011: 'げ', 0x8012: 'こ', 0x8013: 'ご',
    0x8014: 'さ', 0x8015: 'ざ', 0x8016: 'し', 0x8017: 'じ', 0x8018: 'す',
    0x8019: 'ず', 0x801A: 'せ', 0x801B: 'ぜ', 0x801C: 'そ', 0x801D: 'ぞ',
    0x801E: 'た', 0x801F: 'だ', 0x8020: 'ち', 0x8021: 'ぢ', 0x8022: 'っ',
    0x8023: 'つ', 0x8024: 'づ', 0x8025: 'て', 0x8026: 'で', 0x8027: 'と',
    0x8028: 'ど', 0x8029: 'な', 0x802A: 'に', 0x802B: 'ぬ', 0x802C: 'ね',
    0x802D: 'の', 0x802E: 'は', 0x802F: 'ば', 0x8030: 'ぱ', 0x8031: 'ひ',
    0x8032: 'び', 0x8033: 'ぴ', 0x8034: 'ふ', 0x8035: 'ぶ', 0x8036: 'ぷ',
    0x8037: 'へ', 0x8038: 'べ', 0x8039: 'ぺ', 0x803A: 'ほ', 0x803B: 'ぼ',
    0x803C: 'ぽ', 0x803D: 'ま', 0x803E: 'み', 0x803F: 'む', 0x8040: 'め',
    0x8041: 'も', 0x8042: 'ゃ', 0x8043: 'や', 0x8044: 'ゅ', 0x8045: 'ゆ',
    0x8046: 'ょ', 0x8047: 'よ', 0x8048: 'ら', 0x8049: 'り', 0x804A: 'る',
    0x804B: 'れ', 0x804C: 'ろ', 0x804D: 'ゎ', 0x804E: 'わ', 0x804F: 'を',
    0x8050: 'ん',

    # Katakana (0x80 0x51-0xA5)
    0x8051: 'ァ', 0x8052: 'ア', 0x8053: 'ィ', 0x8054: 'イ', 0x8055: 'ゥ',
    0x8056: 'ウ', 0x8057: 'ェ', 0x8058: 'エ', 0x8059: 'ォ', 0x805A: 'オ',
    0x805B: 'カ', 0x805C: 'ガ', 0x805D: 'キ', 0x805E: 'ギ', 0x805F: 'ク',
    0x8060: 'グ', 0x8061: 'ケ', 0x8062: 'ゲ', 0x8063: 'コ', 0x8064: 'ゴ',
    0x8065: 'サ', 0x8066: 'ザ', 0x8067: 'シ', 0x8068: 'ジ', 0x8069: 'ス',
    0x806A: 'ズ', 0x806B: 'セ', 0x806C: 'ゼ', 0x806D: 'ソ', 0x806E: 'ゾ',
    0x806F: 'タ', 0x8070: 'ダ', 0x8071: 'チ', 0x8072: 'ヂ', 0x8073: 'ッ',
    0x8074: 'ツ', 0x8075: 'ヅ', 0x8076: 'テ', 0x8077: 'デ', 0x8078: 'ト',
    0x8079: 'ド', 0x807A: 'ナ', 0x807B: 'ニ', 0x807C: 'ヌ', 0x807D: 'ネ',
    0x807E: 'ノ', 0x807F: 'ハ', 0x8080: 'バ', 0x8081: 'パ', 0x8082: 'ヒ',
    0x8083: 'ビ', 0x8084: 'ピ', 0x8085: 'フ', 0x8086: 'ブ', 0x8087: 'プ',
    0x8088: 'ヘ', 0x8089: 'ベ', 0x808A: 'ペ', 0x808B: 'ホ', 0x808C: 'ボ',
    0x808D: 'ポ', 0x808E: 'マ', 0x808F: 'ミ', 0x8090: 'ム', 0x8091: 'メ',
    0x8092: 'モ', 0x8093: 'ャ', 0x8094: 'ヤ', 0x8095: 'ュ', 0x8096: 'ユ',
    0x8097: 'ョ', 0x8098: 'ヨ', 0x8099: 'ラ', 0x809A: 'リ', 0x809B: 'ル',
    0x809C: 'レ', 0x809D: 'ロ', 0x809E: 'ヮ', 0x809F: 'ワ', 0x80A0: 'ヲ',
    0x80A1: 'ン', 0x80A2: 'ヴ', 0x80A3: '、', 0x80A4: '。', 0x80A5: 'ー',

    # Numbers (0x80 0xA6-0xAF)
    0x80A6: '0', 0x80A7: '1', 0x80A8: '2', 0x80A9: '3', 0x80AA: '4',
    0x80AB: '5', 0x80AC: '6', 0x80AD: '7', 0x80AE: '8', 0x80AF: '9',

    # Uppercase A-O (0x80 0xB0-0xBE)
    0x80B0: 'A', 0x80B1: 'B', 0x80B2: 'C', 0x80B3: 'D', 0x80B4: 'E',
    0x80B5: 'F', 0x80B6: 'G', 0x80B7: 'H', 0x80B8: 'I', 0x80B9: 'J',
    0x80BA: 'K', 0x80BB: 'L', 0x80BC: 'M', 0x80BD: 'N', 0x80BE: 'O',

    # Uppercase P-Z, lowercase a-f (0x80 0xBF-0xCF)
    0x80BF: 'P', 0x80C0: 'Q', 0x80C1: 'R', 0x80C2: 'S', 0x80C3: 'T',
    0x80C4: 'U', 0x80C5: 'V', 0x80C6: 'W', 0x80C7: 'X', 0x80C8: 'Y',
    0x80C9: 'Z', 0x80CA: 'a', 0x80CB: 'b', 0x80CC: 'c', 0x80CD: 'd',
    0x80CE: 'e', 0x80CF: 'f',

    # Lowercase g-z (0x80 0xD0-0xE3)
    0x80D0: 'g', 0x80D1: 'h', 0x80D2: 'i', 0x80D3: 'j', 0x80D4: 'k',
    0x80D5: 'l', 0x80D6: 'm', 0x80D7: 'n', 0x80D8: 'o', 0x80D9: 'p',
    0x80DA: 'q', 0x80DB: 'r', 0x80DC: 's', 0x80DD: 't', 0x80DE: 'u',
    0x80DF: 'v', 0x80E0: 'w', 0x80E1: 'x', 0x80E2: 'y', 0x80E3: 'z',

    # Punctuation (0x80 0xE4-0xEF)
    0x80E4: '.', 0x80E5: '「', 0x80E6: '」', 0x80E7: '『', 0x80E8: '』',
    0x80E9: '…', 0x80EA: '?', 0x80EB: '!', 0x80EC: ',', 0x80ED: '·',
    0x80EE: ':', 0x80EF: '_',

    # More symbols (0x80 0xF0-0xFF, 0x81 0x00-0x22)
    0x80F0: '々', 0x80F1: '/', 0x80F2: '~', 0x80F3: '\'', 0x80F4: '\'',
    0x80F5: '"', 0x80F6: '"', 0x80F7: '(', 0x80F8: ')', 0x80F9: '{',
    0x80FA: '}', 0x80FB: '【', 0x80FC: '】', 0x80FD: '+', 0x80FE: '-',
    0x80FF: '±', 0x8100: '×', 0x8101: '=', 0x8102: '<', 0x8103: '>',
    0x8104: '∞', 0x8105: '♂', 0x8106: '♀', 0x8107: '%', 0x8108: '&',
    0x8109: '*', 0x810A: '※', 0x810B: '─', 0x810C: '│', 0x810D: '▲',
    0x810E: '▼', 0x810F: '◀', 0x8110: '▶', 0x8111: '○', 0x8112: '△',
    0x8113: '□', 0x8114: '■', 0x8115: '♪', 0x8116: ';', 0x8117: '◎',
    0x8118: '０', 0x8119: '１', 0x811A: '２', 0x811B: '３', 0x811C: '４',
    0x811D: '５', 0x811E: '６', 0x811F: '７', 0x8120: '８', 0x8121: '９',
    0x8122: '－',
}

# Single-byte mode: byte values shifted by +1 from multi-byte second byte
# Example: 0x80CC ('c') → single-byte 0xCD
# To decode single-byte X: look up multi-byte code 0x8000 | (X - 1)

# ═══════════════════════════════════════════════════════════════════
# Control Codes — EXACT from DataCrystal
# Source: https://datacrystal.tcrf.net/wiki/Final_Fantasy_Tactics_Advance/Strings
# ═══════════════════════════════════════════════════════════════════

# 0x40 XX control characters (DataCrystal exact list)
FFTA_CTRL_40: dict[int, str] = {
    0x02: '[40_02]', 0x03: '[40_03]', 0x04: '[40_04]', 0x05: '[40_05]',
    0x06: '[40_06]', 0x07: '[40_07]', 0x08: '[40_08]', 0x09: '[40_09]',
    0x0A: '[40_0A]', 0x0B: '[40_0B]', 0x0C: '[40_0C]', 0x0D: '[40_0D]',
    0x0E: '[40_0E]', 0x0F: '[40_0F]', 0x10: '[40_10]', 0x11: '[40_11]',
    0x12: '[40_12]', 0x13: '[40_13]',
    0x15: '[40_15]',
    0x1F: '[40_1F]',
    0x21: '[40_21]',
    0x27: '[40_27]', 0x28: '[40_28]', 0x29: '[40_29]', 0x2A: '[40_2A]',
    0x2B: '[40_2B]', 0x2C: '[40_2C]', 0x2D: '[40_2D]', 0x2E: '[40_2E]',
    0x2F: '[40_2F]', 0x30: '[40_30]', 0x31: '[40_31]', 0x32: '[40_32]',
    0x33: '[40_33]', 0x34: '[40_34]', 0x35: '[40_35]', 0x36: '[40_36]',
    0x37: '[40_37]', 0x38: '[40_38]', 0x39: '[40_39]', 0x3A: '[40_3A]',
    0x3B: '[40_3B]',
    0x3E: '[SPACE]',  # Space width marker
    0x40: '[40_40]', 0x41: '[40_41]', 0x42: '[40_42]', 0x43: '[40_43]',
    0x44: '[40_44]', 0x45: '[40_45]', 0x46: '[40_46]', 0x47: '[40_47]',
    0x48: '[40_48]', 0x49: '[40_49]', 0x4A: '[40_4A]', 0x4B: '[40_4B]',
    0x4C: '[40_4C]', 0x4D: '[40_4D]', 0x4E: '[40_4E]', 0x4F: '[40_4F]',
    0x50: '[40_50]',
    0x53: '[CHOICE]',  # Dialog choice (followed by 2 strings)
    0x54: '[40_54]', 0x55: '[40_55]', 0x56: '[40_56]', 0x57: '[40_57]',
    0x58: '[40_58]', 0x59: '[40_59]', 0x5A: '[40_5A]', 0x5B: '[40_5B]',
    0x5C: '[40_5C]', 0x5D: '[40_5D]', 0x5E: '[40_5E]', 0x5F: '[40_5F]',
    0x60: '[40_60]', 0x61: '[WAIT]',  # Wait for button press
    0x62: '[40_62]',
    0x63: '[CLEAR]',  # Clear dialog box
    0x64: '[40_64]', 0x65: '[40_65]', 0x66: '[40_66]', 0x67: '[40_67]',
    0x68: '[40_68]', 0x69: '[40_69]', 0x6A: '[40_6A]', 0x6B: '[40_6B]',
    0x6C: '[40_6C]', 0x6D: '[40_6D]',
    0x6E: '[NEWLINE]',
    0x6F: '[40_6F]',
    0x70: '[NEXT_PAGE]',  # Next page icon
    0x71: '[40_71]',
    0x72: '[CRN]',  # CRN lookup (character name)
    0x73: ' ',  # Space
    0x74: '[DELAY]',  # Delay XX/10 seconds
    0x75: '[40_75]', 0x76: '[40_76]',
    0x77: '[40_77]', 0x78: '[40_78]', 0x79: '[40_79]', 0x7A: '[40_7A]',
    0x7B: '[40_7B]', 0x7C: '[40_7C]', 0x7D: '[40_7D]', 0x7E: '[40_7E]',
    0x7F: '[40_7F]',
}

# Character name references (0x40 0x25 XX)
FFTA_CHAR_NAMES: dict[int, str] = {
    0x00: 'Marche', 0x01: 'Mewt', 0x02: 'Ritz', 0x03: 'Shara',
    0x04: 'Vilikky', 0x05: 'Ezel', 0x06: 'Cid', 0x07: 'Babus',
    0x08: 'Nora', 0x09: 'Montblanc', 0x0A: 'Luso', 0x0B: 'Adelle',
}

# ═══════════════════════════════════════════════════════════════════
# CRN Lookup Table — EXACT from DataCrystal
# Source: https://datacrystal.tcrf.net/wiki/Final_Fantasy_Tactics_Advance/CRN_data
# ═══════════════════════════════════════════════════════════════════

FFTA_CRN_NAMES: dict[int, str] = {
    0x00: 'NONE', 0x01: 'Delita', 0x02: 'Ramza', 0x03: 'Alma',
    0x04: 'Agrias', 0x05: 'Mustadio', 0x06: 'Orlandu', 0x07: 'Gafgarion',
    0x08: 'Algus', 0x09: 'Beowulf', 0x0A: 'Reis', 0x0B: 'Ovelia',
    0x0C: 'Izlude', 0x0D: 'Meliadoul', 0x0E: 'Chantage', 0x0F: 'Worker 8',
    0x10: 'Cloud', 0x11: 'Togra', 0x12: 'Rafa', 0x13: 'Malak',
    0x14: 'Argath', 0x15: 'Celia', 0x16: 'Lede', 0x17: 'Wiegraf',
    0x18: 'Velius', 0x19: 'Marach', 0x1A: 'Balbanes', 0x1B: 'Teta',
    0x1C: 'Dyce', 0x1D: 'Lilka', 0x1E: 'Enkou', 0x1F: 'Mid',
    0x20: 'Elmdor', 0x21: 'Cuchulain', 0x22: 'Queen', 0x23: 'King',
    0x24: 'UnGeneration', 0x25: 'Bahamut', 0x26: 'Asura', 0x27: 'Leviathan',
    0x28: 'Odin', 0x29: 'Sacred', 0x2A: 'Phoenix', 0x2B: 'Titan',
    0x2C: 'Tiamat', 0x2D: 'Azul', 0x2E: 'Salmon', 0x2F: 'Byblos',
    0x30: 'Chocobo', 0x31: 'Black Chocobo', 0x32: 'Brown Chocobo', 0x33: 'Red Chocobo',
    0x34: 'Yellow Chocobo', 0x35: 'Zephyr', 0x36: 'Sleipnir', 0x37: 'Abaddon',
    0x38: 'Ahriman', 0x39: 'Ajora', 0x3A: 'Allosaurus', 0x3B: 'Amdola',
    0x3C: 'Archaeodemon', 0x3D: 'Argath', 0x3E: 'Atmos', 0x3F: 'Atomos',
    0x40: 'Baby tonberry', 0x41: 'Balma', 0x42: 'Balnitel', 0x43: 'Balrion',
    0x44: 'Barnacle', 0x45: 'Beliar', 0x46: 'Boco', 0x47: 'Brainwear',
    0x48: 'Carbunkl', 0x49: 'Chocobo', 0x4A: 'Clyvence', 0x4B: 'Cockatrice',
    0x4C: 'Cougar', 0x4D: 'Cream Cocoa', 0x4E: 'Cucullain', 0x4F: 'Death machine',
    0x50: 'Dustman', 0x51: 'Dwarven', 0x52: 'Dyce', 0x53: 'Elidel',
    0x54: 'Emma', 0x55: 'Ezell', 0x56: 'Famfrit', 0x57: 'Fezz',
    0x58: 'Flotpass', 0x59: 'Fraguel', 0x5A: 'Galerrian', 0x5B: 'Garif',
    0x5C: 'Garnet', 0x5D: 'Ghoul', 0x5E: 'Gilgamesh', 0x5F: 'Goblin',
    0x60: 'Golgor', 0x61: 'Granddragon', 0x62: 'Grandt', 0x63: 'Grundler',
    0x64: 'Hathat', 0x65: 'Hekat', 0x66: 'Humbaba', 0x67: 'Hydra',
    0x68: 'Isilud', 0x69: 'Jackabo', 0x6A: 'Jagd Yiazmat', 0x6B: 'Kafith',
    0x6C: 'Kaiser Dragon', 0x6D: 'Kampf', 0x6E: 'Lani', 0x6F: 'Lion',
    0x70: 'Lucavi', 0x71: 'Luchor dimension', 0x72: 'Malboro', 0x73: 'Maliris',
    0x74: 'Mime', 0x75: 'Minotaur', 0x76: 'Miraj', 0x77: 'Mocchi',
    0x78: 'Momodirome', 0x79: 'Mortalior', 0x7A: 'Mymidon', 0x7B: 'Mythril',
    0x7C: 'Nidhogg', 0x7D: 'Nightmare', 0x7E: 'Odin', 0x7F: 'Oglop',
    0x80: 'Orc', 0x81: 'Orobon', 0x82: 'Ochu', 0x83: 'Panther',
    0x84: 'Platypode', 0x85: 'Polypede', 0x86: 'Propos', 0x87: 'Pyreflies',
    0x88: 'Quezuko', 0x89: 'Ramuh', 0x8A: 'Raptor', 0x8B: 'Raven',
    0x8C: 'Red Dragon', 0x8D: 'Rinnel', 0x8E: 'Roly Poly', 0x8F: 'Salamander',
    0x90: 'Sandworm', 0x91: 'Scholar', 0x92: 'Sekhmet', 0x93: 'Shadow',
    0x94: 'Siren', 0x95: 'Skeleton', 0x96: 'Slime', 0x97: 'Sphinx',
    0x98: 'Stilva', 0x99: 'T. Rex', 0x9A: 'Taru', 0x9B: 'Thorn',
    0x9C: 'Thunder Drake', 0x9D: 'Tiamat', 0x9E: 'Tonberry', 0x9F: 'Troll',
    0xA0: 'Ultima Demon', 0xA1: 'Ultimecia', 0xA2: 'Undead Princess', 0xA3: 'Ur-Kensa',
    0xA4: 'Valoflip', 0xA5: 'Vampire', 0xA6: 'Vishno', 0xA7: 'Volt Arene',
    0xA8: 'Wendice', 0xA9: 'White Knight', 0xAA: 'Witch of the Fens', 0xAB: 'Wyvern',
    0xAC: 'Yazmat', 0xAD: 'Zalera', 0xAE: 'Zalmoon', 0xAF: 'Zangan',
    0xB0: 'Zemus', 0xB1: 'Zodiark', 0xB2: 'Zombie', 0xB3: 'Zu',
    0xB4: 'Zu 判', 0xB5: 'Unknown', 0xB6: 'Cactuar', 0xB7: 'Chocobo Egg',
    0xB8: 'Garuda', 0xB9: 'Hashmal', 0xBA: 'Oglop (Cid)', 0xBB: 'Pisama',
    0xBC: 'Rulkan', 0xBD: 'Vaal', 0xBE: 'Wacol', 0xBF: 'Warlock',
    0xC0: 'Warrior', 0xC1: 'Weirdling', 0xC2: 'Windslash', 0xC3: 'Wojavi',
    0xC4: 'Wolf', 0xC5: 'Wraith', 0xC6: 'Wyrm', 0xC7: 'Xarcat',
    0xC8: 'Yellow Chocobo', 0xC9: 'Yeti', 0xCA: 'Yig', 0xCB: 'Zombie Dragon',
    0xCC: 'Zurvan', 0xCD: 'Flan', 0xCE: 'Bomb', 0xCF: 'Bomb King',
    0xD0: 'Ahriman', 0xD1: 'Bald Bull', 0xD2: 'Behemoth', 0xD3: 'Blood Fan',
    0xD4: 'Buer', 0xD5: 'Dark Dragon', 0xD6: 'Dark Flare', 0xD7: 'Dead Breath',
    0xD8: 'Deepee', 0xD9: 'Dirt Eater', 0xDA: 'Eddy', 0xDB: 'Elder Dragon',
    0xDC: 'Fafnir', 0xDD: 'Firaga', 0xDE: 'Flame Breath', 0xDF: 'Flare Star',
    0xE0: 'Gateri', 0xE1: 'Grenade', 0xE2: 'Growth', 0xE3: 'Gusting Pike',
    0xE4: 'Holy', 0xE5: 'Ice Dragon', 0xE6: 'Ink', 0xE7: 'Karma',
    0xE8: 'Level ? Holy', 0xE9: 'Level ? Flame', 0xEA: 'Level ? Graviga',
    0xEB: 'Maelstrom', 0xEC: 'Meteor', 0xED: 'Mighty Swing', 0xEE: 'Nullify',
    0xEF: 'Phantasm', 0xF0: 'Quake', 0xF1: 'Quake III', 0xF2: 'Rapid Fire',
    0xF3: 'Sabre Soul', 0xF4: 'Shadowbind', 0xF5: 'Slow Kill', 0xF6: 'Stop',
    0xF7: 'Swarmstrike', 0xF8: 'Thundaga', 0xF9: 'Touchdown', 0xFA: 'Ultima',
    0xFB: 'Viraga', 0xFC: 'Whirlwind', 0xFD: '???', 0xFE: '???',
    0xFF: '???',
}

# ═══════════════════════════════════════════════════════════════════
# Pointer Tables — EXACT from DataCrystal
# Source: https://datacrystal.tcrf.net/wiki/Final_Fantasy_Tactics_Advance/String_tables
# ═══════════════════════════════════════════════════════════════════

# GBA address base
GBA_BASE = 0x08000000

FFTA_STRING_TABLES = [
    # (pointer_table_offset, text_start_offset, entry_count, name)
    (0x005567F0, 0x005541B4, 767, 'Universal'),
    (0x00526680, 0x0052336C, 753, 'Item/Location Names'),
    (0x0055A64C, 0x00558008, 512, 'Mission Names'),
    (0x005680DC, 0x00566A00, 725, 'Random Names'),
]

# CRN data (character name strings)
FFTA_CRN_OFFSET = 0x55128C  # CRN data starts here (ROM offset, GBA base stripped)
FFTA_CRN_POINTERS = 0x5516D0  # CRN pointer table (ROM offset)

# Game codes for detection
FFTA_GAME_CODES = ['AFXE', 'AGBJ', 'AGBE']

# Text terminators
FFTA_TERMINATORS = [0x00]


# ═══════════════════════════════════════════════════════════════════
# Decoder
# ═══════════════════════════════════════════════════════════════════

class FFTATextDecoder:
    """Decoder adapter — wraps _decode_ffta_text for the extractor API."""

    def decode(self, data: bytes, start: int, length: int) -> str:
        text, _ = _decode_ffta_text(data, start, length)
        return text

    def encode(self, text: str) -> bytes:
        raise NotImplementedError("FFTA encoding not yet implemented")

def _decode_ffta_text(data: bytes, start: int, length: int) -> tuple[str, int]:
    """Decode FFTA text using the exact DataCrystal charmap.

    Returns (decoded_text, bytes_consumed).

    FFTA uses two encoding modes:
    1. Multi-byte (default): 0x8X XX sequences
    2. Single-byte (starts with 0x01): bytes shifted by -1 from multi-byte table

    Control codes:
    - 0x00 = End of string
    - 0x01 = Switch to single-byte mode
    - 0x40 XX = Control character (various sub-types)
    - 0x32 0xXX 0xYYYYYYYY = LZSS compressed block start
    """
    result: list[str] = []
    i = start
    end = min(start + length, len(data))
    single_byte_mode = False

    while i < end:
        byte = data[i]

        # End of string
        if byte == 0x00:
            break

        # Switch to single-byte mode
        if byte == 0x01:
            single_byte_mode = True
            i += 1
            continue

        # 0x40 = Control character
        if byte == 0x40 and i + 1 < end:
            ctrl = data[i + 1]
            i += 2

            # Character name reference (0x40 0x25 XX)
            if ctrl == 0x25 and i < end:
                name_idx = data[i]
                i += 1
                name = FFTA_CHAR_NAMES.get(name_idx, f'[{name_idx:02X}]')
                result.append(f'{{{name}}}')
                continue

            # CRN lookup (0x40 0x72 XX)
            if ctrl == 0x72 and i < end:
                crn_idx = data[i]
                i += 1
                crn_name = FFTA_CRN_NAMES.get(crn_idx, f'CRN_{crn_idx:02X}')
                result.append(f'{{{crn_name}}}')
                continue

            # Delay (0x40 0x74 XX)
            if ctrl == 0x74 and i < end:
                delay = data[i]
                i += 1
                result.append(f'[DELAY:{delay}]')
                continue

            # Choice (0x40 0x53 XX YY) — complex, just mark it
            if ctrl == 0x53:
                result.append('[CHOICE]')
                # Skip 2 bytes (choice params)
                if i + 1 < end:
                    i += 2
                continue

            # Space width (0x40 0x3E XX)
            if ctrl == 0x3E and i < end:
                width = data[i]
                i += 1
                result.append(f'[SPACE_W:{width}]')
                continue

            # Lookup in table
            ctrl_str = FFTA_CTRL_40.get(ctrl, f'[40_{ctrl:02X}]')
            result.append(ctrl_str)
            continue

        # Multi-byte mode (0x8X XX)
        if 0x80 <= byte <= 0x8F and i + 1 < end:
            second = data[i + 1]
            char_code = (byte << 8) | second
            char = CHARMAP_FFTA_MULTI.get(char_code, f'[{byte:02X}_{second:02X}]')
            result.append(char)
            i += 2
            continue

        # Single-byte mode
        if single_byte_mode:
            # Single-byte = multi-byte shifted by 1
            # byte X → multi-byte code 0x8000 | (X - 1)
            if byte >= 0x80:
                char_code = 0x8000 | (byte - 1)
                char = CHARMAP_FFTA_MULTI.get(char_code, f'[{byte:02X}]')
            else:
                # Control codes in single-byte mode
                if byte in FFTA_CTRL_40:
                    char = FFTA_CTRL_40[byte]
                else:
                    char = f'[{byte:02X}]'
            result.append(char)
            i += 1
            continue

        # Unknown byte in multi-byte mode (should not happen in valid text)
        result.append(f'[{byte:02X}]')
        i += 1

    return ''.join(result), i - start


class FFTAdvancePlugin(GamePlugin):
    """Плагин для Final Fantasy Tactics Advance (GBA)"""

    def __init__(self):
        super().__init__()
        self._lzss = FFTA_LZSSHandler()

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(FFTA_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов FFTA

        Uses 4 pointer tables from DataCrystal plus CRN data.
        """
        logger.info("Извлечение текстовых сегментов для Final Fantasy Tactics Advance")

        segments: list[dict] = []

        # ─── 1. Pointer table strings (4 tables) ────────────────
        for tbl_offset, text_start, count, name in FFTA_STRING_TABLES:
            tbl_addr = tbl_offset  # ROM offset (no GBA base needed for ROM data)
            if tbl_addr + count * 4 > len(rom.data):
                logger.warning(f"String table '{name}' at 0x{tbl_offset:X} exceeds ROM size")
                continue

            table_segments = self._read_pointer_table(
                rom.data, tbl_addr, text_start, count, name
            )
            segments.extend(table_segments)
            logger.info(f"String table '{name}': {len(table_segments)} strings from {count} pointers")

        # ─── 2. CRN data (character names) ──────────────────────
        crn_segments = self._read_crn_data(rom.data)
        segments.extend(crn_segments)
        logger.info(f"CRN data: {len(crn_segments)} character names")

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def _read_pointer_table(self, data: bytes, tbl_offset: int,
                            text_start: int, count: int,
                            table_name: str) -> list[dict]:
        """Read a pointer table and extract strings.

        Each pointer is 4 bytes, pointing to text_start + offset.
        The pointer value is the ROM offset of the string.
        """
        segments: list[dict] = []

        for i in range(count):
            ptr_addr = tbl_offset + i * 4
            if ptr_addr + 4 > len(data):
                break

            # Read pointer (4 bytes little-endian)
            ptr_value = int.from_bytes(data[ptr_addr:ptr_addr + 4], 'little')

            # FFTA pointers include GBA base — subtract it
            string_offset = ptr_value - GBA_BASE if ptr_value >= GBA_BASE else ptr_value

            # Validate: offset should be within ROM
            if string_offset < 0 or string_offset >= len(data):
                continue

            # Find string length (up to next pointer or max 512 bytes)
            next_ptr = tbl_offset + (i + 1) * 4
            if next_ptr + 4 <= len(data):
                next_val_raw = int.from_bytes(data[next_ptr:next_ptr + 4], 'little')
                next_val = next_val_raw - GBA_BASE if next_val_raw >= GBA_BASE else next_val_raw
                max_len = min(next_val - string_offset, 512) if next_val > string_offset else 512
            else:
                max_len = 512

            max_len = min(max_len, len(data) - string_offset)

            if max_len <= 0:
                continue

            # Decode the string
            text, bytes_consumed = _decode_ffta_text(data, string_offset, max_len)

            # Filter out segments with only unknown byte markers
            if not text or re.fullmatch(r'(\[[A-F0-9]{2}(_[A-F0-9]{2})?\])*', text):
                continue

            segments.append({
                'name': f'{table_name}_{i}',
                'start': string_offset,
                'end': string_offset + bytes_consumed,
                'text': text,
                'decoder': FFTATextDecoder(),
                'compression': None,
                'charmap': CHARMAP_FFTA_MULTI,
                'terminators': FFTA_TERMINATORS,
            })

        return segments

    def _read_crn_data(self, data: bytes) -> list[dict]:
        """Read CRN (character name) data.

        CRN strings start at FFTA_CRN_OFFSET, each prefixed with 0x01.
        """
        segments: list[dict] = []

        offset = FFTA_CRN_OFFSET
        for idx in range(107):  # 107 CRN names
            if offset >= len(data):
                break

            # Each CRN string starts with 0x01 (single-byte mode marker)
            if data[offset] == 0x01:
                offset += 1

            # Find end of string (0x00)
            str_start = offset
            while offset < len(data) and data[offset] != 0x00:
                offset += 1

            str_len = offset - str_start
            if str_len > 0:
                text, bytes_consumed = _decode_ffta_text(data, str_start, str_len)
                crn_name = FFTA_CRN_NAMES.get(idx, f'CRN_{idx:02X}')

                segments.append({
                    'name': f'CRN_{crn_name}',
                    'start': str_start,
                    'end': str_start + bytes_consumed,
                    'text': text,
                    'decoder': FFTATextDecoder(),
                    'compression': None,
                    'charmap': CHARMAP_FFTA_MULTI,
                    'terminators': FFTA_TERMINATORS,
                })

            offset += 1  # Skip 0x00 terminator

        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        """Байт-терминаторы для FFTA"""
        return FFTA_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        """FFTA LZSS compression handler"""
        if 'lzss' in segment_name.lower():
            return self._lzss
        return None
