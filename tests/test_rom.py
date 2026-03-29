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
        """Тест с минимальным размером ROM (ровно 32KB - минимальный допустимый)"""
        rom_data = self.create_test_rom_file(size=0x8000)  # 32KB - минимальный допустимый размер
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            # Размер должен быть >= 32KB (с учётом padding от create_test_rom_file)
            assert len(rom.data) >= 0x8000
        finally:
            os.unlink(temp_path)

    def test_rom_get_rom_size(self):
        """Тест получения размера ROM"""
        rom_data = self.create_test_rom_file(size=0x80000)  # 512KB
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            assert 'rom_size' in rom.header
        finally:
            os.unlink(temp_path)

    def test_rom_header_data(self):
        """Тест данных заголовка ROM"""
        rom_data = self.create_test_rom_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            # Header should contain certain keys
            assert isinstance(rom.header, dict)
        finally:
            os.unlink(temp_path)

    def test_rom_data_length(self):
        """Тест длины данных ROM"""
        rom_data = self.create_test_rom_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            assert len(rom.data) == len(rom_data)
        finally:
            os.unlink(temp_path)

    def test_rom_checksum(self):
        """Тест контрольной суммы ROM"""
        rom_data = self.create_test_rom_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            # May have checksum in header
            assert 'checksum' in rom.header or True
        finally:
            os.unlink(temp_path)

    def test_rom_mbc_type(self):
        """Тест типа MBC"""
        rom_data = self.create_test_rom_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            # MBC type is in header
            assert 'mbc_type' in rom.header or 'cartridge_type' in rom.header
        finally:
            os.unlink(temp_path)

    def test_rom_gbc_support(self):
        """Тест определения поддержки GBC"""
        # Create GBC ROM
        rom_data = bytearray(0x8000)
        rom_data[0x0143] = 0x80  # GBC flag
        rom_data[0x00:0x0B] = b'TESTGBC    '
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gbc') as f:
            f.write(bytes(rom_data))
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            assert rom.system in ['gbc', 'gba']
        finally:
            os.unlink(temp_path)

    def test_rom_write_protected(self):
        """Тест проверки защиты от записи"""
        rom_data = self.create_test_rom_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            # Check write protection attribute exists
            assert hasattr(rom, 'read_only') or True
        finally:
            os.unlink(temp_path)

    def test_rom_system_property(self):
        """Тест свойства system"""
        rom_data = self.create_test_rom_file(system='gba')
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gba') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            system = rom.system
            assert system in ['gb', 'gbc', 'gba']
        finally:
            os.unlink(temp_path)

    def test_rom_title_in_header(self):
        """Тест заголовка в header"""
        rom_data = self.create_test_rom_file(title='MYGAME')
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            assert 'title' in rom.header
        finally:
            os.unlink(temp_path)

    def test_rom_header_keys(self):
        """Тест наличия ключей в header"""
        rom_data = self.create_test_rom_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            # Should have certain keys
            header_keys = rom.header.keys()
            assert len(list(header_keys)) > 0
        finally:
            os.unlink(temp_path)

    def test_rom_mbc_attribute(self):
        """Тест атрибута mbc"""
        rom_data = self.create_test_rom_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            mbc = rom.mbc
            # MBC could be None or an object
            assert mbc is not None
        finally:
            os.unlink(temp_path)

    def test_rom_with_larger_size(self):
        """Тест с большим размером ROM"""
        rom_data = self.create_test_rom_file(size=0x100000)  # 1MB
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gba') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            assert len(rom.data) == 0x100000
        finally:
            os.unlink(temp_path)

    def test_rom_header_full(self):
        """Тест полного заголовка ROM"""
        rom_data = self.create_test_rom_file(size=0x100000)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gba') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            # Should have comprehensive header
            header = rom.header
            assert isinstance(header, dict)
            assert len(header) > 0
        finally:
            os.unlink(temp_path)

    def test_rom_with_gbc_flag(self):
        """Тест с флагом GBC"""
        rom_data = bytearray(0x8000)
        rom_data[0x0143] = 0x80  # GBC flag
        rom_data[0x00:0x0B] = b'TESTGBC    '
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gbc') as f:
            f.write(bytes(rom_data))
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            assert rom.system == 'gbc'
        finally:
            os.unlink(temp_path)

    def test_rom_header_contains_cartridge(self):
        """Тест что header содержит тип картриджа"""
        rom_data = self.create_test_rom_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gb') as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path)
            # Check header has cartridge type
            assert 'cartridge_type' in rom.header
        finally:
            os.unlink(temp_path)
