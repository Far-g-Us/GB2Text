"""Тесты механизма поддержки ROM-хаков (сигнатурный гейт плагинов)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.plugin import GamePlugin
from core.plugin_manager import CancellationToken, ConfigurablePlugin, PluginManager
from core.rom import GameBoyROM
from plugins.gba_golden_sun import GoldenSunPlugin
from plugins.gba_pokemon import PokemonGBAPlugin


def _build_gba_bytes(title: str, game_code: str = 'BPEE', size: int = 0x1000000) -> bytes:
    """Синтетический GBA ROM: title на 0xA0, game_code на 0xAC (gbatek)."""
    data = bytearray(b'\xff' * size)
    data[0x0A0:0x0A0 + len(title)] = title.encode('ascii')
    data[0x0AC:0x0B0] = game_code.encode('ascii')
    return bytes(data)


class SyntheticHackPlugin(GamePlugin):
    """Тестовый хак-плагин: тот же game_code, но сигнатура по title."""

    _is_stub = True

    @property
    def game_id_pattern(self) -> str:
        return r'^GBA_BPEE$'

    def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
        return []

    def validate_rom(self, rom: GameBoyROM) -> bool:
        return rom.header.get('title', '') == 'POKEMON HACK'


class TestRomHackSupport:

    def _make_rom(self, tmp_path, title: str, game_code: str = 'BPEE'):
        path = tmp_path / f'{title[:8] or "rom"}_{game_code}.gba'
        path.write_bytes(_build_gba_bytes(title, game_code))
        return GameBoyROM(str(path))

    def test_gba_title_read_from_correct_offset(self, tmp_path):
        """Фикс офсета: title GBA читается с 0xA0, а не с ветки ARM."""
        rom = self._make_rom(tmp_path, 'POKEMON RUBY')
        assert rom.header['title'] == 'POKEMON RUBY'
        assert rom.header['game_code'] == 'BPEE'

    def test_legacy_no_rom_first_match(self, tmp_path):
        """Без rom — прежнее поведение: первый regex-match."""
        pm = PluginManager("plugins")
        plugin = pm.get_plugin("GBA_BPEE", "gba")
        assert isinstance(plugin, PokemonGBAPlugin)

    def test_vanilla_rom_beats_hack_plugin(self, tmp_path):
        """Хак+ваниль: validate_rom(hack)=False → остаётся ванильный плагин."""
        pm = PluginManager("plugins")
        pm.specific_plugins.append(SyntheticHackPlugin())
        rom = self._make_rom(tmp_path, 'POKEMON EMER')
        plugin = pm.get_plugin(rom.get_game_id(), rom.system, rom=rom)
        assert isinstance(plugin, PokemonGBAPlugin)

    def test_hack_rom_beats_vanilla_plugin(self, tmp_path):
        """Хак-ROM: гейт-плагин выигрывает у ванильного независимо от порядка."""
        pm = PluginManager("plugins")
        pm.specific_plugins.append(SyntheticHackPlugin())
        rom = self._make_rom(tmp_path, 'POKEMON HACK')
        plugin = pm.get_plugin(rom.get_game_id(), rom.system, rom=rom)
        assert isinstance(plugin, SyntheticHackPlugin)

    def test_validate_rom_exception_not_candidate(self, tmp_path):
        """Исключение в validate_rom → плагин пропускается, ваниль остаётся."""
        class BrokenHackPlugin(GamePlugin):
            _is_stub = True

            @property
            def game_id_pattern(self) -> str:
                return r'^GBA_BPEE$'

            def get_text_segments(self, rom: GameBoyROM) -> list[dict]:
                return []

            def validate_rom(self, rom: GameBoyROM) -> bool:
                raise RuntimeError('boom')

        pm = PluginManager("plugins")
        pm.specific_plugins.append(BrokenHackPlugin())
        rom = self._make_rom(tmp_path, 'POKEMON HACK')
        plugin = pm.get_plugin(rom.get_game_id(), rom.system, rom=rom)
        assert isinstance(plugin, PokemonGBAPlugin)

    def test_cancel_returns_none(self, tmp_path):
        """Отмена срабатывает и без rom, и с rom."""
        pm = PluginManager("plugins")
        token = CancellationToken()
        token.cancel()
        assert pm.get_plugin("GBA_BPEE", "gba", token) is None
        rom = self._make_rom(tmp_path, 'POKEMON EMER')
        assert pm.get_plugin(rom.get_game_id(), rom.system, token, rom=rom) is None


class TestConfigSignature:

    def _write_config(self, plugins_dir, name: str, config: dict):
        cfg_dir = plugins_dir / 'config'
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / name).write_text(json.dumps(config), encoding='utf-8')

    def test_config_signature_matches_title(self, tmp_path):
        cfg = {
            'game_id_pattern': '^GBA_BPEE$',
            'rom_signature': [{'title_pattern': '^POKEMON HACK$'}],
            'segments': [],
        }
        plugin = ConfigurablePlugin(cfg)
        v_path = tmp_path / 'V.gba'
        v_path.write_bytes(_build_gba_bytes('POKEMON EMER', 'BPEE'))
        h_path = tmp_path / 'H.gba'
        h_path.write_bytes(_build_gba_bytes('POKEMON HACK'))
        vanilla = GameBoyROM(str(v_path))
        hack = GameBoyROM(str(h_path))
        assert plugin.validate_rom(vanilla) is False
        assert plugin.validate_rom(hack) is True

    def test_config_size_signature(self, tmp_path):
        b_path = tmp_path / 'B.gba'
        b_path.write_bytes(_build_gba_bytes('POKEMON EMER', 'BPEE', size=0x2000000))
        s_path = tmp_path / 'S.gba'
        s_path.write_bytes(_build_gba_bytes('POKEMON EMER', 'BPEE', size=0x1000000))
        big = GameBoyROM(str(b_path))
        small = GameBoyROM(str(s_path))
        plugin = ConfigurablePlugin({
            'game_id_pattern': '^GBA_BPEE$',
            'rom_signature': [{'min_size': 0x1800000, 'max_size': 0x3000000}],
            'segments': [],
        })
        assert plugin.validate_rom(big) is True
        assert plugin.validate_rom(small) is False

    def test_load_signature_config_not_duplicate(self, tmp_path):
        """Конфиг с сигнатурой и тем же pattern НЕ выкидывается как дубликат."""
        self._write_config(tmp_path, 'base.json', {
            'game_id_pattern': '^GBA_ZZZZ$',
            'segments': [], })
        # Дубликат без сигнатуры — пропускается, как раньше
        self._write_config(tmp_path, 'dup.json', {
            'game_id_pattern': '^GBA_ZZZZ$',
            'segments': [], })
        # Хак-конфиг с тем же pattern — загружается
        self._write_config(tmp_path, 'hack.json', {
            'game_id_pattern': '^GBA_ZZZZ$',
            'rom_signature': [{'title_pattern': '^SYNTH$'}],
            'segments': [], })
        pm = PluginManager(str(tmp_path))
        patterns = [p.game_id_pattern for p in pm.specific_plugins]
        assert patterns.count('^GBA_ZZZZ$') == 2

    def test_non_pokemon_game_hack_detected(self, tmp_path):
        """Механизм не покемон-специфичен: хак Golden Sun с сигнатурой
        перебивает ванильный GoldenSunPlugin, ваниль остаётся у плагина."""
        pm = PluginManager("plugins")
        pm.specific_plugins.append(ConfigurablePlugin({
            'game_id_pattern': '^GBA_AGSE$',
            'rom_signature': [{'title_pattern': '^GOLDEN SUN H$'}],
            'segments': [], }))
        v_path = tmp_path / 'GS_V.gba'
        v_path.write_bytes(_build_gba_bytes('GOLDEN SUN  ', 'AGSE'))
        h_path = tmp_path / 'GS_H.gba'
        h_path.write_bytes(_build_gba_bytes('GOLDEN SUN H', 'AGSE'))
        vanilla = GameBoyROM(str(v_path))
        hack = GameBoyROM(str(h_path))
        assert isinstance(
            pm.get_plugin(hack.get_game_id(), hack.system, rom=hack),
            ConfigurablePlugin)
        assert isinstance(
            pm.get_plugin(vanilla.get_game_id(), vanilla.system, rom=vanilla),
            GoldenSunPlugin)

    def test_signature_title_pattern_is_prefix_match(self, tmp_path):
        """re.match согласован с докой: паттерн без якорей ловит префикс."""
        path = tmp_path / 'V.gba'
        path.write_bytes(_build_gba_bytes('POKEMON EMER'))
        rom = GameBoyROM(str(path))
        plugin = ConfigurablePlugin({
            'game_id_pattern': '^GBA_BPEE$',
            'rom_signature': [{'title_pattern': 'POKEMON'}],
            'segments': [], })
        # Именно поэтому нужны явные якоря (^...$) — см. контракт.
        assert plugin.validate_rom(rom) is True

    def test_signature_first_base_not_duplicate(self, tmp_path):
        """Signature-конфиг загружается раньше base — base НЕ выкидывается как дубликат."""
        self._write_config(tmp_path, 'a_hack.json', {
            'game_id_pattern': '^GBA_ZZZY$',
            'rom_signature': [{'title_pattern': '^SYNTH$'}],
            'segments': [], })
        self._write_config(tmp_path, 'z_base.json', {
            'game_id_pattern': '^GBA_ZZZY$',
            'segments': [], })
        pm = PluginManager(str(tmp_path))
        patterns = [p.game_id_pattern for p in pm.specific_plugins]
        assert patterns.count('^GBA_ZZZY$') == 2

    def test_load_invalid_signature_skipped(self, tmp_path):
        """Битый regex в rom_signature → конфиг не загружается."""
        self._write_config(tmp_path, 'bad.json', {
            'game_id_pattern': '^GBA_QQ$',
            'rom_signature': [{'title_pattern': '(('}],
            'segments': [], })
        pm = PluginManager(str(tmp_path))
        assert not any(p.game_id_pattern == '^GBA_QQ$' for p in pm.specific_plugins)

    def test_config_selects_hack_over_vanilla(self, tmp_path):
        """Конфиг-хак с сигнатурой перебивает ванильный плагин при хак-ROM."""
        pm = PluginManager("plugins")
        pm.specific_plugins.append(ConfigurablePlugin({
            'game_id_pattern': '^GBA_BPEE$',
            'rom_signature': [{'title_pattern': '^POKEMON HACK$'}],
            'segments': [], }))
        v_path = tmp_path / 'V.gba'
        v_path.write_bytes(_build_gba_bytes('POKEMON EMER', 'BPEE'))
        h_path = tmp_path / 'H.gba'
        h_path.write_bytes(_build_gba_bytes('POKEMON HACK'))
        vanilla = GameBoyROM(str(v_path))
        hack = GameBoyROM(str(h_path))
        assert isinstance(
            pm.get_plugin(hack.get_game_id(), hack.system, rom=hack),
            ConfigurablePlugin)
        assert isinstance(
            pm.get_plugin(vanilla.get_game_id(), vanilla.system, rom=vanilla),
            PokemonGBAPlugin)


class TestRomPassthrough:
    """Только rom (без game_id) прокидывается во все реальные вызовы."""

    def test_gui_calls_pass_rom(self):
        """Все вызовы get_plugin в gui/main_window.py передают rom=."""
        src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'gui', 'main_window.py')
        text = open(src, encoding='utf-8').read().splitlines()
        spots = []
        for i, line in enumerate(text):
            if 'get_plugin(' in line and not line.lstrip().startswith('#'):
                lines = [line]
                j = i
                while ')' not in lines[-1] and j < len(text) - 1:
                    j += 1
                    lines.append(text[j])
                assert 'rom=' in '\n'.join(lines), \
                    f"main_window.py:{i + 1}: get_plugin без rom="
                spots.append(i + 1)
        assert len(spots) == 7, spots

    def test_extractor_passes_rom(self):
        src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'core', 'extractor.py')
        text = open(src, encoding='utf-8').read()
        assert 'rom=self.rom' in text
