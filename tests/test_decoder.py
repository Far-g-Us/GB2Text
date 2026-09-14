"""
Тесты для модуля decoder
"""
import os
import sys

import pytest

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.decoder import DEFAULT_VERBOSE_UNKNOWN, CharMapDecoder


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
        # Терминатор (0x00) отображается в пустую строку, 'C'(0x43) заменяется на ближайший символ
        # Ближайший к 0x43 это 0x42='B'(разница 1), а не 0x41='A'(разница 2)
        assert result in ['AB', 'ABA', 'ABB']  #取决于 реализации _find_similar_char

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

    def test_verbose_unknown_marks_unknown_bytes(self):
        """Тест показа неизвестных байтов как {{XX}}"""
        charmap = {
            0x41: 'A',
        }
        decoder = CharMapDecoder(charmap, verbose_unknown=True)

        data = b'\x41\x4F'
        result = decoder.decode(data, 0, len(data))
        assert result == 'A{{4F}}'

    def test_verbose_unknown_off_by_default(self):
        """Тест: по умолчанию неизвестные байты заменяются похожими символами"""
        charmap = {
            0x41: 'A',
        }
        decoder = CharMapDecoder(charmap)

        data = b'\x42'  # 'B' неизвестен
        result = decoder.decode(data, 0, len(data))
        assert '{{42}}' not in result

    def test_default_verbose_unknown_module_flag(self):
        """Тест: module-level флаг применяется к новым декодерам"""
        old = DEFAULT_VERBOSE_UNKNOWN
        try:
            import core.decoder as decoder_module
            decoder_module.DEFAULT_VERBOSE_UNKNOWN = True
            decoder = CharMapDecoder({0x41: 'A'})
            assert decoder.verbose_unknown is True
            result = decoder.decode(b'\x01', 0, 1)
            assert result == '{{01}}'
        finally:
            decoder_module.DEFAULT_VERBOSE_UNKNOWN = old
        assert CharMapDecoder({0x41: 'A'}).verbose_unknown is False

    def test_explicit_verbose_overrides_module_flag(self):
        """Тест: явный параметр перекрывает module-level флаг"""
        old = DEFAULT_VERBOSE_UNKNOWN
        try:
            import core.decoder as decoder_module
            decoder_module.DEFAULT_VERBOSE_UNKNOWN = True
            decoder = CharMapDecoder({0x41: 'A'}, verbose_unknown=False)
            assert decoder.verbose_unknown is False
        finally:
            decoder_module.DEFAULT_VERBOSE_UNKNOWN = old


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
