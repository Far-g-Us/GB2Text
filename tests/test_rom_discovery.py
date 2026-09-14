"""
Автоматическое тестирование всех ROM в test_roms/
Не нужно прописывать игры — система сама находит плагин по game_id
"""
import os

import pytest

from core.plugin_manager import PluginManager
from core.rom import GameBoyROM


def find_roms():
    """Находит все .gba файлы в test_roms/"""
    roms_dir = os.path.join(os.path.dirname(__file__), '..', 'test_roms')
    if not os.path.exists(roms_dir):
        return []

    return [
        os.path.join(roms_dir, f)
        for f in os.listdir(roms_dir)
        if f.lower().endswith(('.gba', '.gbc', '.gb'))
    ]


ROM_PATHS = find_roms()


@pytest.mark.parametrize("rom_path", ROM_PATHS, ids=lambda p: os.path.basename(p))
def test_plugin_matches_rom(rom_path):
    """Проверяет что для ROM находится подходящий плагин"""
    rom = GameBoyROM(rom_path)
    pm = PluginManager()
    plugin = pm.get_plugin(rom.get_game_id(), system=rom.system)

    assert plugin is not None, f"No plugin found for {rom.get_game_id()}"
    # Проверяем что regex паттерн совпадает
    import re
    assert re.match(plugin.game_id_pattern, rom.get_game_id()), \
        f"Plugin {plugin.__class__.__name__} pattern doesn't match {rom.get_game_id()}"


@pytest.mark.parametrize("rom_path", ROM_PATHS, ids=lambda p: os.path.basename(p))
def test_extraction_returns_segments(rom_path):
    """Проверяет что извлечение возвращает непустой список сегментов"""
    rom = GameBoyROM(rom_path)
    pm = PluginManager()
    plugin = pm.get_plugin(rom.get_game_id(), system=rom.system)

    segments = plugin.get_text_segments(rom)
    assert isinstance(segments, list)
    if getattr(plugin, 'is_stub', False):
        assert len(segments) == 0, \
            f"Stub plugin {plugin.__class__.__name__} returned segments for {os.path.basename(rom_path)}"
    else:
        assert len(segments) > 0, f"No segments found for {os.path.basename(rom_path)}"


@pytest.mark.parametrize("rom_path", ROM_PATHS, ids=lambda p: os.path.basename(p))
def test_segments_have_required_keys(rom_path):
    """Проверяет структуру сегментов"""
    rom = GameBoyROM(rom_path)
    pm = PluginManager()
    plugin = pm.get_plugin(rom.get_game_id(), system=rom.system)

    segments = plugin.get_text_segments(rom)
    required_keys = {'name', 'start', 'end'}

    for seg in segments:
        assert required_keys.issubset(seg.keys()), \
            f"Segment missing keys: {required_keys - seg.keys()}"
        assert seg['start'] < seg['end'], \
            f"Invalid segment range: {seg['start']} >= {seg['end']}"
