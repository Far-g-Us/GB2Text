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


class GenericGBPlugin(GamePlugin):
    """Базовый плагин для игр Game Boy"""

    @property
    def game_id_pattern(self) -> str:
        return r'^GAME_[0-9A-F]{2}$'

    def get_text_segments(self, rom) -> list:
        from core.scanner import find_text_pointers

        # Для GB используем 16-битные указатели
        pointers = find_text_pointers(rom.data, pointer_size=get_pointer_size('gb'))

        segments = []
        for i, (ptr_addr, text_addr) in enumerate(pointers):
            # Определяем длину сегмента
            segment_length = self._estimate_segment_length(rom.data, text_addr)
            segments.append({
                'name': f'gb_segment_{i}',
                'start': text_addr,
                'end': text_addr + segment_length,
                'decoder': None,
                'compression': None
            })

        # Если нет указателей, используем стандартные адреса
        if not segments:
            segments.append({
                'name': 'main_text',
                'start': 0x4000,
                'end': 0x7FFF,
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
                'compression': 'gba_lz77'
            })

        # Если нет указателей, используем стандартные адреса для GBA
        if not segments:
            segments.append({
                'name': 'main_text',
                'start': 0x083D0000,
                'end': 0x08400000,
                'decoder': None,
                'compression': 'gba_lz77'
            })

        return segments