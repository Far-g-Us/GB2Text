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

import logging
import time

logger = logging.getLogger('gb2text.mbc')


class MBC:
    """Базовый класс для MBC"""

    RAM_SIZES = {
        0: 0,      # No RAM
        1: 2048,   # 2KB
        2: 8192,   # 8KB
        3: 32768,  # 32KB (4x8KB)
        4: 131072, # 128KB (16x8KB)
        5: 65536,  # 64KB (8x8KB)
    }

    def __init__(self, rom_data: bytes, ram_size_code: int = 0):
        self.rom_data = rom_data
        self.rom_banks = 2
        self.ram_banks = 1
        self.ram_enabled = False
        self.rom_bank = 1
        self.ram_bank = 0
        self.has_battery = False
        ram_bytes = self.RAM_SIZES.get(ram_size_code, 0)
        self.ram_data = bytearray(ram_bytes) if ram_bytes > 0 else bytearray()
        if ram_bytes > 0x2000:
            self.ram_banks = ram_bytes // 0x2000

    def read_rom(self, address: int) -> int:
        """Чтение из ROM"""
        if 0x0000 <= address < 0x4000:
            return self.rom_data[address]
        elif 0x4000 <= address < 0x8000:
            offset = 0x4000 * self.rom_bank + (address - 0x4000)
            if offset < len(self.rom_data):
                return self.rom_data[offset]
            return 0xFF
        return 0xFF

    def read_ram(self, address: int) -> int:
        """Чтение из RAM"""
        if not self.ram_enabled:
            return 0xFF
        offset = 0x2000 * self.ram_bank + (address - 0xA000)
        if 0 <= offset < len(self.ram_data):
            return self.ram_data[offset]
        return 0xFF

    def write_ram(self, address: int, value: int):
        """Запись в RAM"""
        if not self.ram_enabled:
            return
        offset = 0x2000 * self.ram_bank + (address - 0xA000)
        if 0 <= offset < len(self.ram_data):
            self.ram_data[offset] = value & 0xFF

    def write(self, address: int, value: int):
        """Запись в карту памяти"""
        logger.debug(f"MBC.write отброшен: 0x{address:04X} = 0x{value:02X}")


class MBC1(MBC):
    """Поддержка MBC1"""

    def __init__(self, rom_data: bytes, ram_size_code: int = 0):
        super().__init__(rom_data, ram_size_code)
        self.memory_model = 0  # 0=16/8, 1=4/32

    def write(self, address: int, value: int):
        if 0x0000 <= address < 0x2000:
            self.ram_enabled = (value & 0x0F) == 0x0A
        elif 0x2000 <= address < 0x4000:
            bank = value & 0x1F
            if bank == 0:
                bank = 1
            self.rom_bank = bank
        elif 0x4000 <= address < 0x6000:
            if self.memory_model == 0:
                self.rom_bank = (self.rom_bank & 0x1F) | ((value & 0x03) << 5)
            else:
                self.ram_bank = value & 0x03
        elif 0x6000 <= address < 0x8000:
            self.memory_model = value & 0x01


class MBC2(MBC):
    """Поддержка MBC2 — встроенная RAM 512x4 bit"""

    def __init__(self, rom_data: bytes, ram_size_code: int = 0):
        super().__init__(rom_data, ram_size_code)
        self.rom_banks = 16
        self.ram_banks = 0
        self.ram_data = bytearray(512)

    def read_ram(self, address: int) -> int:
        if not self.ram_enabled:
            return 0xFF
        offset = (address - 0xA000) & 0x01FF
        return self.ram_data[offset] | 0xF0

    def write_ram(self, address: int, value: int):
        if not self.ram_enabled:
            return
        offset = (address - 0xA000) & 0x01FF
        self.ram_data[offset] = value & 0x0F

    def write(self, address: int, value: int):
        if 0x0000 <= address < 0x2000:
            if address & 0x0100:
                self.ram_enabled = (value & 0x0F) == 0x0A
        elif 0x2000 <= address < 0x4000:
            if not (address & 0x0100):
                bank = value & 0x0F
                if bank == 0:
                    bank = 1
                self.rom_bank = bank


class MBC3(MBC):
    """Поддержка MBC3 + RTC"""

    # RTC регистры
    RTC_SECONDS = 0x08
    RTC_MINUTES = 0x09
    RTC_HOURS = 0x0A
    RTC_DAY_LOW = 0x0B
    RTC_DAY_HIGH = 0x0C

    def __init__(self, rom_data: bytes, ram_size_code: int = 0):
        super().__init__(rom_data, ram_size_code)
        self.rom_banks = 16
        self.ram_banks = max(4, self.ram_banks)
        self.has_rtc = False
        self.rtc_register = 0
        self.rtc_latched = False
        self.rtc_seconds = 0
        self.rtc_minutes = 0
        self.rtc_hours = 0
        self.rtc_day_low = 0
        self.rtc_day_high = 0
        self.rtc_latch_data = [0] * 5
        self._last_latch_time = time.time()

    def _update_rtc(self):
        """Обновляет значения RTC из системного времени"""
        elapsed = int(time.time() - self._last_latch_time)
        if elapsed <= 0:
            return
        total_seconds = self.rtc_seconds + elapsed
        self.rtc_seconds = total_seconds % 60
        total_minutes = self.rtc_minutes + total_seconds // 60
        self.rtc_minutes = total_minutes % 60
        total_hours = self.rtc_hours + total_minutes // 60
        self.rtc_hours = total_hours % 24
        total_days = self.rtc_day_low | ((self.rtc_day_high & 0x01) << 8)
        total_days += total_hours // 24
        self.rtc_day_low = total_days & 0xFF
        self.rtc_day_high = (total_days >> 8) & 0x01
        self._last_latch_time = time.time()

    def _latch_rtc(self):
        """Фиксирует текущие значения RTC"""
        self._update_rtc()
        self.rtc_latch_data = [
            self.rtc_seconds,
            self.rtc_minutes,
            self.rtc_hours,
            self.rtc_day_low,
            self.rtc_day_high,
        ]

    def read_ram(self, address: int) -> int:
        if self.rtc_register >= self.RTC_SECONDS and self.rtc_register <= self.RTC_DAY_HIGH:
            idx = self.rtc_register - self.RTC_SECONDS
            if self.rtc_latched and idx < len(self.rtc_latch_data):
                return self.rtc_latch_data[idx]
            return 0xFF
        return super().read_ram(address)

    def write(self, address: int, value: int):
        if 0x0000 <= address < 0x2000:
            self.ram_enabled = (value & 0x0F) == 0x0A
        elif 0x2000 <= address < 0x4000:
            bank = value & 0x7F
            if bank == 0:
                bank = 1
            self.rom_bank = bank
        elif 0x4000 <= address < 0x6000:
            if value <= 0x03:
                self.ram_bank = value
            elif self.RTC_SECONDS <= value <= self.RTC_DAY_HIGH:
                self.rtc_register = value
                self.has_rtc = True
        elif 0x6000 <= address < 0x8000:
            # RTC latch: записать 0x00, затем 0x01
            if value == 0x00:
                self.rtc_latched = False
            elif value == 0x01 and not self.rtc_latched:
                self._latch_rtc()
                self.rtc_latched = True


class MBC5(MBC):
    """Поддержка MBC5"""

    def __init__(self, rom_data: bytes, ram_size_code: int = 0):
        super().__init__(rom_data, ram_size_code)
        self.rom_banks = 512
        self.ram_banks = max(16, self.ram_banks)

    def write(self, address: int, value: int):
        if 0x0000 <= address < 0x2000:
            self.ram_enabled = (value & 0x0F) == 0x0A
        elif 0x2000 <= address < 0x3000:
            self.rom_bank = (self.rom_bank & 0x100) | value
        elif 0x3000 <= address < 0x4000:
            self.rom_bank = (self.rom_bank & 0xFF) | ((value & 0x01) << 8)
        elif 0x4000 <= address < 0x6000:
            self.ram_bank = value & 0x0F


def create_mbc(rom_data: bytes, mbc_type: int, ram_size_code: int = 0) -> MBC:
    """Создает экземпляр MBC в зависимости от типа"""
    if mbc_type == 0x00 or mbc_type == 0x08 or mbc_type == 0x09:
        return MBC(rom_data, ram_size_code)
    elif mbc_type in (0x01, 0x02, 0x03):
        return MBC1(rom_data, ram_size_code)
    elif mbc_type == 0x05 or mbc_type == 0x06:
        return MBC2(rom_data, ram_size_code)
    elif mbc_type in (0x0B, 0x0C, 0x0D):
        return MBC3(rom_data, ram_size_code)
    elif mbc_type in (0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E):
        return MBC5(rom_data, ram_size_code)
    else:
        return MBC(rom_data, ram_size_code)
