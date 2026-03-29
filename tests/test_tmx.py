"""
Tests for TMX functionality
"""

import pytest
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

        assert "<tmx version=\"1.4\">" in tmx_content
        assert "Hello world" in tmx_content
        assert "Привет мир" in tmx_content
        assert "Test Game" in tmx_content
        assert "0x1000" in tmx_content

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

        assert tmx_content.count("<tu>") == 3  # 3 translation units
        assert "segment1" in tmx_content
        assert "segment2" in tmx_content

    def test_export_tmx_empty_translation(self):
        """Test TMX export skips empty translations"""
        handler = TMXHandler()

        results = {
            "main_text": [
                {"text": "Hello", "translation": "Привет", "offset": 0x1000},
                {"text": "World", "translation": "", "offset": 0x1005},  # Empty translation
                {"text": "", "translation": "Мир", "offset": 0x1010}  # Empty text
            ]
        }

        tmx_content = handler.export_tmx(results, "en", "ru")

        # Should only contain the first entry
        assert tmx_content.count("<tu>") == 1
        assert "Hello" in tmx_content
        assert "Привет" in tmx_content

    def test_import_tmx_basic(self):
        """Test basic TMX import"""
        handler = TMXHandler()

        tmx_content = """<?xml version="1.0" encoding="utf-8"?>
<tmx version="1.4">
  <header creationtool="GB2Text" creationtoolversion="1.0" datatype="plaintext" segtype="sentence" adminlang="en" srclang="en"/>
  <body>
    <tu>
      <prop type="segment-name">main_text</prop>
      <prop type="rom-offset">0x1000</prop>
      <tuv xml:lang="en"><seg>Hello world</seg></tuv>
      <tuv xml:lang="ru"><seg>Привет мир</seg></tuv>
    </tu>
  </body>
</tmx>"""

        translations = handler.import_tmx(tmx_content)

        assert "main_text" in translations
        assert 0x1000 in translations["main_text"]
        assert translations["main_text"][0x1000] == "Привет мир"

    def test_import_tmx_without_offset(self):
        """Test TMX import without ROM offset"""
        handler = TMXHandler()

        tmx_content = """<?xml version="1.0" encoding="utf-8"?>
<tmx version="1.4">
  <body>
    <tu>
      <prop type="segment-name">main_text</prop>
      <tuv xml:lang="en"><seg>Hello</seg></tuv>
      <tuv xml:lang="ru"><seg>Привет</seg></tuv>
    </tu>
  </body>
</tmx>"""

        translations = handler.import_tmx(tmx_content)

        assert "main_text" in translations
        # Should have hash-based key since no offset
        assert len(translations["main_text"]) == 1

    def test_import_tmx_invalid_xml(self):
        """Test TMX import with invalid XML"""
        handler = TMXHandler()

        with pytest.raises(ValueError, match="Неверный формат TMX файла"):
            handler.import_tmx("invalid xml content")

    def test_get_tmx_info(self):
        """Test getting TMX file information"""
        handler = TMXHandler()

        tmx_content = """<?xml version="1.0" encoding="utf-8"?>
<tmx version="1.4">
  <header creationtool="TestTool" srclang="en"/>
  <body>
    <tu></tu>
    <tu></tu>
  </body>
</tmx>"""

        info = handler.get_tmx_info(tmx_content)

        assert info["version"] == "1.4"
        assert info["creation_tool"] == "TestTool"
        assert info["source_lang"] == "en"
        assert info["tu_count"] == 2

    def test_escape_xml_chars(self):
        """Test XML character escaping"""
        handler = TMXHandler()

        test_text = 'Text with <tags> & "quotes"'
        escaped = handler._escape_xml_chars(test_text)

        # Проверяем что спецсимволы заменены на XML-сущности
        expected = 'Text with &lt;tags&gt; &amp; &quot;quotes&quot;'
        assert escaped == expected, f"Expected:\n{expected}\nGot:\n{escaped}"

        # Test edge cases
        assert handler._escape_xml_chars('<>&"\'') == '&lt;&gt;&amp;&quot;&apos;'
        assert handler._escape_xml_chars('normal text') == 'normal text'
        assert handler._escape_xml_chars('') == ''

        # Дополнительно: убедимся что & экранируется первым
        # (иначе &lt; превратится в &amp;lt;)
        assert handler._escape_xml_chars('already &amp; escaped') == 'already &amp;amp; escaped'