"""
Интеграционные тесты с ROM файлами из папки test_roms

Положите ROM файлы в папку test_roms для запуска этих тестов.
Поддерживаемые форматы: .gb, .gbc, .gba
"""
import os
import random
import pytest
from core.rom import GameBoyROM
from core.scanner import find_text_pointers, detect_multiple_languages
from core.database import get_pointer_size
from plugins.generic import GenericGBAPlugin
ROM_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'test_roms')


class TestROMDirectory:
    """Тесты для ROM файлов в test_roms"""
    
    @pytest.fixture
    def rom_files(self):
        """Получение списка ROM файлов"""
        if not os.path.exists(ROM_DIR):
            return []
        
        supported_extensions = ['.gb', '.gbc', '.gba']
        files = []
        for f in os.listdir(ROM_DIR):
            ext = os.path.splitext(f)[1].lower()
            if ext in supported_extensions:
                files.append(os.path.join(ROM_DIR, f))
        return files
    
    def test_rom_directory_exists(self):
        """Тест существования папки test_roms"""
        # Если папки нет - пропускаем тест
        if not os.path.exists(ROM_DIR):
            pytest.skip("Папка test_roms не существует")
        assert os.path.exists(ROM_DIR), f"Папка {ROM_DIR} не существует"
    
    def test_rom_files_available(self, rom_files):
        """Тест наличия ROM файлов для тестирования"""
        if not rom_files:
            pytest.skip("Нет ROM файлов в папке test_roms")
        
        print(f"\nНайдены ROM файлы: {[os.path.basename(f) for f in rom_files]}")
    
    def test_load_all_roms(self, rom_files):
        """Тест загрузки всех ROM файлов"""
        if not rom_files:
            pytest.skip("Нет ROM файлов в папке test_roms")
        
        for rom_path in rom_files:
            rom = GameBoyROM(rom_path)
            assert len(rom.data) > 0
            print(f"\nЗагружен: {os.path.basename(rom_path)} - система: {rom.system}")
    
    def test_gba_roms(self, rom_files):
        """Тест GBA ROM файлов"""
        gba_files = [f for f in rom_files if f.endswith('.gba')]
        if not gba_files:
            pytest.skip("Нет GBA файлов в папке test_roms")
        
        for rom_path in gba_files:
            rom = GameBoyROM(rom_path)
            assert rom.system == 'gba'
    
    def test_gb_roms(self, rom_files):
        """Тест GB ROM файлов"""
        gb_files = [f for f in rom_files if f.endswith('.gb') or f.endswith('.gbc')]
        if not gb_files:
            pytest.skip("Нет GB/GBC файлов в папке test_roms")
        
        for rom_path in gb_files:
            rom = GameBoyROM(rom_path)
            assert rom.system in ['gb', 'gbc']
    
    def test_gba_pointer_detection(self, rom_files):
        """Тест обнаружения указателей в GBA"""
        gba_files = [f for f in rom_files if f.endswith('.gba')]
        if not gba_files:
            pytest.skip("Нет GBA файлов в папке test_roms")
        
        for rom_path in gba_files:
            rom = GameBoyROM(rom_path)
            pointer_size = get_pointer_size('gba')
            pointers = find_text_pointers(rom.data, pointer_size=pointer_size)
            assert isinstance(pointers, list)
            print(f"\n{os.path.basename(rom_path)}: найдено указателей: {len(pointers)}")
    
    def test_gba_plugin_extraction(self, rom_files):
        """Тест извлечения текста плагином"""
        gba_files = [f for f in rom_files if f.endswith('.gba')]
        if not gba_files:
            pytest.skip("Нет GBA файлов в папке test_roms")
        
        for rom_path in gba_files:
            rom = GameBoyROM(rom_path)
            plugin = GenericGBAPlugin()
            segments = plugin.get_text_segments(rom)
            assert isinstance(segments, list)
            print(f"\n{os.path.basename(rom_path)}: найдено сегментов: {len(segments)}")
    
    def test_game_language_detection(self, rom_files):
        """Тест определения языка игры"""
        if not rom_files:
            pytest.skip("Нет ROM файлов в папке test_roms")
        
        for rom_path in rom_files:
            rom = GameBoyROM(rom_path)
            basename = os.path.basename(rom_path).lower()
            
            # Определяем язык по названию файла
            detected_from_name = None
            if '[ru]' in basename or '_ru' in basename or ' russia' in basename:
                detected_from_name = 'russian'
            elif '(japan)' in basename or '.jp.' in basename:
                detected_from_name = 'japanese'
            elif '(usa)' in basename or '(europe)' in basename or '.en.' in basename:
                detected_from_name = 'english'
            
            # Определяем язык по содержимому ROM
            detected_from_rom = detect_multiple_languages(rom.data[:2000])
            
            assert isinstance(detected_from_rom, list)
            assert len(detected_from_rom) > 0
            
            print(f"\n{os.path.basename(rom_path)}:")
            print(f"  - Ожидаемый язык (по имени): {detected_from_name}")
            print(f"  - Обнаруженные языки (по содержимому): {detected_from_rom}")
    
    def test_text_extraction_random(self, rom_files):
        """Тест извлечения рандомной строки текста из игры"""
        if not rom_files:
            pytest.skip("Нет ROM файлов в папке test_roms")
        
        gba_files = [f for f in rom_files if f.endswith('.gba')]
        if not gba_files:
            pytest.skip("Нет GBA файлов в папке test_roms")
        
        for rom_path in gba_files[:2]:  # Тестируем первые 2 GBA файла
            rom = GameBoyROM(rom_path)
            plugin = GenericGBAPlugin()
            segments = plugin.get_text_segments(rom)
            
            # Проверяем что есть сегменты
            assert len(segments) > 0, "Должны быть найдены сегменты текста"
            
            # Выбираем рандомный сегмент
            random.seed(42)  # Фиксируем seed для воспроизводимости
            random_segment = random.choice(segments)
            
            # Проверяем структуру сегмента
            assert 'start' in random_segment or 'address' in random_segment
            assert 'end' in random_segment
            assert 'name' in random_segment
            
            # Проверяем что сегмент имеет данные
            assert isinstance(random_segment, dict)
            assert 'end' in random_segment
            
            print(f"\n{os.path.basename(rom_path)}:")
            print(f"  - Всего сегментов: {len(segments)}")
            print(f"  - Выбранный сегмент: {random_segment.get('name', 'unknown')}")
            print(f"  - Адрес: 0x{random_segment.get('start', 0):X} - 0x{random_segment.get('end', 0):X}")
