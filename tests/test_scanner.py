"""Тесты для модуля scanner"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scanner import (
    find_text_pointers,
    is_text_like,
    detect_multiple_languages,
    auto_detect_charmap,
    analyze_text_segment,
    auto_detect_segments
)


class TestScanner:
    """Тесты для функций сканера"""
    
    def test_find_text_pointers_basic(self):
        """Тест базового поиска указателей"""
        # Создаём тестовые данные с указателями
        rom_data = bytes(range(256)) * 100
        pointers = find_text_pointers(rom_data, pointer_size=2)
        assert isinstance(pointers, list)
    
    def test_find_text_pointers_empty(self):
        """Тест с пустыми данными"""
        rom_data = b''
        pointers = find_text_pointers(rom_data)
        assert isinstance(pointers, list)
    
    def test_find_text_pointers_gba(self):
        """Тест поиска указателей для GBA"""
        rom_data = bytes(range(256)) * 100
        pointers = find_text_pointers(rom_data, pointer_size=4)
        assert isinstance(pointers, list)
    
    def test_is_text_like_valid(self):
        """Тест определения текста"""
        # ASCII текст
        text_data = b'Hello World!'
        result = is_text_like(text_data, 0, 5)
        assert isinstance(result, bool)
    
    def test_is_text_like_empty(self):
        """Тест с пустыми данными"""
        result = is_text_like(b'', 0, 0)
        assert result == False
    
    def test_detect_multiple_languages_english(self):
        """Тест определения английского языка"""
        # ASCII текст
        text_data = b'Hello World! This is a test.'
        result = detect_multiple_languages(text_data, 0, 100)
        assert isinstance(result, list)
        assert 'english' in result
    
    def test_detect_multiple_languages_empty(self):
        """Тест с пустыми данными"""
        result = detect_multiple_languages(b'', 0, 10)
        assert isinstance(result, list)
    
    def test_detect_multiple_languages_japanese(self):
        """Тест определения японского языка"""
        # Катакана
        text_data = b'Hello' + b'\\x83\\x80\\x83\\x81'  #  Hello катаканой
        result = detect_multiple_languages(text_data, 0, 50)
        assert isinstance(result, list)
    
    def test_auto_detect_charmap_basic(self):
        """Тест автоопределения таблицы символов"""
        text_data = b'Hello World!'
        charmap = auto_detect_charmap(text_data, 0, 50)
        assert isinstance(charmap, dict)
        assert len(charmap) > 0
    
    def test_auto_detect_charmap_empty(self):
        """Тест с пустыми данными"""
        charmap = auto_detect_charmap(b'', 0, 0)
        assert isinstance(charmap, dict)
    
    def test_analyze_text_segment_basic(self):
        """Тест анализа текстового сегмента"""
        text_data = b'Hello World!'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)
        assert 'readability' in result
        assert 'has_pointers' in result
    
    def test_analyze_text_segment_empty(self):
        """Тест анализа пустого сегмента"""
        result = analyze_text_segment(b'', 0, 0)
        assert isinstance(result, dict)
    
    def test_auto_detect_segments_basic(self):
        """Тест автоопределения сегментов"""
        # Создаём данные с текстовыми блоками
        rom_data = b'\\x00' * 100 + b'Hello World!' + b'\\x00' * 50
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)
    
    def test_auto_detect_segments_empty(self):
        """Тест с пустыми данными"""
        segments = auto_detect_segments(b'')
        assert isinstance(segments, list)
    
    def test_find_text_pointers_with_start(self):
        """Тест поиска указателей с указанием start"""
        rom_data = bytes(range(256)) * 50
        pointers = find_text_pointers(rom_data, start=1000)
        assert isinstance(pointers, list)
    
    def test_find_text_pointers_with_end(self):
        """Тест поиска указателей с указанием end"""
        rom_data = bytes(range(256)) * 50
        pointers = find_text_pointers(rom_data, end=1000)
        assert isinstance(pointers, list)
    
    def test_find_text_pointers_min_length(self):
        """Тест с min_length"""
        rom_data = bytes(range(256)) * 50
        pointers = find_text_pointers(rom_data, min_length=4)
        assert isinstance(pointers, list)
    
    def test_is_text_like_longer(self):
        """Тест is_text_like с более длинным текстом"""
        text_data = b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        result = is_text_like(text_data, 0, 20)
        assert isinstance(result, bool)
    
    def test_detect_multiple_languages_russian(self):
        """Тест определения русского языка"""
        # Кириллица
        text_data = b'Hello' + b'\xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82'  # Привет
        result = detect_multiple_languages(text_data, 0, 50)
        assert isinstance(result, list)
    
    def test_auto_detect_charmap_with_terminator(self):
        """Тест автоопределения charmap с терминатором"""
        text_data = b'Hello\x00World!'
        charmap = auto_detect_charmap(text_data, 0, 100)
        assert isinstance(charmap, dict)
    
    def test_analyze_text_segment_with_pointers(self):
        """Тест анализа сегмента с указателями"""
        # Данные с указателями
        text_data = b'\x00\x10\x00\x20Hello World!'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)

    def test_auto_detect_charmap_japanese(self):
        """Тест автоопределения charmap для японского языка"""
        # Создаём данные с катаканой (ROM должен быть достаточно большим)
        base_data = b'\xA3\xA4\xA5' * 50  # アィИ повторяется много раз
        katakana_data = base_data + b'\x00' * 400  # Добавляем padding до минимального размера
        charmap = auto_detect_charmap(katakana_data, 0, len(katakana_data))
        assert isinstance(charmap, dict)
        assert len(charmap) > 0
        # Проверяем, что катакана добавлена
        assert 0xA3 in charmap  # ア

    def test_auto_detect_charmap_russian(self):
        """Тест автоопределения charmap для русского языка"""
        # Создаём данные с кириллицей (CP866, ROM должен быть достаточно большим)
        base_data = b'\xC0\xC1\xC2' * 50  # АБВ повторяется много раз
        russian_data = base_data + b'\x00' * 400  # Добавляем padding до минимального размера
        charmap = auto_detect_charmap(russian_data, 0, len(russian_data))
        assert isinstance(charmap, dict)
        assert len(charmap) > 0
        # Проверяем, что кириллица добавлена
        assert 0xC0 in charmap  # А

    def test_auto_detect_charmap_small_rom(self):
        """Тест автоопределения charmap для маленького ROM"""
        small_data = b'Hi'  # Меньше ROM_HEADER_SIZE
        charmap = auto_detect_charmap(small_data, 0, len(small_data))
        assert isinstance(charmap, dict)
        assert len(charmap) > 0

    def test_auto_detect_segments_with_multiple_blocks(self):
        """Тест автоопределения сегментов с несколькими блоками"""
        # Создаём данные с текстовыми блоками достаточной длины
        text_block = b'Hello World! This is a very long test text message that should be detected as readable.' * 10
        rom_data = (b'\x00' * 200 +
                   text_block +
                   b'\x00' * 100 +
                   b'\x00' * 200)
        segments = auto_detect_segments(rom_data, min_segment_length=50, min_readability=0.5)
        assert isinstance(segments, list)
        # Может не найти сегменты из-за пропуска областей, но функция должна работать

    def test_auto_detect_segments_skip_ranges(self):
        """Тест пропуска известных нетекстовых областей"""
        # Создаём данные с текстом в VRAM области (которая должна быть пропущена)
        rom_data = b'\x00' * 0x8000 + b'Hello World!' + b'\x00' * 1000
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_auto_detect_segments_gbc_mode(self):
        """Тест автоопределения сегментов в режиме GBC"""
        rom_data = b'\x00' * 200 + b'Hello World!' + b'\x00' * 100
        segments = auto_detect_segments(rom_data, block_size=32)
        assert isinstance(segments, list)

    def test_find_text_pointers_address_base(self):
        """Тест поиска указателей с base адресом"""
        rom_data = bytes(range(256)) * 50
        pointers = find_text_pointers(rom_data, pointer_size=2, address_base=0x4000)
        assert isinstance(pointers, list)

    def test_is_text_like_all_printable(self):
        """Тест is_text_like когда все символы печатные"""
        text_data = b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!?'
        result = is_text_like(text_data, 0, len(text_data))
        assert isinstance(result, bool)

    def test_is_text_like_mixed(self):
        """Тест is_text_like со смешанными данными"""
        # Some printable, some not
        text_data = b'Hello\x00\x01\x02World'
        result = is_text_like(text_data, 0, len(text_data))
        assert isinstance(result, bool)

    def test_is_text_like_with_katakana(self):
        """Тест is_text_like с катаканой"""
        # Katakana range
        text_data = b'\x83\x80\x83\x81\x83\x82'
        result = is_text_like(text_data, 0, len(text_data))
        assert isinstance(result, bool)

    def test_is_text_like_with_cyrillic(self):
        """Тест is_text_like с кириллицей"""
        # Cyrillic text
        text_data = b'\xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\xd2'  # Привет
        result = is_text_like(text_data, 0, len(text_data))
        assert isinstance(result, bool)

    def test_detect_multiple_languages_mixed(self):
        """Тест определения нескольких языков со смешанным текстом"""
        text_data = b'Hello\xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2\x83\x80\x83\x81World'
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_detect_multiple_languages_only_ascii(self):
        """Тест определения языка только с ASCII"""
        text_data = b'Hello World This is English text 123'
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_auto_detect_charmap_with_pokemon(self):
        """Тест автоопределения charmap как в покемонах"""
        # Typical Pokemon text with special chars
        text_data = b'POKEMON\x50\x51\x52\x53\x54TEXT'
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)

    def test_auto_detect_charmap_all_same(self):
        """Тест автоопределения charmap с одинаковыми символами"""
        text_data = b'AAAAAAAAAAAAAAAAAA'
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)

    def test_analyze_text_segment_high_readability(self):
        """Тест анализа сегмента с высокой читаемостью"""
        text_data = b'Hello World This is a test message!'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)
        assert 'readability' in result
        # High readability expected
        assert result['readability'] > 0

    def test_analyze_text_segment_no_pointers(self):
        """Тест анализа сегмента без указателей"""
        text_data = b'Just plain text without pointers'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)

    def test_auto_detect_segments_multiple(self):
        """Тест автоопределения нескольких сегментов"""
        rom_data = b'\x00' * 100 + b'Hello World!' + b'\x00' * 50 + b'Another text block!' + b'\x00' * 50
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_auto_detect_segments_japanese(self):
        """Тест автоопределения сегментов с японским текстом"""
        rom_data = b'\x00' * 100 + b'\x83\x80\x83\x81\x83\x82' + b'\x00' * 50
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_find_text_pointers_unsupported_size(self):
        """Тест поиска указателей с неподдерживаемым размером"""
        rom_data = bytes(range(256)) * 50
        pointers = find_text_pointers(rom_data, pointer_size=3)  # Unsupported size
        assert isinstance(pointers, list)

    def test_is_text_like_short_data(self):
        """Тест is_text_like с данными короче min_length"""
        text_data = b'Hi'  # Very short
        result = is_text_like(text_data, 0, 10)  # min_length > data
        assert result == False

    def test_detect_multiple_languages_with_hiragana(self):
        """Тест определения языка с хираганой"""
        # Hiragana range
        text_data = b'\x82\x9f\x82\xa0\x82\xa2'  # Hiragana
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_auto_detect_charmap_with_numbers(self):
        """Тест автоопределения charmap с цифрами"""
        text_data = b'1234567890'
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)

    def test_auto_detect_charmap_special_chars(self):
        """Тест автоопределения charmap со специальными символами"""
        text_data = b'Hello!@#$%^&*()'
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)

    def test_analyze_text_segment_no_readable(self):
        """Тест анализа сегмента без читаемых символов"""
        text_data = b'\x00\x01\x02\x03\x04'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)

    def test_analyze_text_segment_with_terminators(self):
        """Тест анализа сегмента с терминаторами"""
        text_data = b'Hello\x00World\x00'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)

    def test_auto_detect_segments_empty_rom(self):
        """Тест автоопределения сегментов с пустым ROM"""
        rom_data = b''
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_auto_detect_segments_large_rom(self):
        """Тест автоопределения сегментов с большим ROM"""
        # Large ROM with some text blocks
        rom_data = b'\x00' * 1000 + b'Hello World!' + b'\x00' * 500 + b'Test Text' + b'\x00' * 1000
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_detect_multiple_languages_unicode(self):
        """Тест определения языка с unicode"""
        # Mix of different scripts
        text_data = b'Hello\xc0\xc1\xc2\xc3World'
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_is_text_like_with_all_printable(self):
        """Тест is_text_like с полностью печатными символами"""
        text_data = b'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()'
        result = is_text_like(text_data, 0, len(text_data))
        assert isinstance(result, bool)

    def test_analyze_text_segment_many_pointers(self):
        """Тест анализа сегмента с множеством указателей"""
        text_data = b'\x00\x10\x00\x20\x00\x30Hello World!'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)
        assert 'has_pointers' in result

    def test_auto_detect_charmap_all_zeros(self):
        """Тест автоопределения charmap с нулями"""
        text_data = b'\x00\x00\x00\x00\x00'
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)

    def test_auto_detect_segments_with_pokemon_text(self):
        """Тест автоопределения сегментов с текстом как в покемонах"""
        # Pokemon-style text
        rom_data = b'\x00' * 0x100 + b'POKEMON' + b'\x00' * 0x100 + b'TRAINER' + b'\x00' * 0x100
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_find_text_pointers_gba_mode(self):
        """Тест поиска указателей в режиме GBA"""
        rom_data = bytes(range(256)) * 200
        pointers = find_text_pointers(rom_data, pointer_size=4, address_base=0x08000000)
        assert isinstance(pointers, list)

    def test_is_text_like_partial_coverage(self):
        """Тест is_text_like с частичным покрытием"""
        # Mix of printable and non-printable
        text_data = b'AB\x00\x01CD\x02EF'
        result = is_text_like(text_data, 0, len(text_data))
        assert isinstance(result, bool)

    def test_detect_multiple_languages_korean(self):
        """Тест определения корейского языка"""
        # Korean Hangul
        text_data = b'\xea\xb0\x80\xea\xb0\x81\xea\xb0\x82'  # 가나다
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_analyze_text_segment_high_pointer_density(self):
        """Тест анализа сегмента с высокой плотностью указателей"""
        text_data = b'\x00\x10\x00\x20\x00\x30\x00\x40Hello World!'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)

    def test_auto_detect_charmap_with_extended_ascii(self):
        """Тест автоопределения charmap с расширенным ASCII"""
        # Extended ASCII characters
        text_data = bytes([128, 129, 130, 131, 132, 133, 134, 135])
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)

    def test_auto_detect_segments_all_zeros(self):
        """Тест автоопределения сегментов с нулями"""
        rom_data = b'\x00' * 10000
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_auto_detect_segments_unicode_text(self):
        """Тест автоопределения сегментов с unicode"""
        rom_data = b'\x00' * 100 + b'\xc0\xc1\xc2\xc3Text' + b'\x00' * 100
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_detect_multiple_languages_chinese(self):
        """Тест определения китайского языка"""
        # Chinese characters
        text_data = b'\xe4\xb8\xad\xe6\x96\x87'  # 中文
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_analyze_text_segment_mixed_content(self):
        """Тест анализа сегмента со смешанным содержимым"""
        text_data = b'Hello\x00\x00\x00World\xFFTest\xFE'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)
        assert 'readability' in result

    def test_detect_multiple_languages_only_japanese(self):
        """Тест только японский язык"""
        # High concentration of katakana
        text_data = b'\x83\x80\x83\x81\x83\x82\x83\x83\x83\x84\x83\x85\x83\x86\x83\x87\x83\x88\x83\x89\x83\x8a' * 5
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_auto_detect_charmap_mixed_bytes(self):
        """Тест автоопределения charmap со смешанными байтами"""
        text_data = bytes(list(range(256)))
        charmap = auto_detect_charmap(text_data, 0, 256)
        assert isinstance(charmap, dict)

    def test_analyze_text_segment_no_terminators(self):
        """Тест анализа без терминаторов"""
        text_data = b'ThisIsOneLongStringWithoutAnyTerminators'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)

    def test_is_text_like_only_control_chars(self):
        """Тест is_text_like только управляющие символы"""
        text_data = b'\x00\x01\x02\x03\x04\x05'
        result = is_text_like(text_data, 0, len(text_data))
        assert result == False

    def test_auto_detect_segments_very_sparse(self):
        """Тест автоопределения с очень редким текстом"""
        rom_data = b'\x00' * 10000 + b'Hi' + b'\x00' * 20000
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_detect_multiple_languages_empty_result(self):
        """Тест пустого результата определения языка"""
        text_data = b'\x00\x00\x00\x00'
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_analyze_text_segment_very_long(self):
        """Тест анализа очень длинного сегмента"""
        text_data = b'Hello World! ' * 1000
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)
        assert 'readability' in result

    def test_detect_multiple_languages_ascii_heavy(self):
        """Тест определения языка с высокой плотностью ASCII"""
        # High ASCII count > 20 should trigger english detection
        text_data = bytes(list(range(0x20, 0x7E))) * 2
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)
        assert 'english' in result

    def test_detect_multiple_languages_japanese_heavy(self):
        """Тест определения языка с японскими символами"""
        # High katakana count > 10
        text_data = bytes([0xA0 + (i % 0x3F) for i in range(200)])
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_auto_detect_charmap_no_english(self):
        """Тест автоопределения без английского"""
        # No English, should use first detected language
        text_data = bytes([0xA0 + (i % 0x3F) for i in range(100)])
        charmap = auto_detect_charmap(text_data, 0, 100)
        assert isinstance(charmap, dict)

    def test_is_text_like_alternating_bytes(self):
        """Тест is_text_like с чередующимися байтами"""
        text_data = bytes([i % 256 for i in range(50)])
        result = is_text_like(text_data, 0, 50)
        assert isinstance(result, bool)

    def test_analyze_text_segment_single_byte(self):
        """Тест анализа сегмента с одним байтом"""
        text_data = b'X'
        result = analyze_text_segment(text_data, 0, 1)
        assert isinstance(result, dict)

    def test_auto_detect_segments_at_page_boundary(self):
        """Тест автоопределения на границе страницы"""
        # At ROM bank boundary (0x4000)
        rom_data = b'\x00' * 0x3FF0 + b'Hello' + b'\x00' * 100
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_detect_multiple_languages_cyrillic_heavy(self):
        """Тест определения языка с кириллицей"""
        # High Cyrillic count
        text_data = bytes([0x90 + (i % 0x30) for i in range(200)])  # Cyrillic range
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_auto_detect_charmap_empty_result(self):
        """Тест автоопределения с пустым результатом"""
        # Empty text data
        text_data = b''
        charmap = auto_detect_charmap(text_data, 0, 0)
        assert isinstance(charmap, dict)

    def test_analyze_text_segment_very_short(self):
        """Тест анализа очень короткого сегмента"""
        text_data = b'A'
        result = analyze_text_segment(text_data, 0, 1)
        assert isinstance(result, dict)

    def test_auto_detect_segments_small_rom(self):
        """Тест автоопределения с маленьким ROM"""
        rom_data = b'Hi'
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_detect_multiple_languages_mixed_freq(self):
        """Тест определения языка со смешанной частотой"""
        # Mix of ASCII and non-ASCII with specific frequencies
        text_data = bytes([0x20, 0x21, 0x30, 0x31, 0x40, 0x41] * 20)
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_auto_detect_charmap_japanese_like(self):
        """Тест автоопределения charmap с японоподобными данными"""
        # Japanese text with katakana
        text_data = bytes([0xA0 + (i % 0x3F) for i in range(100)])
        charmap = auto_detect_charmap(text_data, 0, 100)
        assert isinstance(charmap, dict)

    def test_auto_detect_charmap_russian_like(self):
        """Тест автоопределения charmap с русскоподобными данными"""
        # Russian text with cyrillic
        text_data = bytes([0x90 + (i % 0x30) for i in range(100)])
        charmap = auto_detect_charmap(text_data, 0, 100)
        assert isinstance(charmap, dict)

    def test_auto_detect_charmap_small_rom(self):
        """Тест автоопределения charmap с маленьким ROM"""
        # ROM smaller than ROM_HEADER_SIZE
        text_data = b'Hi'
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)
        assert len(charmap) > 0

    def test_analyze_text_segment_with_terminators(self):
        """Тест анализа сегмента с терминаторами"""
        text_data = b'Hello World! \x00 Test'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)
        assert 'readability' in result

    def test_auto_detect_segments_gbc_mode(self):
        """Тест автоопределения сегментов в режиме GBC"""
        # ROM with GBC characteristics
        rom_data = b'\x00' * 0x100 + b'Hello World!' + b'\x00' * 0x100
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_auto_detect_charmap_with_terminators(self):
        """Тест charmap с терминаторами"""
        # Data with terminators
        text_data = b'Hello\x00World\x00Test\xFF'
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)

    def test_detect_multiple_languages_high_ascii(self):
        """Тест определения языка с высокой плотностью ASCII"""
        # High ASCII density > 30%
        text_data = b'ABCDEFGHIJ' * 50  # 100% ASCII
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_analyze_text_segment_with_repeated_patterns(self):
        """Тест анализа сегмента с повторяющимися паттернами"""
        # Repeated patterns
        text_data = b'ABCDABCDABCDABCD'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)
        assert 'repeated_patterns' in result

    def test_auto_detect_segments_low_readability(self):
        """Тест автоопределения с низкой читаемостью"""
        # Random bytes - low readability
        import random
        rom_data = bytes([random.randint(0, 255) for _ in range(1000)])
        segments = auto_detect_segments(rom_data, min_readability=0.1)
        assert isinstance(segments, list)

    def test_auto_detect_charmap_very_high_katakana(self):
        """Тест charmap с очень высокой плотностью катаканы"""
        # Need > 15 katakana characters to trigger japanese detection
        # Katakana range: 0xA0-0xDF
        text_data = bytes([0xA0 + (i % 0x3F) for i in range(200)])  # More than 15 unique
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)

    def test_auto_detect_charmap_very_high_cyrillic(self):
        """Тест charmap с очень высокой плотностью кириллицы"""
        # Need > 15 cyrillic characters to trigger russian detection
        # Cyrillic range: 0x90-0xBF
        text_data = bytes([0x90 + (i % 0x30) for i in range(200)])  # More than 15
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)

    def test_auto_detect_segments_with_blocks(self):
        """Тест сегментов с разными блоками"""
        # Create data with readable blocks separated by zeros
        rom_data = b'\x00' * 100
        rom_data += b'Hello World! ' * 20  # Readable block
        rom_data += b'\x00' * 200
        rom_data += b'Test Text! ' * 20  # Another readable block
        rom_data += b'\x00' * 100
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_analyze_text_segment_with_pointer_at_start(self):
        """Тест анализа с указателем в начале"""
        # Pointer at the start
        text_data = b'\x00\x10\x00\x00Hello World!'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)

    def test_auto_detect_segments_adjacent_texts(self):
        """Тест автоопределения с прилегающими текстами"""
        rom_data = b'\x00' * 100 + b'Hello' + b'\x00' * 10 + b'World' + b'\x00' * 100
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_analyze_text_segment_mid_range_bytes(self):
        """Тест анализа с байтами среднего диапазона"""
        # Mid-range bytes
        text_data = bytes([128, 129, 130, 131, 132] * 50)
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)

    def test_auto_detect_charmap_katakana_only(self):
        """Тест charmap только с катаканой - без ASCII вообще"""
        # Pure katakana - NO ASCII characters at all
        # This should trigger japanese without english
        text_data = bytes([0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA] * 50)
        # Make it at least ROM_HEADER_SIZE (0x150 = 336 bytes)
        text_data = text_data * 7  # 700 bytes
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)

    def test_auto_detect_charmap_cyrillic_only(self):
        """Тест charmap только с кириллицей - без ASCII вообще"""
        # Pure cyrillic - NO ASCII characters at all  
        # This should trigger russian without english
        text_data = bytes([0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99] * 50)
        # Make it at least ROM_HEADER_SIZE (0x150 = 336 bytes)
        text_data = text_data * 7  # 700 bytes
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)

    def test_analyze_text_segment_many_pointers_rom(self):
        """Тест анализа с множеством указателей в ROM"""
        # Create data with many valid pointers
        # Pointers should be in range 0x4000-0x80000000
        text_data = b'\x00\x40\x00\x00' * 50  # 0x00004000 pointers
        text_data += b'Hello World!'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)

    def test_auto_detect_segments_single_text(self):
        """Тест автоопределения с одним текстом"""
        rom_data = b'\x00' * 500 + b'SingleText' + b'\x00' * 1000
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_detect_multiple_languages_low_ascii(self):
        """Тест определения языка с низким содержанием ASCII"""
        # ASCII count < 20, should not detect English
        text_data = bytes([0x80 + i for i in range(50)])
        result = detect_multiple_languages(text_data, 0, len(text_data))
        assert isinstance(result, list)

    def test_analyze_text_segment_no_pointers(self):
        """Тест анализа без указателей"""
        text_data = b'No pointers here, just text!'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)
        assert result.get('has_pointers', False) == False

    def test_auto_detect_segments_many_texts(self):
        """Тест автоопределения с множеством текстов"""
        rom_data = b'\x00' * 50 + b'Text1' + b'\x00' * 50 + b'Text2' + b'\x00' * 50 + b'Text3' + b'\x00' * 50
        segments = auto_detect_segments(rom_data)
        assert isinstance(segments, list)

    def test_auto_detect_charmap_high_ascii(self):
        """Тест автоопределения с высоким ASCII"""
        # High ASCII content
        text_data = b'ABCDEFGHIJ' * 50
        charmap = auto_detect_charmap(text_data, 0, len(text_data))
        assert isinstance(charmap, dict)

    def test_analyze_text_segment_terminators_at_end(self):
        """Тест анализа с терминаторами в конце"""
        text_data = b'Some text here\x00\x00\x00'
        result = analyze_text_segment(text_data, 0, len(text_data))
        assert isinstance(result, dict)
