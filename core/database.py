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
База данных с безопасной информацией о типичных структурах ROM
"""

from typing import List, Dict
import logging
from core.constants import SYSTEM_GB, SYSTEM_GBC, SYSTEM_GBA, GBA_ROM_BASE_ADDRESS, POINTER_SIZES

logger = logging.getLogger('gb2text.database')

# Безопасная база данных с общими паттернами
ROM_DATABASE = {
    SYSTEM_GB: {
        'text_segment_patterns': [
            {'start_min': 0x4000, 'start_max': 0x5000, 'end_min': 0x6000, 'end_max': 0x7FFF},
            {'start_min': 0x8000, 'start_max': 0x9000, 'end_min': 0xA000, 'end_max': 0xBFFF}
        ],
        'pointer_size': POINTER_SIZES[SYSTEM_GB]  # 16-битные указатели для GB
    },
    SYSTEM_GBC: {
        'text_segment_patterns': [
            {'start_min': 0x4000, 'start_max': 0x5000, 'end_min': 0x6000, 'end_max': 0x7FFF},
            {'start_min': 0x8000, 'start_max': 0x9000, 'end_min': 0xA000, 'end_max': 0xBFFF}
        ],
        'pointer_size': POINTER_SIZES[SYSTEM_GBC]  # 16-битные указатели для GBC
    },
    SYSTEM_GBA: {
        'text_segment_patterns': [
            {'start_min': GBA_ROM_BASE_ADDRESS + 0x0D0000, 'start_max': GBA_ROM_BASE_ADDRESS + 0x0E0000, 
             'end_min': GBA_ROM_BASE_ADDRESS + 0x100000, 'end_max': GBA_ROM_BASE_ADDRESS + 0x120000}
        ],
        'pointer_size': POINTER_SIZES[SYSTEM_GBA]  # 32-битные указатели для GBA
    }
}

def get_segment_patterns(system: str) -> List[Dict]:
    """Получает типичные паттерны текстовых сегментов для системы"""
    return ROM_DATABASE.get(system, {}).get('text_segment_patterns', [])

def get_pointer_size(system: str) -> int:
    """Получает размер указателя для системы"""
    size = ROM_DATABASE.get(system, {}).get('pointer_size', 2)
    if size is None:
        logger.warning(f"Неизвестный размер указателя для системы {system}, используем 2 по умолчанию")
        return 2
    return size