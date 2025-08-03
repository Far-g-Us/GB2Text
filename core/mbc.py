class MBC:
    """Базовый класс для обработки Memory Bank Controllers"""

    def __init__(self, rom_data: bytearray, cartridge_type: int):
        self.rom_data = rom_data
        self.cartridge_type = cartridge_type
        self.rom_banks = 2 ** (rom_data[0x148] + 1) if rom_data[0x148] < 0x08 else 0

    def read(self, address: int) -> int:
        """Чтение байта из виртуального адресного пространства"""
        # Реализация будет зависеть от типа MBC
        if address < 0x4000:  # Банк 0
            return self.rom_data[address]
        elif address < 0x8000:  # Переключаемый банк
            return self.rom_data[address]
        # Другие области памяти...
        return 0