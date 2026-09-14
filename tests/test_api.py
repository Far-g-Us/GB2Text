"""Unit-тесты api._core: массинг ошибок, безопасные пути, round-trip extract→inject."""

import re

import pytest

from api import _core
from api._core import SDKError


def test_get_version():
    version = _core.get_version()
    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", version)


def test_resolve_rom_missing():
    with pytest.raises(SDKError) as exc_info:
        _core.resolve_rom("nope/no_such_rom.gb")
    assert exc_info.value.code in ("IO_ERROR", "ROM_ERROR")


def test_resolve_rom_wrong_extension(tmp_path):
    bad = tmp_path / "text.txt"
    bad.write_text("just text")
    with pytest.raises(SDKError) as exc_info:
        _core.resolve_rom(str(bad))
    assert exc_info.value.code == "UNSUPPORTED_SYSTEM"


def test_list_plugins_empty_dir(empty_plugin_dir):
    assert _core.list_plugins(empty_plugin_dir) == []


def test_list_plugins_real_dir_has_generics():
    plugins = _core.list_plugins("plugins")
    names = {p["name"] for p in plugins}
    assert {"GenericGBPlugin", "GenericGBAPlugin"}.issubset(names)


def test_detect(api_rom_file):
    result = _core.detect(api_rom_file, plugin_dir="plugins")
    assert result["game_id"] == "GB_TESTTITLEAPI"
    assert result["system"] == "gb"
    assert result["plugin"] is not None
    assert result["plugin"]["name"] in ("GenericGBPlugin", "AutoDetectPlugin")


def test_detect_plugin_not_recognized(tmp_path):
    bad = tmp_path / "test.bin"
    bad.write_bytes(b"\x00" * 0x8000)
    with pytest.raises(SDKError) as exc_info:
        _core.detect(str(bad))
    assert exc_info.value.code == "UNSUPPORTED_SYSTEM"


def test_extract_shape_and_text(api_rom_file):
    result = _core.extract(api_rom_file, plugin_dir="plugins")
    assert "segments" in result and "stats" in result
    assert result["stats"]["message_count"] >= 1
    all_text = " ".join(
        msg["text"] for msgs in result["segments"].values() for msg in msgs
    )
    assert "HELLO WORLD" in all_text


def test_resolve_output_default(tmp_path):
    rom = tmp_path / "game.gb"
    out = _core.resolve_output(str(rom))
    assert out == str(tmp_path / "game_translated.gb")


def test_resolve_output_wrong_parent(tmp_path):
    rom = tmp_path / "game.gb"
    other = tmp_path.parent / "elsewhere.gb"
    with pytest.raises(SDKError) as exc_info:
        _core.resolve_output(str(rom), str(other))
    assert exc_info.value.code == "IO_ERROR"


def test_resolve_output_same_as_rom(tmp_path):
    rom = tmp_path / "game.gb"
    with pytest.raises(SDKError) as exc_info:
        _core.resolve_output(str(rom), str(rom))
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_inject_round_trip(api_rom_file, tmp_path):
    extracted = _core.extract(api_rom_file, plugin_dir="plugins")
    translations = {
        seg_name: [
            {"translation": "HI WORLD"}
            for _ in messages
        ]
        for seg_name, messages in extracted["segments"].items()
    }
    output_path = str(tmp_path / "patched.gb")
    report = _core.inject(
        api_rom_file,
        translations,
        output_path=output_path,
        plugin_dir="plugins",
    )
    assert report["output_path"] == str((tmp_path / "patched.gb").resolve())
    assert all(status for status in report["segments"].values())

    re_extracted = _core.extract(output_path, plugin_dir="plugins")
    all_text = " ".join(
        msg["text"] for msgs in re_extracted["segments"].values() for msg in msgs
    )
    assert "HI WORLD" in all_text


def test_inject_wrong_translations_type(api_rom_file, tmp_path):
    with pytest.raises(SDKError) as exc_info:
        _core.inject(api_rom_file, ["not", "a", "dict"], plugin_dir="plugins")
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_load_json_file_valid(tmp_path):
    path = tmp_path / "tr.json"
    path.write_text('{"main_text": [{"translation": "HI"}]}', encoding="utf-8")
    data = _core.load_json_file(str(path))
    assert data == {"main_text": [{"translation": "HI"}]}


def test_load_json_file_missing(tmp_path):
    with pytest.raises(SDKError) as exc_info:
        _core.load_json_file(str(tmp_path / "nope.json"))
    assert exc_info.value.code == "IO_ERROR"


def test_load_json_file_invalid(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SDKError) as exc_info:
        _core.load_json_file(str(path))
    assert exc_info.value.code == "VALIDATION_ERROR"
