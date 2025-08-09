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

from core.plugin import GamePlugin
from core.rom import GameBoyROM
from core.database import get_segment_patterns
from core.scanner import auto_detect_segments
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='gb_extractor.log'
)
logger = logging.getLogger('gb_extractor')


class AutoDetectPlugin(GamePlugin):
    """Плагин для автоматического определения текстовых сегментов"""

    @property
    def game_id_pattern(self) -> str:
        return r'^.*$'

    def get_text_segments(self, rom: GameBoyROM) -> list:
        segments = []

        # Сначала пытаемся использовать типичные паттерны для системы
        patterns = get_segment_patterns(rom.system)
        for pattern in patterns:
            # Проверяем, есть ли данные в этом диапазоне
            if pattern['start_min'] < len(rom.data):
                start = max(pattern['start_min'], 0)
                end = min(pattern['end_max'], len(rom.data))
                if end > start:
                    segments.append({
                        'name': f'pattern_segment_{len(segments)}',
                        'start': start,
                        'end': end,
                        'decoder': None,
                        'compression': None
                    })

        # Если не найдено сегментов через паттерны, используем автоопределение
        if not segments:
            detected = auto_detect_segments(rom.data)
            for i, seg in enumerate(detected):
                segments.append({
                    'name': seg['name'],
                    'start': seg['start'],
                    'end': seg['end'],
                    'decoder': None,
                    'compression': None
                })

        return segments