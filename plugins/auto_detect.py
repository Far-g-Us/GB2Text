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
Плагин для автоматического определения структуры текста в неизвестных играх
"""

from datetime import time
from typing import List, Dict, Tuple
from core.plugin import GamePlugin
from core.rom import GameBoyROM
from core.database import get_segment_patterns, get_pointer_size
from core.scanner import auto_detect_segments, find_text_pointers, analyze_text_segment
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='gb2text.log'
)
logger = logging.getLogger('gb2text')


class AutoDetectPlugin(GamePlugin):
    """Плагин для автоматического определения текстовых сегментов"""

    @property
    def game_id_pattern(self) -> str:
        return r'^.*$'

    def get_text_segments(self, rom: GameBoyROM) -> List[Dict]:
        """Автоматическое определение текстовых сегментов"""
        logger = logging.getLogger('gb2text.auto_detect')
        logger.info(f"Начало автоопределения текстовых сегментов для системы {rom.system}")

        segments = []

        # Используем типичные паттерны для системы
        patterns = get_segment_patterns(rom.system)
        logger.info(f"Найдено {len(patterns)} типичных паттернов для системы {rom.system}")

        for i, pattern in enumerate(patterns):
            # Проверяем, есть ли данные в этом диапазоне
            if pattern['start_min'] < len(rom.data):
                start = max(pattern['start_min'], 0)
                end = min(pattern['end_max'], len(rom.data))
                if end > start and (end - start) > 100:  # Минимальная длина 100 байт
                    segments.append({
                        'name': f'pattern_segment_{i}',
                        'start': start,
                        'end': end,
                        'decoder': None,
                        'compression': self._get_compression_for_system(rom.system)
                    })
                    logger.info(f"Добавлен сегмент из паттерна: 0x{start:X} - 0x{end:X}")

        # Если не найдено сегментов через паттерны, ищем указатели
        if not segments:
            logger.info("Не найдено сегментов через паттерны, ищем указатели")
            pointer_size = get_pointer_size(rom.system)
            logger.info(f"Поиск указателей с размером {pointer_size} байта")

            pointers = find_text_pointers(rom.data, pointer_size=pointer_size)

            # Группируем близко расположенные указатели
            pointer_groups = self._group_close_pointers(pointers)

            for i, group in enumerate(pointer_groups):
                start_addr = min([ptr[1] for ptr in group])
                segment_length = self._estimate_segment_length(rom.data, start_addr)

                if segment_length > 100:  # Минимальная длина
                    segments.append({
                        'name': f'pointer_segment_{i}',
                        'start': start_addr,
                        'end': start_addr + segment_length,
                        'decoder': None,
                        'compression': self._get_compression_for_system(rom.system)
                    })
                    logger.info(f"Добавлен сегмент из указателей: 0x{start_addr:X} - 0x{start_addr + segment_length:X}")

        # Если все еще нет сегментов, используем автоопределение
        if not segments:
            logger.info("Используем автоопределение сегментов")
            detected = auto_detect_segments(rom.data, min_segment_length=200)
            for i, seg in enumerate(detected):
                segments.append({
                    'name': seg['name'],
                    'start': seg['start'],
                    'end': seg['end'],
                    'decoder': None,
                    'compression': self._get_compression_for_system(rom.system)
                })

        # Добавляем фильтрацию сегментов по плотности текста
        filtered_segments = []
        for segment in segments:
            analysis = analyze_text_segment(rom.data, segment['start'], segment['end'])
            if analysis['readability'] > 0.5:  # Минимальная плотность текста 50%
                filtered_segments.append(segment)
                logger.info(f"Сегмент 0x{segment['start']:X} - 0x{segment['end']:X} "
                            f"принят (плотность текста: {analysis['readability']:.2%})")
            else:
                logger.info(f"Сегмент 0x{segment['start']:X} - 0x{segment['end']:X} "
                            f"отклонен (плотность текста: {analysis['readability']:.2%})")

        segments = filtered_segments

        if not segments:
            logger.warning("Не удалось определить текстовые сегменты")

        logger.info(f"Автоопределено {len(segments)} текстовых сегментов")

        return segments

    def _group_close_pointers(self, pointers: List[Tuple[int, int]], max_distance: int = 100) -> List[
        List[Tuple[int, int]]]:
        """Группирует близко расположенные указатели"""
        if not pointers:
            return []

        sorted_pointers = sorted(pointers, key=lambda x: x[1])
        groups = []
        current_group = [sorted_pointers[0]]

        for i in range(1, len(sorted_pointers)):
            prev_addr = sorted_pointers[i - 1][1]
            curr_addr = sorted_pointers[i][1]

            if curr_addr - prev_addr <= max_distance:
                current_group.append(sorted_pointers[i])
            else:
                groups.append(current_group)
                current_group = [sorted_pointers[i]]

        if current_group:
            groups.append(current_group)

        return groups

    def _estimate_segment_length(self, rom_data: bytes, start_addr: int) -> int:
        """Оценивает длину текстового сегмента"""
        # Ищем терминатор или конец сегмента
        for i in range(start_addr, min(start_addr + 0x1000, len(rom_data))):
            if rom_data[i] in [0x00, 0xFF, 0xFE]:  # Распространенные терминаторы
                return i - start_addr + 1
        return 0x100  # Стандартная длина, если терминатор не найден

    def _get_compression_for_system(self, system: str) -> str:
        """Определяет тип сжатия для системы"""
        if system == 'gba':
            return 'gba_lz77'
        return None