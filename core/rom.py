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
Модуль для работы с ROM-файлами Game Boy, Game Boy Color и Game Boy Advance
"""

import re
from pathlib import Path
from typing import Dict, Any, Literal


class GameBoyROM:
    """Загрузка и базовый анализ ROM-файла"""

    def __init__(self, rom_path: str):
        self.path = rom_path
        self.data = self._load_rom(rom_path)
        self.header = self._parse_header()
        self.system = self._detect_system()

    def _load_rom(self, path: str) -> bytearray:
        with open(path, 'rb') as f:
            return bytearray(f.read())

    def _parse_header(self) -> Dict[str, Any]:
        """Извлечение информации из заголовка ROM"""
        return {
            'title': self._read_string(0x134, 15),
            'cgb_flag': self.data[0x143],
            'new_licensee': self._read_string(0x144, 2),
            'sgb_flag': self.data[0x146],
            'cartridge_type': self.data[0x147],
            'rom_size': self.data[0x148],
            'ram_size': self.data[0x149],
            'destination': self.data[0x14A],
            'old_licensee': self.data[0x14B],
            'mask_rom_version': self.data[0x14C],
            'header_checksum': self.data[0x14D],
            'global_checksum': (self.data[0x14E] << 8) | self.data[0x14F]
        }

    def _read_string(self, start: int, length: int) -> str:
        return ''.join(chr(b) for b in self.data[start:start + length]
                       if 0x20 <= b <= 0x7E).strip()

    def _detect_system(self) -> Literal['gb', 'gbc', 'gba']:
        """Определение системы по сигнатуре ROM"""
        # Проверка на Game Boy Advance
        if len(self.data) > 0xB2 and self.data[0xA0:0xB2] == b'Nintendo Game Boy':
            return 'gba'

        # Проверка на Game Boy Color
        if self.header['cgb_flag'] == 0x80 or self.header['cgb_flag'] == 0xC0:
            return 'gbc'

        return 'gb'

    def get_game_id(self) -> str:
        """Генерация уникального ID игры для поиска конфигурации"""
        title = re.sub(r'\W+', '', self.header['title']).upper()
        return f"{title}_{self.system.upper()}_{self.header['cartridge_type']:02X}"

    def is_gba(self) -> bool:
        return self.system == 'gba'

    def is_gbc(self) -> bool:
        return self.system == 'gbc'