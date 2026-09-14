"""Тесты эталонных конфигов rom_signature (П2 roadmap v1.3)."""

import json
import pathlib
from typing import Any

import pytest

from core.decoder import CharMapDecoder
from core.plugin_manager import ConfigurablePlugin, PluginManager

CONFIG_DIR = pathlib.Path(__file__).parent.parent / "plugins" / "config"

REFERENCE_CONFIGS = [
    "_reference_pokemon_gba_romhack.json",
    "_reference_fire_emblem_gba_romhack.json",
    "_reference_golden_sun_gba_romhack.json",
    "_reference_advance_wars_gba_romhack.json",
]


def _plugin_addresses() -> dict[str, dict[str, tuple[int, int]]]:
    """Реальные адреса сегментов прямо из Python-плагинов (AC1).

    Источники: gba_pokemon.py FIXED_TABLES['emerald'], gba_golden_sun.py
    константы, gba_fire_emblem.py scan range. AW-адреса взяты из ручного
    анализа ROM (плагин — заглушка, адресов в нём нет).
    """
    from plugins.gba_pokemon import FIXED_TABLES

    emerald = {
        t['name']: (t['addr'], t['addr'] + t['width'] * t['count'])
        for t in FIXED_TABLES['emerald']
    }

    from plugins.gba_golden_sun import (
        GS_DATA_FILES,
        GS_OFFSETS_BASE,
        GS_STRINGS_PTR_BASE,
        GS_TREES_BASE,
    )

    golden_sun = {
        "gs_huffman_trees": (GS_TREES_BASE, GS_OFFSETS_BASE),
        "gs_string_ptr_table": (GS_STRINGS_PTR_BASE,
                                GS_STRINGS_PTR_BASE + GS_DATA_FILES * 8),
    }

    return {
        "_reference_pokemon_gba_romhack.json": emerald,
        "_reference_fire_emblem_gba_romhack.json": {
            "fe_text_region": (0x100000, 0x400000),
        },
        "_reference_golden_sun_gba_romhack.json": golden_sun,
        "_reference_advance_wars_gba_romhack.json": {
            "mission_names": (0x80D44, 0x8162C),
        },
    }


def _load_config(fname: str) -> Any:
    return json.loads((CONFIG_DIR / fname).read_text(encoding="utf-8"))


@pytest.fixture
def pm():
    return PluginManager("plugins")


class TestReferenceConfigs:
    """Эталонные конфиги должны быть валидными и совместимыми с загрузчиком."""

    @pytest.mark.parametrize("fname", REFERENCE_CONFIGS)
    def test_reference_config_valid(self, pm, fname):
        """Каждый эталонный конфиг корректен по схеме _is_valid_config."""
        path = CONFIG_DIR / fname
        assert path.exists(), f"Отсутствует эталонный конфиг {fname}"

        config = json.loads(path.read_text(encoding="utf-8"))
        assert pm._is_valid_config(config), f"{fname} не прошёл _is_valid_config"

    @pytest.mark.parametrize("fname", REFERENCE_CONFIGS)
    def test_reference_config_not_loaded_by_default(self, fname):
        """Конфиги с префиксом _ не подхватываются загрузчиком (это примеры)."""
        # Проверяем правило загрузчика в исходниках: файлы на '_' пропускаются
        assert fname.startswith("_"), f"{fname} должен начинаться с _ для пропуска"
        assert "." in fname[1:], "Имя файла должно быть <имя>.json"

    @pytest.mark.parametrize("fname", REFERENCE_CONFIGS)
    def test_reference_config_has_rom_signature(self, fname):
        """Каждый эталонный конфиг должен демонстрировать rom_signature."""
        config = json.loads((CONFIG_DIR / fname).read_text(encoding="utf-8"))
        assert "rom_signature" in config, f"{fname} не содержит rom_signature"
        sig = config["rom_signature"]
        entries = sig if isinstance(sig, list) else [sig]
        assert entries, f"{fname}: пустой rom_signature"
        for entry in entries:
            assert "title_pattern" in entry, f"{fname}: сигнатура без title_pattern"

    def test_reference_configs_do_not_shadow_python_plugins(self):
        """Конфиги не должны регистрироваться (иначе задушат Python-плагины)."""
        pm = PluginManager("plugins")
        config_plugins = [p for p in pm.plugins if isinstance(p, ConfigurablePlugin)]
        for p in config_plugins:
            assert not str(p.config.get('game_id_pattern', '')).startswith('^GBA_'), \
                f"Конфиг-плагин {p.game_id_pattern} конфликтует с Python-плагинами"

    def test_reference_signature_rejects_non_matching_rom(self, pm):
        """rom_signature отклоняет ROM не подходящий под сигнатуру."""
        config = json.loads((CONFIG_DIR / "_reference_pokemon_gba_romhack.json").read_text("utf-8"))
        plugin = ConfigurablePlugin(config)

        # ROM с неверным заголовком и неверным размером — должен быть отклонён
        from core.rom import GameBoyROM
        rom = GameBoyROM.__new__(GameBoyROM)
        rom.header = {"title": "NOT A POKEMON GAME"}
        rom.data = b"\x00" * 0x1000  # слишком мал
        assert plugin.validate_rom(rom) is False

    def test_reference_signature_accepts_matching_rom(self, pm):
        """rom_signature принимает ROM с совпадающей сигнатурой."""
        for fname, title, size in [
            ("_reference_pokemon_gba_romhack.json", "POKEMON EMER", 0x1000000),
            ("_reference_advance_wars_gba_romhack.json", "ADVANCEWARS", 0x400000),
            ("_reference_golden_sun_gba_romhack.json", "Golden_Sun_A", 0x800000),
            ("_reference_fire_emblem_gba_romhack.json", "FIREEMBLEM2P", 0x2000000),
        ]:
            config = json.loads(
                (CONFIG_DIR / fname).read_text("utf-8"))
            plugin = ConfigurablePlugin(config)

            from core.rom import GameBoyROM
            rom = GameBoyROM.__new__(GameBoyROM)
            rom.header = {"title": title}
            rom.data = b"\x00" * size
            assert plugin.validate_rom(rom) is True, f"{fname}: сигнатура не приняла реальный title {title!r}"

    def test_config_loader_skips_underscore_files(self):
        """Загрузчик конфигов пропускает файлы с префиксом _."""
        _pm = PluginManager("plugins")

        # Эталонные конфиги не должны оказаться среди загруженных
        config_plugins = [p for p in _pm.plugins if isinstance(p, ConfigurablePlugin)]
        loaded_patterns = {getattr(p, 'game_id_pattern', '') for p in config_plugins}
        assert not {"^GBA_", "POKEMON", "FIRE EMBLEM", "GOLDENSUN", "ADVANCE_WARS"}.intersection(
            loaded_patterns
        )

    # ---- AC1/AC2 (план П2) ----

    @pytest.mark.parametrize("fname", REFERENCE_CONFIGS)
    def test_segments_are_real_non_stub(self, fname):
        """AC1: каждый конфиг содержит реальный документируемый сегмент
        (start > 0x0, end > start), а не заглушку 0x0-0x100."""
        config = _load_config(fname)
        segments = config.get("segments") or []
        assert segments, f"{fname}: нет сегментов"

        real = [
            seg for seg in segments
            if int(seg["start"], 16) > 0x0 and int(seg["end"], 16) > int(seg["start"], 16)
        ]
        assert real, f"{fname}: нет ни одного реального сегмента (start > 0x0, end > start)"

    @pytest.mark.parametrize("fname", REFERENCE_CONFIGS)
    def test_segments_document_plugin_addresses(self, fname):
        """AC1: адреса сегментов совпадают с адресами Python-плагинов."""
        expected = _plugin_addresses()[fname]
        config = _load_config(fname)

        found = {seg["name"]: (int(seg["start"], 16), int(seg["end"], 16))
                 for seg in config["segments"]}
        assert found == expected, \
            f"{fname}: адреса не совпадают с плагин-адресами\n  найдено: {found}\n  ожидалось: {expected}"

    def test_charmap_normalized_accepts_ranges(self):
        """Нормализация charmap из core корректно обрабатывает форматы конфигов."""
        normalize = ConfigurablePlugin._normalize_charmap

        table = normalize({"0x41-0x5A": "A-Z", "0x20": " "})
        assert table[0x41] == "A" and table[0x5A] == "Z" and table[0x20] == " "

        table = normalize({"0x30-0x39": "0-9"})
        assert table[0x30] == "0" and table[0x39] == "9"

        table = normalize({"0x20-0x7E": "ASCII printable"})
        assert table[0x41] == "A" and table[0x61] == "a" and table[0x39] == "9"

        with pytest.raises(ValueError):
            normalize({"0xZZ": "X"})
        with pytest.raises(ValueError):
            normalize({"0x42-0x41": "A"})

    @pytest.mark.parametrize("fname", REFERENCE_CONFIGS)
    def test_config_charmap_decodes_ascii(self, fname):
        """AC2: charmap каждого сегмента нормализуется и декодирует ≥1 ASCII-символ
        (проверяется ЧЕРЕЗ сore-компоненты, а не дублирующий парсер теста)."""
        config = _load_config(fname)
        for seg in config.get("segments") or []:
            charmap = seg.get("charmap") or {}
            assert charmap, f"{fname}: сегмент {seg['name']} без charmap"

            table = ConfigurablePlugin._normalize_charmap(charmap)
            assert table, f"{fname}: {seg['name']} — пустой charmap после нормализации"
            assert all(isinstance(byte, int) and 0 <= byte <= 0xFF for byte in table), \
                f"{fname}: {seg['name']} — байты вне 0x00-0xFF"

            decoder = CharMapDecoder(table)
            # Декодируем байты, покрытые charmap
            data = bytes(sorted(table))
            decoded = decoder.decode(data, 0, len(data))
            assert any(ch.isascii() and (ch.isalpha() or ch.isdigit()) for ch in decoded), \
                f"{fname}: {seg['name']} — charmap не декодирует ни одного ASCII-символа"

    @pytest.mark.parametrize("fname", REFERENCE_CONFIGS)
    def test_config_charmap_works_in_get_text_segments(self, fname):
        """AC2-интеграция: ConfigurablePlugin.get_text_segments не падает на
        строковом charmap конфига и возвращает сегменты с декодером."""
        config = _load_config(fname)
        plugin = ConfigurablePlugin(config)

        from core.rom import GameBoyROM
        rom = GameBoyROM.__new__(GameBoyROM)
        # Размер под максимальный end-адрес всех сегментов
        max_end = max(int(seg["end"], 16) for seg in config["segments"])
        rom.data = b"A" * max_end
        rom.header = {"title": config["rom_signature"][0]["title_pattern"]}

        segs = plugin.get_text_segments(rom)
        assert segs, f"{fname}: get_text_segments не вернул сегменты"
        for seg in segs:
            assert "decoder" in seg, f"{fname}: {seg['name']} без декодера"
            assert seg["decoder"] is not None, f"{fname}: {seg['name']} с пустым декодером"
