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
Поддержка различных Memory Bank Controllers
"""


class MBC:
    """Базовый класс для MBC"""

    def __init__(self, rom_data: bytes):
        self.rom_data = rom_data
        self.rom_banks = 2
        self.ram_banks = 1
        self.ram_enabled = False
        self.rom_bank = 1
        self.ram_bank = 0

    def read_rom(self, address: int) -> int:
        """Чтение из ROM"""
        if 0x0000 <= address < 0x4000:
            # Банк 0
            return self.rom_data[address]
        elif 0x4000 <= address < 0x8000:
            # Переключаемый банк
            offset = 0x4000 * self.rom_bank + (address - 0x4000)
            if offset < len(self.rom_data):
                return self.rom_data[offset]
            return 0xFF
        return 0xFF

    def read_ram(self, address: int) -> int:
        """Чтение из RAM"""
        if not self.ram_enabled:
            return 0xFF
        # Реализация зависит от типа MBC
        return 0xFF

    def write(self, address: int, value: int):
        """Запись в карту памяти"""
        pass


class MBC1(MBC):
    """Поддержка MBC1"""

    def __init__(self, rom_data: bytes):
        super().__init__(rom_data)
        self.rom_banks = 2
        self.ram_banks = 1
        self.memory_model = 0  # 0=16/8, 1=4/32, 2=16/32

    def write(self, address: int, value: int):
        if 0x0000 <= address < 0x2000:
            # Включение/отключение RAM
            self.ram_enabled = (value & 0x0F) == 0x0A
        elif 0x2000 <= address < 0x4000:
            # Нижние биты номера ROM-банка
            bank = value & 0x1F
            if bank == 0:
                bank = 1
            self.rom_bank = bank
        elif 0x4000 <= address < 0x6000:
            # Верхние биты номера ROM-банка или RAM-банка
            if self.memory_model == 0:
                self.rom_bank = (self.rom_bank & 0x1F) | ((value & 0x03) << 5)
            else:
                self.ram_bank = value & 0x03
        elif 0x6000 <= address < 0x8000:
            # Переключение режима памяти
            self.memory_model = value & 0x01


def create_mbc(rom_data: bytes, mbc_type: int) -> MBC:
    """Создает экземпляр MBC в зависимости от типа"""
    if mbc_type == 0x00 or mbc_type == 0x08 or mbc_type == 0x09:
        return MBC(rom_data)  # Без MBC
    elif mbc_type == 0x01 or mbc_type == 0x02 or mbc_type == 0x03:
        return MBC1(rom_data)
    # Добавьте другие типы MBC по мере необходимости
    else:
        return MBC(rom_data)  # По умолчанию без MBC