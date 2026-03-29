"""
Тесты для валидации ROM файлов
"""

import pytest
import tempfile
import os
from core.rom import validate_rom_file, GameBoyROM


class TestROMValidation:
    """Тесты функции validate_rom_file"""
    
    def test_valid_gb_file(self):
        """Тест с валидным GB файлом"""
        # Создаём файл 32KB с расширением .gb
        with tempfile.NamedTemporaryFile(suffix='.gb', delete=False) as f:
            f.write(b'\x00' * 0x8000)
            temp_path = f.name
        
        try:
            result = validate_rom_file(temp_path)
            assert result is None  # Нет ошибки - валидный файл
        finally:
            os.unlink(temp_path)
    
    def test_valid_gbc_file(self):
        """Тест с валидным GBC файлом"""
        with tempfile.NamedTemporaryFile(suffix='.gbc', delete=False) as f:
            f.write(b'\x00' * 0x8000)
            temp_path = f.name
        
        try:
            result = validate_rom_file(temp_path)
            assert result is None
        finally:
            os.unlink(temp_path)
    
    def test_valid_gba_file(self):
        """Тест с валидным GBA файлом"""
        with tempfile.NamedTemporaryFile(suffix='.gba', delete=False) as f:
            f.write(b'\x00' * 0x8000)
            temp_path = f.name
        
        try:
            result = validate_rom_file(temp_path)
            assert result is None
        finally:
            os.unlink(temp_path)
    
    def test_invalid_extension(self):
        """Тест с неверным расширением"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'\x00' * 0x8000)
            temp_path = f.name
        
        try:
            result = validate_rom_file(temp_path)
            assert result is not None
            assert '.gb' in result or '.gbc' in result or '.gba' in result
        finally:
            os.unlink(temp_path)
    
    def test_no_extension(self):
        """Тест без расширения"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * 0x8000)
            temp_path = f.name
        
        try:
            result = validate_rom_file(temp_path)
            assert result is not None
        finally:
            os.unlink(temp_path)
    
    def test_file_too_small(self):
        """Тест с слишком маленьким файлом"""
        with tempfile.NamedTemporaryFile(suffix='.gb', delete=False) as f:
            f.write(b'\x00' * 1000)  # Меньше 32KB
            temp_path = f.name
        
        try:
            result = validate_rom_file(temp_path)
            assert result is not None
            assert 'слишком маленький' in result or 'минимум' in result
        finally:
            os.unlink(temp_path)
    
    def test_nonexistent_file(self):
        """Тест с несуществующим файлом"""
        result = validate_rom_file('/nonexistent/path/rom.gb')
        assert result is not None
        assert 'не существует' in result
    
    def test_gameboyrom_with_validation(self):
        """Тест GameBoyROM с включённой валидацией"""
        # Валидный файл
        with tempfile.NamedTemporaryFile(suffix='.gb', delete=False) as f:
            f.write(b'\x00' * 0x8000)
            temp_path = f.name
        
        try:
            rom = GameBoyROM(temp_path, validate=True)
            assert len(rom.data) == 0x8000
        finally:
            os.unlink(temp_path)
    
    def test_gameboyrom_validation_error(self):
        """Тест GameBoyROM с ошибкой валидации"""
        # Невалидный файл
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'\x00' * 0x8000)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError) as exc_info:
                GameBoyROM(temp_path, validate=True)
            assert '.gb' in str(exc_info.value) or '.gbc' in str(exc_info.value)
        finally:
            os.unlink(temp_path)
