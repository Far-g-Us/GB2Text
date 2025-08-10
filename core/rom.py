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

import logging
from typing import Dict
from core.mbc import create_mbc


class GameBoyROM:
    """Загрузка и базовый анализ ROM-файла"""

    def __init__(self, rom_path: str):
        logger = logging.getLogger('gb2text.rom')
        logger.info(f"Загрузка ROM из файла: {rom_path}")

        if not isinstance(rom_path, str):
            logger.error(f"rom_path должен быть строкой, а не {type(rom_path)}")
            raise TypeError(f"rom_path должен быть строкой, а не {type(rom_path)}")

        self.path = rom_path
        self.data = self._load_rom(rom_path)
        self.header = self._parse_header()
        self.system = self._detect_system()
        self.mbc = create_mbc(self.data, self.header['cartridge_type'])
        logger.info(f"ROM загружен успешно. Размер: {len(self.data)} байт")
        logger.info(f"Определена система: {self.system}")
        logger.debug(f"Заголовок ROM: {self.header}")

    def _load_rom(self, rom_path: str) -> bytearray:
        logger = logging.getLogger('gb2text.rom')
        logger.info(f"Чтение данных из файла: {rom_path}")

        try:
            with open(rom_path, 'rb') as f:
                data = bytearray(f.read())
            logger.info(f"Успешно прочитано {len(data)} байт")
            return data
        except Exception as e:
            logger.error(f"Ошибка при чтении ROM файла: {str(e)}")
            raise

    def _parse_header(self) -> Dict:
        """Парсинг заголовка ROM"""
        if len(self.data) < 0x150:
            raise ValueError("Недопустимый ROM файл: слишком маленький")

        # Извлекаем данные заголовка
        try:
            header = {
                'title': self.data[0x0134:0x0143].decode('ascii', errors='replace').rstrip('\x00'),
                'cgb_flag': self.data[0x0143],
                'new_licensee_code': self.data[0x0144] << 8 | self.data[0x0145],
                'sgb_flag': self.data[0x0146],
                'cartridge_type': self.data[0x0147],
                'rom_size': self.data[0x0148],
                'ram_size': self.data[0x0149],
                'destination_code': self.data[0x014A],
                'old_licensee_code': self.data[0x014B],
                'mask_rom_version': self.data[0x014C],
                'header_checksum': self.data[0x014D],
                'global_checksum': (self.data[0x014E] << 8) | self.data[0x014F]
            }
        except Exception as e:
            raise ValueError(f"Недопустимый ROM файл: ошибка при парсинге заголовка: {str(e)}")

        # Исправляем проблему с отсутствующим new_licensee_code
        if header['new_licensee_code'] == 0xFFFF:
            header['new_licensee_code'] = 0

        return header

    def _read_string(self, start: int, length: int) -> str:
        return ''.join(chr(b) for b in self.data[start:start + length]
                       if 0x20 <= b <= 0x7E).strip()

    def _detect_system(self) -> str:
        """Определение системы по сигнатуре ROM"""
        logger = logging.getLogger('gb2text.rom')
        logger.info("Определение типа системы...")

        # Проверка на Game Boy Advance
        if len(self.data) > 0xB2 and self.data[0xA0:0xB2] == b'Nintendo Game Boy':
            logger.info("Определена система: Game Boy Advance (gba)")
            return 'gba'

        # Проверка на Game Boy Color
        if self.header['cgb_flag'] == 0x80 or self.header['cgb_flag'] == 0xC0:
            logger.info("Определена система: Game Boy Color (gbc)")
            return 'gbc'

        # Проверка на Game Boy Pocket/Color по заголовку
        if self.header['new_licensee_code'] == 0x33:
            logger.info("Определена система: Game Boy Color (gbc)")
            return 'gbc'

        # Проверка на Game Boy по заголовку
        if self.header['header_checksum'] != 0:
            logger.info("Определена система: Game Boy (gb)")
            return 'gb'

        # Проверка по размеру ROM
        rom_size = self.header['rom_size']
        if rom_size <= 8:  # До 8 MB
            logger.warning("Не удалось точно определить систему, используем Game Boy (gb) по умолчанию")
            return 'gb'
        else:
            return 'gbc'


    def get_game_id(self) -> str:
        """Возвращает идентификатор игры"""
        # Создаем безопасный идентификатор
        cartridge_type = self.header['cartridge_type']
        return f"GAME_{cartridge_type:02X}"

    def is_gba(self) -> bool:
        return self.system == 'gba'

    def is_gbc(self) -> bool:
        return self.system == 'gbc'

    def read(self, address: int) -> int:
        """Чтение из ROM с учетом MBC"""
        if 0x0000 <= address < 0x8000:
            return self.mbc.read_rom(address)
        elif 0xA000 <= address < 0xC000:
            return self.mbc.read_ram(address - 0xA000)
        return 0xFF