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
Plugin for automated detection of text structure in unknown games
"""

import logging

from core.database import get_pointer_size, get_segment_patterns
from core.plugin import GamePlugin
from core.rom import GameBoyROM
from core.scanner import analyze_text_segment, auto_detect_segments, find_text_pointers

# Logging is configured at the entry points (main/run_gui)
logger = logging.getLogger('gb2text.auto_detect')

class AutoDetectPlugin(GamePlugin):
    """Plugin for automatic text-segment detection"""

    @property
    def game_id_pattern(self) -> str:
        return r'^.*$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        """Automatically detect text segments"""
        logger = logging.getLogger('gb2text.auto_detect')
        logger.info(f"Начало автоопределения текстовых сегментов для системы {rom.system}")

        segments = []

        # Use typical patterns for the system
        patterns = get_segment_patterns(rom.system)
        logger.info(f"Найдено {len(patterns)} типичных паттернов для системы {rom.system}")

        for i, pattern in enumerate(patterns):
            # Check whether there is data in this range
            if pattern['start_min'] < len(rom.data):
                start = max(pattern['start_min'], 0)
                end = min(pattern['end_max'], len(rom.data))
                if end > start and (end - start) > 200:  # Minimum length 200 bytes
                    # Check text density
                    analysis = analyze_text_segment(rom.data, start, end)
                    if analysis['readability'] > 0.65:  # Minimum density 65%
                        segments.append({
                            'name': f'pattern_segment_{i}',
                            'start': start,
                            'end': end,
                            'decoder': None,
                            'compression': self._get_compression_for_system(rom.system)
                        })
                        logger.info(f"Добавлен сегмент из паттерна: 0x{start:X} - 0x{end:X} "
                                    f"(плотность: {analysis['readability']:.2%})")

        # If no segments were found via patterns, search for pointers
        if not segments:
            logger.info("Не найдено сегментов через паттерны, ищем указатели")
            pointer_size = get_pointer_size(rom.system)
            logger.info(f"Поиск указателей с размером {pointer_size} байта")

            # Cache the analysis results
            analyzed_ranges = {}

            address_base = 0x08000000 if rom.system == 'gba' else 0
            pointers = find_text_pointers(
                rom.data,
                pointer_size=pointer_size,
                address_base=address_base
            )

            # Group closely spaced pointers
            pointer_groups = self._group_close_pointers(pointers, max_distance=50)

            for i, group in enumerate(pointer_groups):
                start_addr = min([ptr[1] for ptr in group])

                # Check whether we already analyzed this range
                range_key = (start_addr // 0x1000) * 0x1000  # Group by 4K
                if range_key in analyzed_ranges:
                    if not analyzed_ranges[range_key]:
                        continue  # Already determined that there is no text here
                else:
                    # Analyze only once per 4K
                    analysis = analyze_text_segment(rom.data, start_addr, min(start_addr + 0x1000, len(rom.data)))
                    analyzed_ranges[range_key] = analysis['readability'] > 0.65
                    if not analyzed_ranges[range_key]:
                        continue

                # More accurate segment length estimation
                segment_length = self._estimate_segment_length(rom.data, start_addr, min_length=200)

                if segment_length > 200:  # Increase the minimum length
                    # Additional text-density check
                    analysis = analyze_text_segment(rom.data, start_addr, start_addr + segment_length)
                    if analysis['readability'] > 0.65:
                        segments.append({
                            'name': f'pointer_segment_{i}',
                            'start': start_addr,
                            'end': start_addr + segment_length,
                            'decoder': None,
                            'compression': self._get_compression_for_system(rom.system)
                        })
                        logger.info(
                            f"Добавлен сегмент из указателей: 0x{start_addr:X} - 0x{start_addr + segment_length:X} "
                            f"(плотность: {analysis['readability']:.2%})")

        # If there are still no segments, use auto-detection
        if not segments:
            logger.info("Используем автоопределение сегментов")
            # Increase the minimum auto-detection requirements
            detected = auto_detect_segments(
                rom.data,
                min_segment_length=300,
                min_readability=0.7,
                block_size=64
            )

            for _i, seg in enumerate(detected):
                # Additional text-density check
                analysis = analyze_text_segment(rom.data, seg['start'], seg['end'])
                if analysis['readability'] > 0.7:
                    segments.append({
                        'name': seg['name'],
                        'start': seg['start'],
                        'end': seg['end'],
                        'decoder': None,
                        'compression': self._get_compression_for_system(rom.system)
                    })
                    logger.info(f"Автоопределён сегмент: 0x{seg['start']:X} - 0x{seg['end']:X} "
                                f"(плотность: {analysis['readability']:.2%})")

        # Add additional filtering and segment-overlap checking
        filtered_segments = []
        segments = sorted(segments, key=lambda s: s['start'])

        for segment in segments:
            # Check whether this segment overlaps the already added ones
            is_overlapping = False
            for existing in filtered_segments:
                if (segment['start'] < existing['end'] and segment['end'] > existing['start']):
                    # If the new segment has higher density, replace it
                    new_analysis = analyze_text_segment(rom.data, segment['start'], segment['end'])
                    existing_analysis = analyze_text_segment(rom.data, existing['start'], existing['end'])

                    if new_analysis['readability'] > existing_analysis['readability']:
                        filtered_segments.remove(existing)
                    else:
                        is_overlapping = True
                        break

            if not is_overlapping:
                filtered_segments.append(segment)

        # Limit the maximum number of segments
        max_segments = 20
        if len(filtered_segments) > max_segments:
            # Keep only the segments with the highest text density
            filtered_segments = sorted(
                filtered_segments,
                key=lambda s: analyze_text_segment(rom.data, s['start'], s['end'])['readability'],
                reverse=True
            )[:max_segments]
            logger.warning(f"Обнаружено {len(segments)} сегментов, ограничено до {max_segments}")

        segments = filtered_segments

        if not segments:
            logger.warning("Не удалось определить текстовые сегменты")

        logger.info(f"Автоопределено {len(segments)} текстовых сегментов")

        return segments

    def _group_close_pointers(self, pointers: list[tuple[int, int]], max_distance: int = 50) -> list[
        list[tuple[int, int]]]:
        """Group closely spaced pointers with improved logic"""
        if not pointers:
            return []

        # Sort pointers by text address
        sorted_pointers = sorted(pointers, key=lambda x: x[1])

        groups = []
        current_group = [sorted_pointers[0]]

        for i in range(1, len(sorted_pointers)):
            prev_addr = sorted_pointers[i - 1][1]
            curr_addr = sorted_pointers[i][1]

            # Consider not only distance but also logical groups
            if curr_addr - prev_addr <= max_distance:
                current_group.append(sorted_pointers[i])
            else:
                # Check whether this is the start of a new logical group
                if len(current_group) > 1 or (curr_addr - prev_addr) > 0x100:
                    groups.append(current_group)
                    current_group = [sorted_pointers[i]]

        if current_group:
            groups.append(current_group)

        # Filter out groups with a small number of pointers
        filtered_groups = [g for g in groups if len(g) > 1 or g[0][1] % 0x100 < 0x80]

        if len(filtered_groups) < len(groups):
            logger = logging.getLogger('gb2text.auto_detect')
            logger.info(f"Отфильтровано {len(groups) - len(filtered_groups)} групп указателей с низкой надежностью")

        return filtered_groups

    def _estimate_segment_length(self, data: bytes, start_addr: int, min_length: int = 100) -> int:
        """Estimate the text-segment length with improved accuracy"""
        logging.getLogger('gb2text.auto_detect')

        # Check whether it goes beyond the limits of the ROM
        if start_addr >= len(data):
            return 0

        # Search for terminators taking possible patterns into account
        terminators = [0x00, 0xFF, 0xFE, 0x0D, 0x0A]
        max_length = min(len(data) - start_addr, 0x1000)  # Maximum length 4K

        # Analyze text density to determine the optimal length
        best_length = min_length
        best_readability = 0

        for length in range(min_length, max_length, 50):
            analysis = analyze_text_segment(data, start_addr, start_addr + length)
            if analysis['readability'] > best_readability:
                best_readability = analysis['readability']
                best_length = length
            elif best_readability > 0.6 and analysis['readability'] < best_readability - 0.1:
                # If density dropped sharply, we probably went beyond the text
                break

        # Check for terminators at the end of the segment
        for i in range(best_length - 1, max(0, best_length - 20), -1):
            if data[start_addr + i] in terminators:
                return i + 1

        return best_length

    def _get_compression_for_system(self, system: str) -> str:
        """Determine the compression type for the system"""
        if system == 'gba':
            return 'gba_lz77'
        return None
