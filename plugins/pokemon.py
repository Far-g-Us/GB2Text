"""
Плагин для игр Pokémon
"""

from core.plugin import GamePlugin
from core.decoder import CharMapDecoder


class PokemonPlugin(GamePlugin):
    """Плагин для игр Pokémon"""

    @property
    def game_id_pattern(self) -> str:
        return r'^POKEMON_.*$'

    def get_text_segments(self, rom) -> list:
        # Полная таблица символов для Pokémon
        charmap = {
            0x80: 'A', 0x81: 'B', 0x82: 'C', 0x83: 'D', 0x84: 'E',
            0x85: 'F', 0x86: 'G', 0x87: 'H', 0x88: 'I', 0x89: 'J',
            0x8A: 'K', 0x8B: 'L', 0x8C: 'M', 0x8D: 'N', 0x8E: 'O',
            0x8F: 'P', 0x90: 'Q', 0x91: 'R', 0x92: 'S', 0x93: 'T',
            0x94: 'U', 0x95: 'V', 0x96: 'W', 0x97: 'X', 0x98: 'Y',
            0x99: 'Z',
            0x9A: 'à', 0x9B: 'é', 0x9C: 'è', 0x9D: 'ù',
            0x9E: 'â', 0x9F: 'ê', 0xA0: 'î', 0xA1: 'ô', 0xA2: 'û',
            0xA3: 'ç', 0xA4: 'À', 0xA5: 'É', 0xA6: 'È', 0xA7: 'Ù',
            0xA8: 'Â', 0xA9: 'Ê', 0xAA: 'Î', 0xAB: 'Ô', 0xAC: 'Û',
            0xAD: 'Ç',
            0xAE: 'ï', 0xAF: 'Ï', 0xB0: 'ë', 0xB1: 'Ë', 0xB2: 'ü',
            0xB3: 'Ü', 0xB4: 'æ', 0xB5: 'Æ', 0xB6: 'œ', 0xB7: 'Œ',
            0xB8: '°', 0xB9: '%', 0xBA: '#', 0xBB: '@', 0xBC: '&',
            0xBD: '+', 0xBE: '-', 0xBF: '*',
            0xC0: '/', 0xC1: ',', 0xC2: '.', 0xC3: '!', 0xC4: '?',
            0xC5: '(', 0xC6: ')', 0xC7: ':', 0xC8: ';', 0xC9: "'",
            0xCA: '"', 0xCB: '$', 0xCC: '=', 0xCD: '<', 0xCE: '>',
            0xCF: '[',
            0xD0: ']', 0xD1: '{', 0xD2: '}', 0xD3: '\\', 0xD4: '|',
            0xD5: '^', 0xD6: '_', 0xD7: '`', 0xD8: '~', 0xD9: '♂',
            0xDA: '♀', 0xDB: '×', 0xDC: '÷', 0xDD: '·', 0xDE: '·',
            0xDF: '…',
            0xE0: 'é', 0xE1: 'PK', 0xE2: 'MN', 0xE3: '-', 0xE4: "'d",
            0xE5: "'l", 0xE6: "'r", 0xE7: "'s", 0xE8: "'t", 0xE9: "'v",
            0xEA: "→", 0xEB: "⇒", 0xEC: "▼", 0xED: "♂", 0xEE: "♀",
            0xEF: "!"
        }

        return [
            {
                'name': 'dialogues',
                'start': 0x4000,
                'end': 0x7FFF,
                'decoder': CharMapDecoder(charmap),
                'compression': None,
                'terminator': [0x00]
            },
            {
                'name': 'pokemon_names',
                'start': 0xD000,
                'end': 0xD300,
                'decoder': CharMapDecoder(charmap),
                'compression': None,
                'terminator': [0x50]  # END_TEXT
            }
        ]