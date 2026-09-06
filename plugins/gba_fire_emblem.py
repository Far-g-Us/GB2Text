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
Плагин для Fire Emblem GBA (FE7/FE8)

Game codes: BE7E/BE7J (FE7), BE8E/BE8J (FE8)

Text encoding: Standard ASCII + FE control codes + Huffman compression
Source: FEBuilderGBA source code (laqieer/FEBuilderGBA)

NOTE: This plugin contains ONLY factual technical information.
No copyrighted dialogue or story content is included.
"""

import logging

from core.plugin import GamePlugin
from core.rom import GameBoyROM
from core.compression import HuffmanHandler

logger = logging.getLogger('gb2text.plugins.fire_emblem_gba')

# Fire Emblem GBA control codes (from TextEscape.cs)
FE_CONTROL_CODES: dict[int, str] = {
    0x00: '[END]',
    0x01: '[NL]',
    0x02: '[Clear]',
    0x03: '[A]',
    0x04: '[....]',
    0x05: '[.....]',
    0x06: '[......]',
    0x07: '[.......]',
    0x08: '[FarLeft]',
    0x09: '[MidLeft]',
    0x0A: '[Left]',
    0x0B: '[Right]',
    0x0C: '[MidRight]',
    0x0D: '[FarRight]',
    0x0E: '[FarFarLeft]',
    0x0F: '[FarFarRight]',
    0x10: '[LoadFace]',
    0x11: '[NormalPrint]',
    0x12: '[FastPrint]',
    0x13: '[CloseSpeechFast]',
    0x14: '[CloseSpeechSlow]',
    0x15: '[ToggleMouth]',
    0x16: '[ToggleSmile]',
    0x17: '[Yes]',
    0x18: '[No]',
    0x19: '[BuySell]',
    0x1A: '[ShopContinue]',
    0x1B: '[SendToBack]',
    0x1C: '[FastPrint2]',
    0x1F: '[.]',
    0x40: '[@]',
    0x80: '[Escape]',
    0x93: '[OpenQuote]',
    0x94: '[CloseQuote]',
}

# Font tile indices (0xA0-0xFF) — FE7U/FE8U
# 0x80-0x9F are control codes (see FE_CONTROL_CODES above)
# 0xA0-0xFF are font tile indices — game-specific glyphs
# For US/EU ROMs, these map to accented Latin chars
# For JP ROMs, these map to different glyphs
# Mapping below is approximate — actual depends on ROM font
FE_FONT_TILES: dict[int, str] = {
    0xA0: 'â', 0xA1: 'ã', 0xA2: 'ä', 0xA3: 'æ', 0xA4: 'ç',
    0xA5: 'è', 0xA6: 'é', 0xA7: 'ê', 0xA8: 'ë', 0xA9: 'ì',
    0xAA: 'í', 0xAB: 'î', 0xAC: 'ï', 0xAD: 'ð', 0xAE: 'ñ',
    0xAF: 'ò', 0xB0: 'ó', 0xB1: 'ô', 0xB2: 'õ', 0xB3: 'ö',
    0xB4: '÷', 0xB5: 'ø', 0xB6: 'ù', 0xB7: 'ú', 0xB8: 'û',
    0xB9: 'ü', 0xBA: 'ý', 0xBB: 'þ', 0xBC: 'ÿ',
    # 0xBD-0xFF: game-specific symbols (not mapped yet)
}

# Game codes for detection
# FE7: BE7E (US), BE7J (JP), AE7Y (EU)
# FE8: BE8E (US), BE8J (JP), BE8P (EU)
FE7_GAME_CODES = ['BE7E', 'BE7J', 'AE7Y']
FE8_GAME_CODES = ['BE8E', 'BE8J', 'BE8P']
FE_GAME_CODES = FE7_GAME_CODES + FE8_GAME_CODES


class FETextDecoder:
    """Decoder for Fire Emblem GBA text"""

    def __init__(self):
        self.charmap: dict[int, str] = {}

        # Standard ASCII (0x20-0x7E)
        for i in range(0x20, 0x7F):
            self.charmap[i] = chr(i)

        # Control codes
        self.charmap.update(FE_CONTROL_CODES)

        # Font tiles (0xA0-0xFF)
        self.charmap.update(FE_FONT_TILES)

    def decode(self, data: bytes, start: int, length: int) -> str:
        result: list[str] = []
        i = start
        end = min(start + length, len(data))

        while i < end:
            byte = data[i]

            # End of string
            if byte == 0x00:
                break

            # Handle LoadFace (0x10 + 2 params)
            if byte == 0x10 and i + 2 < end:
                result.append('[LoadFace]')
                i += 3
                continue

            # Handle escape sequences (0x80 + @XX)
            if byte == 0x80 and i + 2 < end:
                result.append(f'[Esc@{data[i+1]:02X}]')
                i += 3
                continue

            if byte in self.charmap:
                result.append(self.charmap[byte])
            else:
                result.append(f'[{byte:02X}]')
            i += 1

        return ''.join(result)


class FireEmblemGBAPlugin(GamePlugin):
    """Плагин для Fire Emblem GBA (FE7/FE8)"""

    def __init__(self):
        super().__init__()
        self._decoder = FETextDecoder()

    @property
    def game_id_pattern(self) -> str:
        codes = '|'.join(FE_GAME_CODES)
        return f'^GBA_({codes})$'

    def get_pointer_size(self, rom: GameBoyROM) -> int:
        return 4

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Извлечение текстовых сегментов Fire Emblem GBA"""
        logger.info("Извлечение текстовых сегментов для Fire Emblem GBA")

        segments: list[dict] = []

        # FE GBA uses Huffman compression
        # Known Huffman tree locations (from FEBuilderGBA/community docs):
        # FE7U: tree at 0xB808AC, text blocks follow
        # FE8U: tree at 0x15D48C, text blocks follow

        game_id = rom.get_game_id()
        if 'BE7E' in game_id or 'AE7Y' in game_id:  # FE7 US/EU
            tree_base = 0xB808AC
            logger.info(f"FE7 detected, Huffman tree at 0x{tree_base:X}")
        elif 'BE8E' in game_id or 'BE8P' in game_id:  # FE8 US/EU
            tree_base = 0x15D48C
            logger.info(f"FE8 detected, Huffman tree at 0x{tree_base:X}")
        else:
            tree_base = 0xB808AC  # Default to FE7
            logger.info(f"Unknown FE game, defaulting to FE7 tree at 0x{tree_base:X}")

        # Scan for text blocks using Huffman decoding
        segments.extend(self._scan_huffman_text(rom, tree_base))

        logger.info(f"Total segments: {len(segments)}")
        return segments

    def _scan_huffman_text(self, rom: GameBoyROM, tree_base: int) -> list[dict]:
        """Scan for Huffman-compressed text blocks in FE ROM"""
        segments: list[dict] = []
        huffman = HuffmanHandler()

        # FE GBA text is typically in these ranges
        scan_ranges = [
            (0x100000, 0x400000),  # Text area (FE7/FE8)
        ]

        for range_start, range_end in scan_ranges:
            if range_start >= len(rom.data):
                continue

            end = min(range_end, len(rom.data))
            offset = range_start

            while offset < end - 10:
                # Try to decode a Huffman text block
                try:
                    decoded = huffman.decompress_text_block(
                        rom.data, offset, tree_base, tree_base
                    )

                    # Check if decoded text is valid
                    if len(decoded) > 5:
                        # Check for ASCII characters
                        ascii_count = sum(1 for b in decoded if 0x20 <= b <= 0x7E)
                        if ascii_count > len(decoded) * 0.5:
                            # Valid text block found
                            block_end = offset + len(decoded)

                            # Check if already covered
                            is_new = True
                            for seg in segments:
                                if seg['start'] <= offset < seg['end']:
                                    is_new = False
                                    break

                            if is_new:
                                segments.append({
                                    'name': f'fe_huffman_{len(segments)}',
                                    'start': offset,
                                    'end': block_end,
                                    'decoder': self._decoder,
                                    'compression': 'huffman',
                                    'charmap': self._decoder.charmap,
                                    'terminators': [0x00],
                                    'huffman_tree': tree_base,
                                })
                                offset = block_end
                                continue
                except Exception:
                    pass

                offset += 1

        return segments

    def get_terminators(self, segment_name: str) -> list[int]:
        return [0x00]

    def get_compression_handler(self, segment_name: str):
        # FE uses Huffman compression
        handler = HuffmanHandler()
        # Set tree pointers based on game
        # These are default values - should be set from segment data
        handler.set_tree_pointers(0xB808AC, 0xB808AC)  # FE7 default
        return handler
