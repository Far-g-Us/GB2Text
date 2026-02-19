"""
Тесты для модуля decoder
"""
import pytest
import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.decoder import CharMapDecoder


class TestDecoder:
    """Тесты для CharMapDecoder"""

    def test_basic_decode(self):
        """Тест базового декодирования"""
        charmap = {
            0x41: 'A',
            0x42: 'B',
            0x43: 'C',
            0x00: '',
            0xFF: '',
        }
        decoder = CharMapDecoder(charmap)
        
        # Тест простого декодирования
        data = b'ABC'
        result = decoder.decode(data, 0, len(data))
        assert result == 'ABC'

    def test_decode_with_terminator(self):
        """Тест декодирования с терминатором"""
        charmap = {
            0x41: 'A',
            0x42: 'B',
            0x00: '',
        }
        decoder = CharMapDecoder(charmap)
        
        # Декодер не останавливается на терминаторе, а пропускает символы с пустую строку
        # Неизвестные символы могут быть заменены на похожие через _find_similar_char
        data = b'AB\x00C'
        result = decoder.decode(data, 0, len(data))
        # Терминатор (0x00) отображается в пустую строку, 'C' может стать 'A' как похожий
        assert result in ['AB', 'ABA']  #取决于 реализации _find_similar_char

    def test_encode(self):
        """Тест кодирования"""
        charmap = {
            0x41: 'A',
            0x42: 'B',
            0x20: ' ',
        }
        decoder = CharMapDecoder(charmap)
        
        # Неизвестные символы заменяются на пробел
        text = 'AB C'
        result = decoder.encode(text)
        # 'C' неизвестен и заменяется на пробел (0x20)
        assert result == b'AB  '

    def test_unknown_characters(self):
        """Тест обработки неизвестных символов"""
        charmap = {
            0x41: 'A',
        }
        decoder = CharMapDecoder(charmap)
        
        data = b'AB'  # 'B' неизвестен
        result = decoder.decode(data, 0, len(data))
        assert 'A' in result

    def test_empty_charmap(self):
        """Тест с пустым charmap"""
        decoder = CharMapDecoder({})
        
        data = b'ABC'
        result = decoder.decode(data, 0, len(data))
        assert result == ''  # Все символы неизвестны


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
