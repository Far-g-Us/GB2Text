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
Plugin for Pokemon Gold/Silver/Crystal (Gen2) — GBC

game_id: GBC_POKEMON(GOLD|GLDAAUE|SILVER|SILAAUE|SLVAAXE|CRYSTAL) or
GBC_PMCRYSTAL(BYTE|BXTJ) (header titles "POKEMON GOLD"/"POKEMON_GLDAAUE"/
"POKEMON SILVER"/"POKEMON_SILAAUE"/"POKEMON_SLVAAXE"/"POKEMON CRYSTAL"/
"PM_CRYSTAL..BYTE"/"PM_CRYSTAL..BXTJ", platform GBC)

Verified against real ROMs in test_roms:
  - Gold   (title "POKEMON_GLDAAUE") — "Pokemon - Gold Version
            (USA, Europe) (SGB Enhanced).gbc"
  - Silver (title "POKEMON_SLVAAXE") — "Pokemon - Silver Version
            (USA, Europe) (SGB Enhanced).gbc"; table layout is byte-identical
            to Gold (same addresses, verified by decoding items/moves/monsters)
  - Crystal UE (title "PM_CRYSTAL\x00BYTE") — "Pokemon - Crystal Version
            (UE) (V1.1) [C][!].gbc"; all four tables live at different
            addresses than Gold (see below)
Crystal JP (title "PM_CRYSTAL\x00BXTJ", Pocket Monsters - Crystal Version
Japan T-En) is recognized (game_id/validate pass) but its text is encoded in
the Japanese charmap, which the framework does not ship yet — tables stay
unmapped and get_text_segments returns [] (stub).

Friend chains: the Gen2 charmap is IDENTICAL to Gen1 (verified by decoding
real ROM strings like "GOLDENROD CITY", "MASTER BALL", "POUND"):
letters 0x80-0x99 up, 0xA0-0xB9 low, 0x50 = '@' terminator, 0x7F = space,
0xE0/E3/E8 = ' / '-' / '.', 0xEF = ♂, 0xF5 = ♀, digits 0xF6-0xFF,
0x4A = '[PKMN]', 0x54 = '#' (POKé glyph). So the Gen1 charmap/decoders
(from plugins.gb_pokemon_gen1) are reused as-is, no duplicate table.

Tables (verified addresses, relative to this 2MB ROM):
  - Gold/Silver: ItemNames         variable, 0x50-terminated, 0x1B0000-0x1B0955
                 TrainerClassNames variable, 0x50-terminated, 0x1B0955-0x1B0B74
                 MonsterNames      fixed width 10 bytes/slot, 0x50 padding,
                                   0x1B0B74-0x1B1574 (256 slots)
                 MoveNames         variable, 0x50-terminated, 0x1B1574-0x1B1EE1
                                   (first move POUND, last move BEAT UP, 251 moves)
  - Crystal UE: ItemNames          variable, 0x50-terminated, 0x1C8000-0x1C8955
                 TrainerClassNames variable, 0x50-terminated, 0x2C1EF-0x2C41A
                 MonsterNames      fixed width 10 bytes/slot, 0x50 padding,
                                   0x53384-0x53D84 (256 slots)
                 MoveNames         variable, 0x50-terminated, 0x1C9F29-0x1CA896
                                   (251 moves, last BEAT UP)

This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging
from typing import ClassVar

from core.plugin import GamePlugin
from core.rom import GameBoyROM
from plugins.gb_pokemon_gen1 import (
    CHARMAP_GEN1,
    GEN1_TERMINATORS,
    Gen1FixedDecoder,
    Gen1TextDecoder,
)

logger = logging.getLogger('gb2text.plugins.pokemon_gsc')

# Title → text tables. Layouts verified against real ROMs (see module docstring):
# GLDAAUE/SLVAAXE share one layout; Crystal UE uses different addresses.
GSC_TABLES: dict[str, list[dict]] = {
    'POKEMON_GLDAAUE': [
        {'name': 'item_names', 'start': 0x1B0000, 'end': 0x1B0955},
        {'name': 'trainer_class_names', 'start': 0x1B0955, 'end': 0x1B0B74},
        {'name': 'monster_names', 'start': 0x1B0B74, 'end': 0x1B1574,
         'fixed_width': 10},
        {'name': 'move_names', 'start': 0x1B1574, 'end': 0x1B1EE1},
    ],
    'POKEMON_SLVAAXE': [
        {'name': 'item_names', 'start': 0x1B0000, 'end': 0x1B0955},
        {'name': 'trainer_class_names', 'start': 0x1B0955, 'end': 0x1B0B74},
        {'name': 'monster_names', 'start': 0x1B0B74, 'end': 0x1B1574,
         'fixed_width': 10},
        {'name': 'move_names', 'start': 0x1B1574, 'end': 0x1B1EE1},
    ],
    'POKEMON_SILAAUE': [
        {'name': 'item_names', 'start': 0x1B0000, 'end': 0x1B0955},
        {'name': 'trainer_class_names', 'start': 0x1B0955, 'end': 0x1B0B74},
        {'name': 'monster_names', 'start': 0x1B0B74, 'end': 0x1B1574,
         'fixed_width': 10},
        {'name': 'move_names', 'start': 0x1B1574, 'end': 0x1B1EE1},
    ],
    'PM_CRYSTAL\x00BYTE': [
        {'name': 'item_names', 'start': 0x1C8000, 'end': 0x1C8955},
        {'name': 'trainer_class_names', 'start': 0x2C1EF, 'end': 0x2C41A},
        {'name': 'monster_names', 'start': 0x53384, 'end': 0x53D84,
         'fixed_width': 10},
        {'name': 'move_names', 'start': 0x1C9F29, 'end': 0x1CA896},
    ],
}


class PokemonGSCPlugin(GamePlugin):
    """Plugin for Pokemon Gold/Silver/Crystal (Gen2, GBC)."""

    GSC_TITLES: ClassVar[set[str]] = {
        'POKEMON GOLD',
        'POKEMON SILVER',
        'POKEMON CRYSTAL',
        'POKEMON_GLDAAUE',
        'POKEMON_SILAAUE',
        'POKEMON_SLVAAXE',
        'PM_CRYSTAL\x00BYTE',
        'PM_CRYSTAL\x00BXTJ',
    }

    def __init__(self):
        super().__init__()
        self._decoder = Gen1TextDecoder(CHARMAP_GEN1)
        self._fixed_decoder = Gen1FixedDecoder(CHARMAP_GEN1)

    @property
    def game_id_pattern(self) -> str:
        return r'^GBC_(POKEMON(GOLD|GLDAAUE|SILVER|SILAAUE|SLVAAXE|CRYSTAL)|PMCRYSTAL(BYTE|BXTJ))$'

    def validate_rom(self, rom: GameBoyROM) -> bool:
        title = rom.header.get('title', '').upper().strip()
        return title in self.GSC_TITLES

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        title = rom.header.get('title', '')
        safe_title = title.upper().strip()

        tables = GSC_TABLES.get(safe_title)
        if tables is None:
            self._is_stub = True
            logger.info(
                f"Pokemon Gen2 '{safe_title}': table layout not implemented, "
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
                    'name': f'gen2_{table["name"]}',
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
                    'name': f'gen2_{table["name"]}',
                    'start': start,
                    'end': end,
                    'decoder': self._decoder,
                    'compression': None,
                    'charmap': CHARMAP_GEN1,
                    'terminators': GEN1_TERMINATORS,
                    'pad_byte': 0x50,
                }
            segments.append(seg)

        logger.info(f"Found {len(segments)} text segments for {safe_title}")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return list(GEN1_TERMINATORS)

    def get_compression_handler(self, segment_name: str):
        return None
