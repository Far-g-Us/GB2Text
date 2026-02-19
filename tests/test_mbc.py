"""
Тесты для модуля MBC (Memory Bank Controller)
"""
import pytest
from core.mbc import MBC, MBC1, create_mbc


class TestMBC:
    """Тесты классов MBC"""
    
    def test_mbc_base_creation(self):
        """Тест создания базового MBC"""
        rom_data = b'\x00' * 0x8000  # Минимальный ROM
        mbc = MBC(rom_data)
        assert mbc.rom_banks == 2
        assert mbc.ram_banks == 1
        assert mbc.ram_enabled is False
        assert mbc.rom_bank == 1
    
    def test_mbc_read_rom_bank0(self):
        """Тест чтения из банка 0"""
        rom_data = bytes(range(256)) * 256  # Паттерн данных
        mbc = MBC(rom_data)
        # Чтение из банка 0 (0x0000-0x3FFF)
        value = mbc.read_rom(0x0100)
        assert value == 0x00  # Первый байт паттерна
    
    def test_mbc_read_rom_switched_bank(self):
        """Тест чтения из переключаемого банка"""
        rom_data = bytes(range(256)) * 256
        mbc = MBC(rom_data)
        mbc.rom_bank = 2
        value = mbc.read_rom(0x4000)
        assert value == 0x00
    
    def test_mbc_read_out_of_bounds(self):
        """Тест чтения за пределами ROM"""
        rom_data = b'\x00' * 0x4000
        mbc = MBC(rom_data)
        value = mbc.read_rom(0x9000)
        assert value == 0xFF  # Должен вернуть 0xFF
    
    def test_mbc_read_ram_disabled(self):
        """Тест чтения RAM когда она выключена"""
        rom_data = b'\x00' * 0x8000
        mbc = MBC(rom_data)
        mbc.ram_enabled = False
        value = mbc.read_ram(0xA000)
        assert value == 0xFF
    
    def test_mbc1_creation(self):
        """Тест создания MBC1"""
        rom_data = b'\x00' * 0x8000
        mbc1 = MBC1(rom_data)
        assert mbc1.rom_banks == 2
        assert mbc1.ram_banks == 1
        assert mbc1.memory_model == 0
    
    def test_mbc1_write_ram_enable(self):
        """Тест включения RAM"""
        rom_data = b'\x00' * 0x8000
        mbc1 = MBC1(rom_data)
        mbc1.write(0x0000, 0x0A)  # Включение RAM
        assert mbc1.ram_enabled is True
    
    def test_mbc1_write_rom_bank(self):
        """Тест переключения ROM банка"""
        rom_data = b'\x00' * 0x8000 * 2
        mbc1 = MBC1(rom_data)
        mbc1.write(0x2000, 0x05)  # Установка банка 5
        assert mbc1.rom_bank == 5
    
    def test_mbc1_write_rom_bank_zero(self):
        """Тест установки банка 0 (должен стать 1)"""
        rom_data = b'\x00' * 0x8000 * 2
        mbc1 = MBC1(rom_data)
        mbc1.write(0x2000, 0x00)  # Банк 0 -> 1
        assert mbc1.rom_bank == 1
    
    def test_create_mbc_rom_only(self):
        """Тест создания MBC для ROM без MBC (тип 0x00)"""
        rom_data = b'\x00' * 0x8000
        mbc = create_mbc(rom_data, 0x00)
        assert isinstance(mbc, MBC)
        assert not isinstance(mbc, MBC1)
    
    def test_create_mbc_mbc1(self):
        """Тест создания MBC1 (тип 0x01)"""
        rom_data = b'\x00' * 0x8000
        mbc = create_mbc(rom_data, 0x01)
        assert isinstance(mbc, MBC1)
    
    def test_create_mbc_unknown(self):
        """Тест создания MBC с неизвестным типом"""
        rom_data = b'\x00' * 0x8000
        mbc = create_mbc(rom_data, 0xFF)  # Неизвестный тип
        assert isinstance(mbc, MBC)  # Должен вернуть базовый MBC
    
    def test_create_mbc_types(self):
        """Тест различных типов MBC"""
        rom_data = b'\x00' * 0x8000
        
        # Тестируем разные типы
        for mbc_type in [0x00, 0x08, 0x09]:  # ROM Only
            mbc = create_mbc(rom_data, mbc_type)
            assert isinstance(mbc, MBC)
        
        for mbc_type in [0x01, 0x02, 0x03]:  # MBC1
            mbc = create_mbc(rom_data, mbc_type)
            assert isinstance(mbc, MBC1)
