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
Base classes and functions not tied to any commercial game
"""

from core.constants import SYSTEM_GB
from core.database import get_pointer_size
from core.plugin import GamePlugin
from core.scanner import find_text_pointers


class GenericGBPlugin(GamePlugin):
    """Base plugin for Game Boy games"""

    @property
    def game_id_pattern(self) -> str:
        return r'^(GB|GAME)_[A-Z0-9]+$'

    def get_text_segments(self, rom) -> list:
        # For GB/GBC use 16-bit pointers
        system = getattr(rom, 'system', SYSTEM_GB)
        pointer_size = get_pointer_size(system)

        pointers = find_text_pointers(
            rom.data,
            pointer_size=pointer_size,
        )

        segments = []
        for i, (_ptr_addr, text_addr) in enumerate(pointers):
            segment_length = self._estimate_segment_length(rom.data, text_addr)
            segments.append({
                'name': f'{system}_segment_{i}',
                'start': text_addr,
                'end': text_addr + segment_length,
                'decoder': None,
                'compression': None
            })

        # Fallback: search for text blocks using database patterns
        if not segments:
            from core.database import get_segment_patterns
            patterns = get_segment_patterns(system)
            for pat in patterns:
                start_min = pat['start_min']
                end_max = min(pat['end_max'], len(rom.data))
                if end_max - start_min >= 0x100:
                    segments.append({
                        'name': f'{system}_fallback_{len(segments)}',
                        'start': start_min,
                        'end': end_max,
                        'decoder': None,
                        'compression': None
                    })

        # Last fallback: the whole bank 1
        if not segments:
            max_addr = min(0x8000, len(rom.data))
            segments.append({
                'name': 'main_text',
                'start': 0x4000,
                'end': max_addr,
                'decoder': None,
                'compression': None
            })

        return segments

    def _estimate_segment_length(self, rom_data: bytes, start_addr: int) -> int:
        """Estimate the text-segment length"""
        # Search for a terminator or the end of the segment
        for i in range(start_addr, min(start_addr + 0x1000, len(rom_data))):
            if rom_data[i] in [0x00, 0xFF, 0xFE]:  # Common terminators
                return i - start_addr + 1
        return 0x100  # Standard length if no terminator is found


class GenericGBCPlugin(GenericGBPlugin):
    """Base plugin for Game Boy Color games"""

    @property
    def game_id_pattern(self) -> str:
        return r'^(GBC|GAME)_[A-Z0-9]+$'

    pass


class GenericGBAPlugin(GenericGBPlugin):
    """Base plugin for Game Boy Advance games"""

    @property
    def game_id_pattern(self) -> str:
        return r'^GBA_[0-9A-F]{4}$'

    def get_text_segments(self, rom) -> list:
        from core.scanner import find_text_pointers

        # For GBA use 32-bit pointers with the base address 0x08000000
        pointers = find_text_pointers(
            rom.data,
            pointer_size=get_pointer_size('gba'),
            address_base=0x08000000
        )

        segments = []
        for i, (_ptr_addr, text_addr) in enumerate(pointers):
            # Determine the segment length
            segment_length = self._estimate_segment_length(rom.data, text_addr)
            segments.append({
                'name': f'gba_segment_{i}',
                'start': text_addr,
                'end': text_addr + segment_length,
                'decoder': None,
                'compression': None
            })

        # If there are no pointers, use standard GBA addresses
        if not segments:
            start_va = 0x083D0000
            end_va = 0x08400000
            start = max(0, start_va - 0x08000000)
            end = max(start, end_va - 0x08000000)
            start = min(start, len(rom.data))
            end = min(end, len(rom.data))
            if end - start >= 0x100:
                segments.append({
                    'name': 'main_text',
                    'start': start,
                    'end': end,
                    'decoder': None,
                    'compression': None
                })
            else:
                end = max(0x4000, min(0x7FFF, len(rom.data)))
                if end > 0x4000:
                    segments.append({
                        'name': 'main_text',
                        'start': 0x4000,
                        'end': end,
                        'decoder': None,
                        'compression': None
                    })

        return segments
