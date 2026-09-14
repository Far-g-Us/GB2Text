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
Plugin for Sonic Advance (GBA)

Game codes: ASOE (Sonic Advance USA), A2NE (Sonic Advance 2)

Text encoding: ASCII
Source: ROM analysis (credits, zone names, music credits)

Text format: ASCII lines with a length prefix
- Byte 0: string length
- Byte 1: 0x00
- Bytes 2+: ASCII text

NOTE: This plugin contains ONLY factual technical information.
Dialogs and story content protected by copyright are not included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM

logger = logging.getLogger('gb2text.plugins.sonic_advance')

# Sonic Advance uses standard ASCII encoding
CHARMAP_SONIC: dict[int, str] = {i: chr(i) for i in range(0x20, 0x7F)}

# Text terminators
SONIC_TERMINATORS = [0x00]

# Game codes for game detection
SONIC_GAME_CODES = ['ASOE', 'A2NE']

# Sonic Advance 2 (A2NE): the text engine differs from SA1, the structure
# is not implemented. The plugin detects the game but returns an empty list.
SONIC_STUB_CODES = {'A2NE'}


class SonicTextDecoder:
    """Sonic Advance text decoder (ASCII)"""

    def __init__(self, charmap: dict[int, str]):
        self.charmap = charmap

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            if byte in SONIC_TERMINATORS:
                break

            if byte in self.charmap:
                result.append(self.charmap[byte])
            elif 0x20 <= byte <= 0x7E:
                result.append(chr(byte))
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class SonicAdvancePlugin(GamePlugin):
    """Plugin for Sonic Advance (GBA)"""

    def __init__(self):
        super().__init__()
        self._decoder = SonicTextDecoder(CHARMAP_SONIC)
        self._game_code = ''

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(SONIC_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Extract Sonic Advance text segments"""
        logger.info("Извлечение текстовых сегментов для Sonic Advance")

        game_code = rom.header.get('game_code', '')
        self._game_code = game_code
        self._is_stub = game_code in SONIC_STUB_CODES

        if game_code in SONIC_STUB_CODES:
            logger.info(
                f"Sonic {game_code} (Advance 2): структура текста "
                f"не реализована, возвращаю пустой список"
            )
            return []

        segments: list[dict] = []

        # Credits text at 0x682000-0x683000 (confirmed by ROM analysis)
        # Format: ASCII lines with a length prefix
        credits_start = 0x682000
        credits_end = 0x683000

        if credits_end <= len(rom.data):
            segments.append({
                'name': 'sonic_credits',
                'start': credits_start,
                'end': credits_end,
                'decoder': self._decoder,
                'compression': None,
                'charmap': CHARMAP_SONIC,
                'terminators': SONIC_TERMINATORS,
            })
            logger.info(f"Found credits block at 0x{credits_start:X}-0x{credits_end:X}")

        # Scan additional text blocks heuristically
        # Search for ASCII lines with a length prefix
        scan_ranges = [
            (0x080000, 0x0C0000),  # Code/data area
            (0x600000, 0x700000),  # Data area
        ]

        for range_start, range_end in scan_ranges:
            if range_start >= len(rom.data):
                continue

            end = min(range_end, len(rom.data))
            i = range_start

            while i + 10 < end:
                # Check the line with a length prefix
                str_len = rom.data[i]
                if 3 <= str_len <= 100:
                    # Check whether the following bytes are ASCII
                    has_ascii = False
                    for j in range(1, min(str_len + 1, 20)):
                        if i + j < end:
                            b = rom.data[i + j]
                            if 0x20 <= b <= 0x7E:
                                has_ascii = True
                            else:
                                has_ascii = False
                                break

                    if has_ascii and str_len >= 5:
                        # A text string was found
                        seg_end = min(i + str_len + 2, end)
                        segments.append({
                            'name': f'sonic_text_{len(segments)}',
                            'start': i,
                            'end': seg_end,
                            'decoder': self._decoder,
                            'compression': None,
                            'charmap': CHARMAP_SONIC,
                            'terminators': SONIC_TERMINATORS,
                        })
                        i = seg_end
                    else:
                        i += 1
                else:
                    i += 1

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return SONIC_TERMINATORS

    def get_compression_handler(self, segment_name: str):
        return None
