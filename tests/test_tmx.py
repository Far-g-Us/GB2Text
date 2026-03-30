"""
Tests for TMX functionality
"""

import pytest
import xml.etree.ElementTree as ET
from core.tmx import TMXHandler


class TestTMXHandler:

    def test_export_tmx_basic(self):
        """Test basic TMX export"""
        handler = TMXHandler()

        results = {
            "main_text": [
                {
                    "text": "Hello world",
                    "translation": "Привет мир",
                    "offset": 0x1000
                }
            ]
        }

        tmx_content = handler.export_tmx(results, "en", "ru", "Test Game")

        # Проверяем что результат — валидный XML
        root = ET.fromstring(tmx_content)
        assert root.tag == "tmx"
        assert root.get("version") == "1.4"

        # Проверяем header
        header = root.find("header")
        assert header is not None
        assert header.get("creationtool") == "GB2Text"
        assert header.get("srclang") == "en"

        # Проверяем body
        body = root.find("body")
        assert body is not None

        tus = body.findall("tu")
        assert len(tus) == 1

        tu = tus[0]

        # Проверяем properties
        props = {p.get("type"): p.text for p in tu.findall("prop")}
        assert props.get("game-title") == "Test Game"
        assert props.get("segment-name") == "main_text"
        assert props.get("rom-offset") == "0x1000"

        # Проверяем tuv элементы
        tuvs = tu.findall("tuv")
        assert len(tuvs) == 2

        # Проверяем тексты в seg элементах
        seg_texts = []
        for tuv in tuvs:
            seg = tuv.find("seg")
            assert seg is not None
            seg_texts.append(seg.text)

        assert "Hello world" in seg_texts
        assert "Привет мир" in seg_texts

    def test_export_tmx_multiple_entries(self):
        """Test TMX export with multiple entries"""
        handler = TMXHandler()

        results = {
            "segment1": [
                {"text": "Hello", "translation": "Привет", "offset": 0x1000},
                {"text": "World", "translation": "Мир", "offset": 0x1005}
            ],
            "segment2": [
                {"text": "Test", "translation": "Тест", "offset": 0x2000}
            ]
        }

        tmx_content = handler.export_tmx(results, "en", "ru")

        # Парсим как XML для надёжной проверки
        root = ET.fromstring(tmx_content)
        tus = root.findall(".//tu")
        assert len(tus) == 3  # 3 translation units

        # Проверяем что оба сегмента присутствуют
        segment_names = set()
        for tu in tus:
            for prop in tu.findall("prop"):
                if prop.get("type") == "segment-name":
                    segment_names.add(prop.text)

        assert "segment1" in segment_names
        assert "segment2" in segment_names

    def test_export_tmx_empty_translation(self):
        """Test TMX export skips empty translations"""
        handler = TMXHandler()

        results = {
            "main_text": [
                {"text": "Hello", "translation": "Привет", "offset": 0x1000},
                {"text": "World", "translation": "", "offset": 0x1005},  # Empty translation
                {"text": "", "translation": "Мир", "offset": 0x1010}     # Empty text
            ]
        }

        tmx_content = handler.export_tmx(results, "en", "ru")

        root = ET.fromstring(tmx_content)
        tus = root.findall(".//tu")

        # Should only contain the first entry
        assert len(tus) == 1

        # Проверяем что это именно первая запись
        seg_texts = [seg.text for seg in root.findall(".//seg") if seg.text]
        assert "Hello" in seg_texts
        assert "Привет" in seg_texts

    def test_export_tmx_special_characters(self):
        """Test TMX export handles special XML characters correctly"""
        handler = TMXHandler()

        results = {
            "main_text": [
                {
                    "text": 'Text with <tags> & "quotes" and \'apostrophes\'',
                    "translation": "Текст с <тегами> & \"кавычками\"",
                    "offset": 0x1000
                }
            ]
        }

        tmx_content = handler.export_tmx(results, "en", "ru")

        # Должен быть валидным XML (не упадёт при парсинге)
        root = ET.fromstring(tmx_content)

        # ElementTree при парсинге автоматически деэкранирует,
        # поэтому seg.text должен содержать оригинальный текст
        segs = root.findall(".//seg")
        seg_texts = [seg.text for seg in segs if seg.text]

        assert 'Text with <tags> & "quotes" and \'apostrophes\'' in seg_texts
        assert "Текст с <тегами> & \"кавычками\"" in seg_texts

    def test_import_tmx_basic(self):
        """Test basic TMX import"""
        handler = TMXHandler()

        tmx_content = '<?xml version="1.0" encoding="utf-8"?>\n'
        tmx_content += '<tmx version="1.4">\n'
        tmx_content += '  <header creationtool="GB2Text" srclang="en"/>\n'
        tmx_content += '  <body>\n'
        tmx_content += '    <tu>\n'
        tmx_content += '      <prop type="segment-name">main_text</prop>\n'
        tmx_content += '      <prop type="rom-offset">0x1000</prop>\n'
        tmx_content += '      <tuv xml:lang="en"><seg>Hello world</seg></tuv>\n'
        tmx_content += '      <tuv xml:lang="ru"><seg>Привет мир</seg></tuv>\n'
        tmx_content += '    </tu>\n'
        tmx_content += '  </body>\n'
        tmx_content += '</tmx>'

        translations = handler.import_tmx(tmx_content)

        assert "main_text" in translations
        assert 0x1000 in translations["main_text"]
        assert translations["main_text"][0x1000] == "Привет мир"

    def test_import_tmx_without_offset(self):
        """Test TMX import without ROM offset"""
        handler = TMXHandler()

        tmx_content = '<?xml version="1.0" encoding="utf-8"?>\n'
        tmx_content += '<tmx version="1.4">\n'
        tmx_content += '  <body>\n'
        tmx_content += '    <tu>\n'
        tmx_content += '      <prop type="segment-name">main_text</prop>\n'
        tmx_content += '      <tuv xml:lang="en"><seg>Hello</seg></tuv>\n'
        tmx_content += '      <tuv xml:lang="ru"><seg>Привет</seg></tuv>\n'
        tmx_content += '    </tu>\n'
        tmx_content += '  </body>\n'
        tmx_content += '</tmx>'

        translations = handler.import_tmx(tmx_content)

        assert "main_text" in translations
        # Should have hash-based key since no offset
        assert len(translations["main_text"]) == 1
        # Значение перевода должно быть правильным
        values = list(translations["main_text"].values())
        assert values[0] == "Привет"

    def test_import_tmx_multiple_segments(self):
        """Test TMX import with multiple segments"""
        handler = TMXHandler()

        tmx_content = '<?xml version="1.0" encoding="utf-8"?>\n'
        tmx_content += '<tmx version="1.4">\n'
        tmx_content += '  <body>\n'
        tmx_content += '    <tu>\n'
        tmx_content += '      <prop type="segment-name">seg1</prop>\n'
        tmx_content += '      <prop type="rom-offset">0x100</prop>\n'
        tmx_content += '      <tuv xml:lang="en"><seg>Hello</seg></tuv>\n'
        tmx_content += '      <tuv xml:lang="ru"><seg>Привет</seg></tuv>\n'
        tmx_content += '    </tu>\n'
        tmx_content += '    <tu>\n'
        tmx_content += '      <prop type="segment-name">seg2</prop>\n'
        tmx_content += '      <prop type="rom-offset">0x200</prop>\n'
        tmx_content += '      <tuv xml:lang="en"><seg>World</seg></tuv>\n'
        tmx_content += '      <tuv xml:lang="ru"><seg>Мир</seg></tuv>\n'
        tmx_content += '    </tu>\n'
        tmx_content += '  </body>\n'
        tmx_content += '</tmx>'

        translations = handler.import_tmx(tmx_content)

        assert "seg1" in translations
        assert "seg2" in translations
        assert translations["seg1"][0x100] == "Привет"
        assert translations["seg2"][0x200] == "Мир"

    def test_import_tmx_invalid_xml(self):
        """Test TMX import with invalid XML"""
        handler = TMXHandler()

        with pytest.raises(ValueError, match="Неверный формат TMX"):
            handler.import_tmx("this is not xml at all <<<>>>")

    def test_import_tmx_not_tmx(self):
        """Test TMX import with valid XML but not TMX"""
        handler = TMXHandler()

        with pytest.raises(ValueError, match="Неверный формат TMX"):
            handler.import_tmx('<?xml version="1.0"?><root><item/></root>')

    def test_import_tmx_no_body(self):
        """Test TMX import without body element"""
        handler = TMXHandler()

        with pytest.raises(ValueError, match="не содержит"):
            handler.import_tmx('<?xml version="1.0"?><tmx version="1.4"><header/></tmx>')

    def test_get_tmx_info(self):
        """Test getting TMX file information"""
        handler = TMXHandler()

        tmx_content = '<?xml version="1.0" encoding="utf-8"?>\n'
        tmx_content += '<tmx version="1.4">\n'
        tmx_content += '  <header creationtool="TestTool" srclang="en"/>\n'
        tmx_content += '  <body>\n'
        tmx_content += '    <tu>\n'
        tmx_content += '      <tuv xml:lang="en"><seg>A</seg></tuv>\n'
        tmx_content += '      <tuv xml:lang="ru"><seg>Б</seg></tuv>\n'
        tmx_content += '    </tu>\n'
        tmx_content += '    <tu>\n'
        tmx_content += '      <tuv xml:lang="en"><seg>C</seg></tuv>\n'
        tmx_content += '      <tuv xml:lang="ru"><seg>В</seg></tuv>\n'
        tmx_content += '    </tu>\n'
        tmx_content += '  </body>\n'
        tmx_content += '</tmx>'

        info = handler.get_tmx_info(tmx_content)

        assert info["version"] == "1.4"
        assert info["creation_tool"] == "TestTool"
        assert info["source_lang"] == "en"
        assert info["tu_count"] == 2

    def test_get_tmx_info_invalid(self):
        """Test getting info from invalid TMX"""
        handler = TMXHandler()

        info = handler.get_tmx_info("not xml")
        assert info["tu_count"] == 0
        assert "error" in info

    def test_escape_xml_chars(self):
        """Test XML character escaping"""
        handler = TMXHandler()

        # Тест базового экранирования
        test_text = 'Text with <tags> & "quotes"'
        escaped = handler._escape_xml_chars(test_text)

        # Проверяем что спецсимволы заменены на XML-сущности
        assert '&lt;' in escaped, f"Expected &lt; in: {repr(escaped)}"
        assert '&gt;' in escaped, f"Expected &gt; in: {repr(escaped)}"
        assert '&amp;' in escaped, f"Expected &amp; in: {repr(escaped)}"
        assert '&quot;' in escaped, f"Expected &quot; in: {repr(escaped)}"

        # Проверяем конкретные значения через repr для однозначности
        assert repr(escaped) == repr('Text with &lt;tags&gt; &amp; &quot;quotes&quot;')

        # Test edge cases
        escaped_all = handler._escape_xml_chars('<>&"\'')
        assert repr(escaped_all) == repr('&lt;&gt;&amp;&quot;&apos;')

        assert handler._escape_xml_chars('normal text') == 'normal text'
        assert handler._escape_xml_chars('') == ''

    def test_roundtrip_export_import(self):
        """Test that export -> import preserves data (круговой тест)"""
        handler = TMXHandler()

        # Исходные данные
        original_results = {
            "dialogue": [
                {"text": "Hello hero!", "translation": "Привет герой!", "offset": 0x100},
                {"text": "Save the world", "translation": "Спаси мир", "offset": 0x200},
            ],
            "menu": [
                {"text": "Start", "translation": "Начать", "offset": 0x300},
            ]
        }

        # Экспорт
        tmx_content = handler.export_tmx(original_results, "en", "ru", "Test Game")

        # Проверяем что экспорт — валидный XML
        assert tmx_content is not None
        assert len(tmx_content) > 0

        # Импорт обратно
        imported = handler.import_tmx(tmx_content)

        # Проверяем что все сегменты на месте
        assert "dialogue" in imported
        assert "menu" in imported

        # Проверяем переводы
        assert imported["dialogue"][0x100] == "Привет герой!"
        assert imported["dialogue"][0x200] == "Спаси мир"
        assert imported["menu"][0x300] == "Начать"

    def test_roundtrip_special_characters(self):
        """Test roundtrip with special XML characters"""
        handler = TMXHandler()

        original_results = {
            "text": [
                {
                    "text": 'Use <A> & <B> to "jump"',
                    "translation": "Нажми <A> и <B> для \"прыжка\"",
                    "offset": 0x500
                }
            ]
        }

        # Экспорт -> Импорт
        tmx_content = handler.export_tmx(original_results, "en", "ru")
        imported = handler.import_tmx(tmx_content)

        # Спецсимволы должны сохраниться без искажений
        assert imported["text"][0x500] == "Нажми <A> и <B> для \"прыжка\""

    def test_export_no_offset(self):
        """Test export without offset field"""
        handler = TMXHandler()

        results = {
            "text": [
                {"text": "Hello", "translation": "Привет"}
                # Нет поля offset
            ]
        }

        tmx_content = handler.export_tmx(results, "en", "ru")

        root = ET.fromstring(tmx_content)

        # Не должно быть prop с type="rom-offset"
        offset_props = [p for p in root.findall(".//prop") if p.get("type") == "rom-offset"]
        assert len(offset_props) == 0

        # Но TU должен быть создан
        assert len(root.findall(".//tu")) == 1