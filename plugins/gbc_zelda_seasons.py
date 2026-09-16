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
Plugin for The Legend of Zelda: Oracle of Seasons (GBC, US).

game_id: GBC_ZELDADINAZ7E (header title "ZELDA DIN AZ7E", platform GBC)

Extraction: full ~2800 null-terminated records across a text pool
(0x73382-0x84DDF), using a mini-dictionary (4 groups, 0-3) with
two-byte refs (0x02-0x05), bracket-style control tokens ([STOP],
[COL], [SPEED], etc.), and literal Unicode for accented Latin and
kanji characters.

Injection: verbatim copy of original bytes when the translation is unchanged
(byte-exact round-trip), dictionary recompression (greedy longest-match over
the 1024-slot mini-dictionary) for new translations; translations that exceed
their free_after window are skipped (skip_long=True). Extraction-complete
with full round-trip support.

NOTE: This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM
from plugins.zelda_oracle_common import OracleTextDecoder

logger = logging.getLogger('gb2text.plugins.oracle_of_seasons')

US_GAME_ID = r'^GBC_ZELDADINAZ7E$'


class OracleOfSeasonsPlugin(GamePlugin):
    """Plugin for The Legend of Zelda: Oracle of Seasons (GBC) - US.

    Full extraction + injection: verbatim byte-copy for unchanged strings,
    greedy dictionary recompression for new translations.
    """

    @property
    def game_id_pattern(self) -> str:
        return US_GAME_ID

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        if len(rom.data) < 0x100000:
            logger.info("Oracle of Seasons: ROM too small (%d bytes), "
                        "returning empty", len(rom.data))
            return []
        decoder = OracleTextDecoder()
        manifest = decoder.build_manifest(rom.data)
        if not manifest:
            return []
        segments = [{
            'name': 'oracle_seasons',
            'kind': 'pointer_dialogues',
            'start': manifest[0]['target'],
            'end': manifest[-1]['target'] + manifest[-1]['free_after'],
            'decoder': decoder,
            'pointer_encoder': decoder.encode_compressed,
            'compression': None,
            'terminator': b'\x00',
            'terminators': [0x00],
            'manifest': manifest,
            'max_decode_len': 65536,
        }]
        logger.info("Oracle of Seasons: %d records, text range 0x%X-0x%X",
                     len(manifest),
                     manifest[0]['target'],
                     manifest[-1]['target'] + manifest[-1]['free_after'])
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00]
