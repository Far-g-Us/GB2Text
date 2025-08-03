"""
Плагин для автоматического определения структуры текста в неизвестных играх
"""

import re
from core.plugin import GamePlugin
from core.rom import GameBoyROM
from core.decoder import CharMapDecoder
from core.scanner import find_text_pointers, detect_charmap
from typing import Dict, List


class AutoDetectPlugin(GamePlugin):
    """Плагин для автоматического определения текстовых сегментов"""

    @property
    def game_id_pattern(self) -> str:
        return r'^.*$'  # Срабатывает на все игры

    def get_text_segments(self, rom: GameBoyROM) -> List[Dict]:
        """Автоматическое определение текстовых сегментов"""
        segments = []

        # 1. Поиск указателей
        pointers = find_text_pointers(rom)

        if pointers:
            # Если найдены указатели, используем их
            segments.append({
                'name': 'auto_pointers',
                'pointers': pointers,
                'decoder': self._create_auto_decoder(rom),
                'compression': None
            })
        else:
            # Если указателей нет, ищем текстовые регионы напрямую
            text_regions = self._find_text_regions(rom)
            for i, region in enumerate(text_regions):
                segments.append({
                    'name': f'auto_region_{i}',
                    'start': region['start'],
                    'end': region['end'],
                    'decoder': self._create_auto_decoder(rom, region['start']),
                    'compression': None
                })

        return segments

    def _find_text_regions(self, rom: GameBoyROM, min_length=20) -> List[Dict]:
        """Поиск регионов, похожих на текст"""
        regions = []
        current_region = None

        for i in range(len(rom.data)):
            # Проверяем, похож ли байт на текст
            is_text = 0x20 <= rom.data[i] <= 0x7E or rom.data[i] in [0x00, 0x0A, 0x0D]

            if is_text and not current_region:
                current_region = [i, i]
            elif is_text and current_region:
                current_region[1] = i
            elif not is_text and current_region:
                if current_region[1] - current_region[0] > min_length:
                    regions.append({
                        'start': current_region[0],
                        'end': current_region[1] + 1
                    })
                current_region = None

        return regions

    def _create_auto_decoder(self, rom: GameBoyROM, start_offset=0) -> CharMapDecoder:
        """Создание автоматической таблицы символов"""
        charmap = detect_charmap(rom.data, start_offset)
        return CharMapDecoder(charmap)