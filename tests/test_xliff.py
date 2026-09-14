"""
Tests for XLIFF 1.2 functionality (CAT import/export)
"""

import xml.etree.ElementTree as ET

import pytest

from core.xliff import XLIFFHandler


def _local(tag: str) -> str:
    """Локальное имя тега без namespace."""
    return tag.split("}")[-1]


def _files(root: ET.Element) -> list[ET.Element]:
    return [e for e in root if _local(e.tag) == "file"]


def _body(file_elem: ET.Element) -> ET.Element:
    return next(e for e in file_elem if _local(e.tag) == "body")


def _units(body: ET.Element) -> list[ET.Element]:
    return [e for e in body if _local(e.tag) == "trans-unit"]


def _child(elem: ET.Element, name: str) -> ET.Element | None:
    for child in elem:
        if _local(child.tag) == name:
            return child
    return None


def _children(elem: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in elem if _local(child.tag) == name]


class TestXLIFFHandler:

    def test_export_xliff_basic(self):
        """Базовый экспорт в XLIFF."""
        handler = XLIFFHandler()
        results = {
            "main_text": [
                {"text": "Hello world", "offset": 0x1000}
            ]
        }

        content = handler.export_xliff(results, "en", "ru", "Test Game")

        root = ET.fromstring(content)
        # Может быть с namespace или без — проверяем локальное имя
        assert _local(root.tag) == "xliff"
        assert root.get("version") == "1.2"

        file_elem = _files(root)[0]
        assert file_elem.get("original") == "main_text"
        assert file_elem.get("source_language") == "en"
        assert file_elem.get("target_language") == "ru"

        trans_units = _units(_body(file_elem))
        assert len(trans_units) == 1

        tu = trans_units[0]
        assert tu.get("id") == "0"
        assert _child(tu, "source").text == "Hello world"
        # Пустой target с state="new"
        target = _child(tu, "target")
        assert target is not None
        assert target.get("state") == "new"
        # offset сохраняется в note
        note = _child(tu, "note")
        assert note is not None
        assert "0x1000" in note.text

    def test_export_xliff_multiple_segments(self):
        """Множественные сегменты и сообщения."""
        handler = XLIFFHandler()
        results = {
            "dialog": [{"text": "First"}],
            "menu": [{"text": "New Game"}, {"text": "Load Game"}],
        }

        content = handler.export_xliff(results, "en", "ru")
        root = ET.fromstring(content)

        files = _files(root)
        assert len(files) == 2

        menu_file = next(f for f in files if f.get("original") == "menu")
        menu_units = _units(_body(menu_file))
        assert [_child(u, "source").text for u in menu_units] == ["New Game", "Load Game"]
        assert [u.get("id") for u in menu_units] == ["0", "1"]

    def test_export_xliff_skips_empty_text(self):
        """Пустые строки не попадают в XLIFF."""
        handler = XLIFFHandler()
        results = {
            "seg": [
                {"text": "Real"},
                {"text": ""},
                {"text": "   "},
            ]
        }
        content = handler.export_xliff(results, "en", "ru")
        root = ET.fromstring(content)
        file_elem = _files(root)[0]
        units = _units(_body(file_elem))
        assert [_child(u, "source").text for u in units] == ["Real"]

    def test_export_xliff_special_characters(self):
        """XML-спецсимволы корректно экранируются и восстанавливаются."""
        handler = XLIFFHandler()
        results = {
            "seg": [{"text": 'Use <b> and & for "quotes"'}]
        }
        content = handler.export_xliff(results, "en", "ru")

        # В сыром XML не должно быть сырых спецсимволов
        assert "<b>" not in content
        assert "& " not in content.replace('&amp;', '')

        root = ET.fromstring(content)
        source = _child(_units(_body(_files(root)[0]))[0], "source")
        assert source.text == 'Use <b> and & for "quotes"'

    def test_import_xliff_roundtrip(self):
        """Экспорт -> заполнение target -> импорт сохраняет текст и индексы."""
        handler = XLIFFHandler()
        results = {
            "dialog": [{"text": "Hello"}, {"text": "Goodbye"}],
            "menu": [{"text": "Continue"}],
        }

        content = handler.export_xliff(results, "en", "ru")
        translated = (
            content
            .replace('<xliff:target state="new"/>', '<xliff:target state="translated">Привет</xliff:target>')
            .replace('Goodbye</xliff:source>', 'Goodbye</xliff:source>\n        <xliff:target state="translated">Пока</xliff:target>', 1)
            .replace('Continue</xliff:source>', 'Continue</xliff:source>\n        <xliff:target state="translated">Продолжить</xliff:target>', 1)
        )

        imported = handler.import_xliff(translated)

        assert imported["dialog"] == {0: "Привет", 1: "Пока"}
        assert imported["menu"] == {0: "Продолжить"}

    def test_import_xliff_replaces_target(self):
        """Импорт берёт target, а НЕ source, если они различаются."""
        handler = XLIFFHandler()
        content = """<?xml version="1.0" encoding="utf-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="seg1" source_language="en" target_language="ru">
    <body>
      <trans-unit id="0">
        <source>Hello</source>
        <target state="translated">Здравствуйте</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        imported = handler.import_xliff(content)
        assert imported == {"seg1": {0: "Здравствуйте"}}

    def test_import_xliff_skips_empty_target(self):
        """Пустые target пропускаются при импорте."""
        handler = XLIFFHandler()
        content = """<?xml version="1.0" encoding="utf-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="seg" source_language="en" target_language="ru">
    <body>
      <trans-unit id="0"><source>Hello</source><target state="new"></target></trans-unit>
      <trans-unit id="1"><source>World</source><target state="translated">Мир</target></trans-unit>
    </body>
  </file>
</xliff>"""
        imported = handler.import_xliff(content)
        assert imported == {"seg": {1: "Мир"}}

    def test_import_xliff_inline_tags(self):
        """Inline-разметка CAT-инструментов схлопывается в текст."""
        handler = XLIFFHandler()
        content = """<?xml version="1.0" encoding="utf-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="dialog" source_language="en" target_language="ru">
    <body>
      <trans-unit id="0">
        <source>Hi <g>there</g></source>
        <target>Привет <g>там</g></target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        imported = handler.import_xliff(content)
        assert imported == {"dialog": {0: "Привет там"}}

    def test_import_xliff_invalid_root(self):
        """Не-XLIFF XML отклоняется с ValueError."""
        handler = XLIFFHandler()
        with pytest.raises(ValueError):
            handler.import_xliff("""<not-xliff><body>bad</body></not-xliff>""")

    def test_import_xliff_invalid_xml(self):
        """Битые XML отклоняются с ValueError."""
        handler = XLIFFHandler()
        with pytest.raises(ValueError):
            handler.import_xliff("<xliff><file></file>")

    def test_import_xliff_non_namespaced(self):
        """Принимает XLIFF без namespace (его генерируют некоторые CAT)."""
        handler = XLIFFHandler()
        content = """<?xml version="1.0" encoding="utf-8"?>
<xliff version="1.2">
  <file original="menu" source_language="en" target_language="ru">
    <body>
      <trans-unit id="0">
        <source>Start</source>
        <target>Начать</target>
      </trans-unit>
    </body>
  </file>
</xliff>"""
        imported = handler.import_xliff(content)
        assert imported == {"menu": {0: "Начать"}}

    def test_roundtrip_preserves_offsets(self):
        """offsets сохраняются в note и привязываются через id — раунд-трип корректен."""
        handler = XLIFFHandler()
        results = {
            "dialog": [
                {"text": "Hello", "offset": 0x1234},
                {"text": "World", "offset": 0xABCD},
            ]
        }
        content = handler.export_xliff(results, "en", "ru")
        root = ET.fromstring(content)
        notes = [_child(tu, "note").text for tu in _units(_body(_files(root)[0]))]
        assert notes == ["rom-offset: 0x1234", "rom-offset: 0xABCD"]

    def test_apply_translations_mapping_by_index(self):
        """Маппинг импортированных переводов на current_results по индексу.

        Используется GUI import_xliff через XLIFFHandler.apply_translations:
        перевод попадает в msg['translation'] по позиции trans-unit в
        сегменте (id = позиция до фильтрации пустых), «дырявые» индексы
        маппятся корректно.
        """
        handler = XLIFFHandler()
        # current_results как в GUI после extraction
        current_results = {
            "dialog": [
                {"text": "Hello", "offset": 0x1000},
                {"text": "  ", "offset": 0x1004},   # пустой — в XLIFF не попадёт
                {"text": "World", "offset": 0x1008},
            ],
            "menu": [
                {"text": "Continue", "offset": 0x2000},
            ],
        }

        content = handler.export_xliff(dict(current_results), "en", "ru")
        root = ET.fromstring(content)
        for file_elem in _files(root):
            name = file_elem.get("original")
            ids = [u.get("id") for u in _units(_body(file_elem))]
            if name == "dialog":
                assert ids == ["0", "2"], f"Ожидались id исходных позиций, получено {ids}"
            else:
                assert ids == ["0"]

        # Имитируем выполненный CAT-перевод (заполняем targets)
        translated = (
            content
            .replace('<xliff:target state="new"/>', '<xliff:target state="translated">Привет</xliff:target>')
            .replace('World</xliff:source>', 'World</xliff:source>\n        <xliff:target state="translated">Мир</xliff:target>', 1)
            .replace('Continue</xliff:source>', 'Continue</xliff:source>\n        <xliff:target state="translated">Продолжить</xliff:target>', 1)
        )
        imported = handler.import_xliff(translated)
        assert imported["dialog"] == {0: "Привет", 2: "Мир"}

        applied_count = XLIFFHandler.apply_translations(current_results, imported)

        assert current_results["dialog"][0]["translation"] == "Привет"
        assert "translation" not in current_results["dialog"][1]  # пустой text
        assert current_results["dialog"][2]["translation"] == "Мир"
        assert current_results["menu"][0]["translation"] == "Продолжить"
        assert applied_count == 3

    def test_apply_translations_skips_unchanged(self):
        """Уже применённый перевод не перезаписывается и не считается."""
        handler = XLIFFHandler()
        current_results = {
            "dialog": [
                {"text": "Hello", "translation": "Привет"},
                {"text": "World"},
            ]
        }
        content = handler.export_xliff(dict(current_results), "en", "ru")
        translated = (
            content
            .replace('<xliff:target state="new"/>', '<xliff:target state="translated">Привет</xliff:target>')
            .replace('World</xliff:source>', 'World</xliff:source>\n        <xliff:target state="translated">Мир</xliff:target>', 1)
        )
        imported = handler.import_xliff(translated)

        applied_count = XLIFFHandler.apply_translations(current_results, imported)

        # «Привет» уже стоял — пропущен, изменился только World
        assert applied_count == 1
        assert current_results["dialog"][1]["translation"] == "Мир"

    def test_import_xliff_skips_bad_id(self):
        """trans-unit без числового id не маппится в 0, а пропускается.

        Предотвращает молчаливое схлопывание всех переводов в index=0.
        """
        handler = XLIFFHandler()
        content = """<?xml version="1.0" encoding="UTF-8"?>
<xliff xmlns="urn:oasis:names:tc:xliff:document:1.2" version="1.2">
  <file original="dialog"><body>
    <trans-unit id="1"><source>Hello</source><target>Привет</target></trans-unit>
    <trans-unit><source>World</source><target>Мир</target></trans-unit>
    <trans-unit id="2"><source>Foo</source><target>Бар</target></trans-unit>
  </body></file>
</xliff>"""
        imported = handler.import_xliff(content)
        assert imported == {"dialog": {1: "Привет", 2: "Бар"}}
