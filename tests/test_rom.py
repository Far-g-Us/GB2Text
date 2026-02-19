"""
Тесты для модуля ROM
"""
import os
import tempfile
from core.rom import GameBoyROM


class TestROM:
    """Тесты класса GameBoyROM"""
    
    def create_test_rom_file(self, size=0x8000, system='gb', title='TEST'):
        """Создание тестового ROM файла"""
        # Создаем минимальный ROM
        rom_data = bytearray(size)
        
        # Заголовок
        title_bytes = title.encode('ascii')[:11].ljust(11, b'\x00')
        rom_data[0x00:0x0B] = title_bytes
        
        # Система (для GBA)
        if system == 'gba':
            rom_data[0x00:0x04] = b'GBA '  # Nintendo logo
        elif system == 'gbc':
            rom_data[0x0143] = 0x80  # GBC flag
        
        # Тип картриджа
        rom_data[0x0147] = 0x00  # ROM Only
        
        # Размер ROM
        rom_data[0x0148] = 0x00  # 32KB
        
        return bytes(rom_data)
    
    def test_rom_from_file(self):
        """Тест загрузки ROM из файла"""
        rom_data = self.create_test_rom_file()
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            assert len(rom.data) > 0
            assert rom.system in ['gb', 'gbc', 'gba']
        finally:
            os.unlink(temp_path)
    
    def test_rom_header_cartridge_type(self):
        """Тест получения типа картриджа"""
        rom_data = self.create_test_rom_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            assert 'cartridge_type' in rom.header
        finally:
            os.unlink(temp_path)
    
    def test_rom_system_detection_gb(self):
        """Тест определения системы GB"""
        rom_data = self.create_test_rom_file(system='gb')
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            assert rom.system in ['gb', 'gbc']
        finally:
            os.unlink(temp_path)
    
    def test_rom_system_detection_gba(self):
        """Тест определения системы GBA"""
        rom_data = self.create_test_rom_file(system='gba')
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gba') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            assert rom.system == 'gba'
        finally:
            os.unlink(temp_path)
    
    def test_rom_get_game_id(self):
        """Тест получения ID игры"""
        rom_data = self.create_test_rom_file(title='TESTGAME')
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            game_id = rom.get_game_id()
            assert isinstance(game_id, str)
            assert 'GAME_' in game_id
        finally:
            os.unlink(temp_path)
    
    def test_rom_read(self):
        """Тест чтения из ROM"""
        rom_data = self.create_test_rom_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            value = rom.read(0x0100)
            assert isinstance(value, int)
        finally:
            os.unlink(temp_path)
    
    def test_rom_mbc_created(self):
        """Тест создания MBC"""
        rom_data = self.create_test_rom_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            assert rom.mbc is not None
        finally:
            os.unlink(temp_path)
    
    def test_rom_small_size(self):
        """Тест с минимальным размером ROM"""
        rom_data = self.create_test_rom_file(size=0x4000)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            assert len(rom.data) == 0x4000
        finally:
            os.unlink(temp_path)
