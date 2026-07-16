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
Базовые классы и функции без привязки к коммерческим играм
"""

from core.plugin import GamePlugin
from core.database import get_pointer_size
from core.scanner import find_text_pointers
from core.constants import GBA_ROM_BASE_ADDRESS, SYSTEM_GB, SYSTEM_GBC, SYSTEM_GBA

class GenericGBPlugin(GamePlugin):
    """Базовый плагин для игр Game Boy"""

    @property
    def game_id_pattern(self) -> str:
        return r'^GAME_[0-9A-F]{2}$'

    def get_text_segments(self, rom) -> list:
        # Для GB/GBC используем 16-битные указатели
        system = getattr(rom, 'system', SYSTEM_GB)
        pointer_size = get_pointer_size(system)

        pointers = find_text_pointers(
            rom.data,
            pointer_size=pointer_size,
        )

        segments = []
        for i, (ptr_addr, text_addr) in enumerate(pointers):
            segment_length = self._estimate_segment_length(rom.data, text_addr)
            segments.append({
                'name': f'{system}_segment_{i}',
                'start': text_addr,
                'end': text_addr + segment_length,
                'decoder': None,
                'compression': None
            })

        # Fallback: ищем текстовые блоки по паттернам из БД
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

        # Последний fallback: весь банк 1
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
        """Оценивает длину текстового сегмента"""
        # Ищем терминатор или конец сегмента
        for i in range(start_addr, min(start_addr + 0x1000, len(rom_data))):
            if rom_data[i] in [0x00, 0xFF, 0xFE]:  # Распространенные терминаторы
                return i - start_addr + 1
        return 0x100  # Стандартная длина, если терминатор не найден


class GenericGBCPlugin(GenericGBPlugin):
    """Базовый плагин для игр Game Boy Color"""
    pass


class GenericGBAPlugin(GenericGBPlugin):
    """Базовый плагин для игр Game Boy Advance"""

    def get_text_segments(self, rom) -> list:
        from core.scanner import find_text_pointers

        # Для GBA используем 32-битные указатели
        pointers = find_text_pointers(rom.data, pointer_size=get_pointer_size('gba'))

        segments = []
        for i, (ptr_addr, text_addr) in enumerate(pointers):
            # Определяем длину сегмента
            segment_length = self._estimate_segment_length(rom.data, text_addr)
            segments.append({
                'name': f'gba_segment_{i}',
                'start': text_addr,
                'end': text_addr + segment_length,
                'decoder': None,
                'compression': None
            })

        # Если нет указателей, используем стандартные адреса для GBA
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
                segments.append({
                    'name': 'main_text',
                    'start': 0x4000,
                    'end': min(0x7FFF, len(rom.data)),
                    'decoder': None,
                    'compression': None
                })

        return segments