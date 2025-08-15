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
                if end > start and (end - start) > 200:  # Минимальная длина 200 байт
                    # Проверяем плотность текста
                    analysis = analyze_text_segment(rom.data, start, end)
                    if analysis['readability'] > 0.65:  # Минимальная плотность 65%
                        segments.append({
                            'name': f'pattern_segment_{i}',
                            'start': start,
                            'end': end,
                            'decoder': None,
                            'compression': self._get_compression_for_system(rom.system)
                        })
                        logger.info(f"Добавлен сегмент из паттерна: 0x{start:X} - 0x{end:X} "
                                    f"(плотность: {analysis['readability']:.2%})")

        # Если не найдено сегментов через паттерны, ищем указатели
        if not segments:
            logger.info("Не найдено сегментов через паттерны, ищем указатели")
            pointer_size = get_pointer_size(rom.system)
            logger.info(f"Поиск указателей с размером {pointer_size} байта")

            # Используем кэширование результатов анализа
            analyzed_ranges = {}

            pointers = find_text_pointers(rom.data, pointer_size=pointer_size)

            # Группируем близко расположенные указатели
            pointer_groups = self._group_close_pointers(pointers, max_distance=50)

            for i, group in enumerate(pointer_groups):
                start_addr = min([ptr[1] for ptr in group])

                # Проверяем, не анализировали ли мы уже этот диапазон
                range_key = (start_addr // 0x1000) * 0x1000  # Группируем по 4K
                if range_key in analyzed_ranges:
                    if not analyzed_ranges[range_key]:
                        continue  # Уже определено, что здесь нет текста
                else:
                    # Анализируем только один раз на каждые 4K
                    analysis = analyze_text_segment(rom.data, start_addr, min(start_addr + 0x1000, len(rom.data)))
                    analyzed_ranges[range_key] = analysis['readability'] > 0.65
                    if not analyzed_ranges[range_key]:
                        continue

                # Более точная оценка длины сегмента
                segment_length = self._estimate_segment_length(rom.data, start_addr, min_length=200)

                if segment_length > 200:  # Увеличиваем минимальную длину
                    # Дополнительная проверка плотности текста
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

        # Если все еще нет сегментов, используем автоопределение
        if not segments:
            logger.info("Используем автоопределение сегментов")
            # Увеличиваем минимальные требования для автоопределения
            detected = auto_detect_segments(
                rom.data,
                min_segment_length=300,
                min_readability=0.7,
                block_size=64
            )

            for i, seg in enumerate(detected):
                # Дополнительная проверка плотности текста
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

        # Добавляем дополнительную фильтрацию и проверку перекрытия сегментов
        filtered_segments = []
        segments = sorted(segments, key=lambda s: s['start'])

        for segment in segments:
            # Проверяем, не перекрывается ли этот сегмент с уже добавленными
            is_overlapping = False
            for existing in filtered_segments:
                if (segment['start'] < existing['end'] and segment['end'] > existing['start']):
                    # Если новый сегмент имеет более высокую плотность, заменяем
                    new_analysis = analyze_text_segment(rom.data, segment['start'], segment['end'])
                    existing_analysis = analyze_text_segment(rom.data, existing['start'], existing['end'])

                    if new_analysis['readability'] > existing_analysis['readability']:
                        filtered_segments.remove(existing)
                    else:
                        is_overlapping = True
                        break

            if not is_overlapping:
                filtered_segments.append(segment)

        # Ограничиваем максимальное количество сегментов
        max_segments = 20
        if len(filtered_segments) > max_segments:
            # Оставляем только сегменты с наибольшей плотностью текста
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

    def _group_close_pointers(self, pointers: List[Tuple[int, int]], max_distance: int = 50) -> List[
        List[Tuple[int, int]]]:
        """Группирует близко расположенные указатели с улучшенной логикой"""
        if not pointers:
            return []

        # Сортируем указатели по адресу текста
        sorted_pointers = sorted(pointers, key=lambda x: x[1])

        groups = []
        current_group = [sorted_pointers[0]]

        for i in range(1, len(sorted_pointers)):
            prev_addr = sorted_pointers[i - 1][1]
            curr_addr = sorted_pointers[i][1]

            # Учитываем не только расстояние, но и логические группы
            if curr_addr - prev_addr <= max_distance:
                current_group.append(sorted_pointers[i])
            else:
                # Проверяем, не является ли это началом новой логической группы
                if len(current_group) > 1 or (curr_addr - prev_addr) > 0x100:
                    groups.append(current_group)
                    current_group = [sorted_pointers[i]]

        if current_group:
            groups.append(current_group)

        # Фильтруем группы с малым количеством указателей
        filtered_groups = [g for g in groups if len(g) > 1 or g[0][1] % 0x100 < 0x80]

        if len(filtered_groups) < len(groups):
            logger = logging.getLogger('gb2text.auto_detect')
            logger.info(f"Отфильтровано {len(groups) - len(filtered_groups)} групп указателей с низкой надежностью")

        return filtered_groups

    def _estimate_segment_length(self, data: bytes, start_addr: int, min_length: int = 100) -> int:
        """Оценивает длину текстового сегмента с улучшенной точностью"""
        logger = logging.getLogger('gb2text.auto_detect')

        # Проверяем, не выходит ли за пределы ROM
        if start_addr >= len(data):
            return 0

        # Ищем терминаторы с учетом возможных паттернов
        terminators = [0x00, 0xFF, 0xFE, 0x0D, 0x0A]
        max_length = min(len(data) - start_addr, 0x1000)  # Максимальная длина 4K

        # Анализируем плотность текста для определения оптимальной длины
        best_length = min_length
        best_readability = 0

        for length in range(min_length, max_length, 50):
            analysis = analyze_text_segment(data, start_addr, start_addr + length)
            if analysis['readability'] > best_readability:
                best_readability = analysis['readability']
                best_length = length
            elif best_readability > 0.6 and analysis['readability'] < best_readability - 0.1:
                # Если плотность резко упала, вероятно, мы вышли за пределы текста
                break

        # Проверяем наличие терминаторов в конце сегмента
        for i in range(best_length - 1, max(0, best_length - 20), -1):
            if data[start_addr + i] in terminators:
                return i + 1

        return best_length

    def _get_compression_for_system(self, system: str) -> str:
        """Определяет тип сжатия для системы"""
        if system == 'gba':
            return 'gba_lz77'
        return None