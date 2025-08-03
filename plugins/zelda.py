"""
Плагин для игр The Legend of Zelda
"""

from core.plugin import GamePlugin
from core.decoder import CharMapDecoder, LZ77Handler


class ZeldaPlugin(GamePlugin):
    """Плагин для The Legend of Zelda"""

    @property
    def game_id_pattern(self) -> str:
        return r'^ZELDA_.*$'

    def get_text_segments(self, rom) -> list:
        # Таблица символов для Zelda
        charmap = {
            0x00: 'A', 0x01: 'B', 0x02: 'C', 0x03: 'D',
            0x20: ' ', 0xFF: '[END]'
        }

        return [
            {
                'name': 'main_text',
                'start': 0x5000,
                'end': 0x7000,
                'decoder': CharMapDecoder(charmap),
                'compression': LZ77Handler()
            }
        ]