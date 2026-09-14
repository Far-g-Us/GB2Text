"""Тесты stub-плагинов: детекция игры и честный пустой результат."""

import re

import pytest

from core.plugin import GamePlugin
from core.rom import GameBoyROM

STUB_PLUGINS = [
    pytest.param(('plugins.gba_sonic_advance', 'SonicAdvancePlugin', 'A2NE'), id='sonic_advance_2'),
    pytest.param(('plugins.gba_breath_of_fire', 'BreathOfFirePlugin', 'ABFE'), id='breath_of_fire'),
    pytest.param(('plugins.gba_telefang_2', 'Telefang2Plugin', 'ATPJ'), id='telefang_2'),
    pytest.param(('plugins.gba_advance_wars', 'AdvanceWarsPlugin', 'AWRE'), id='advance_wars'),
    pytest.param(('plugins.gba_castlevania_ctm', 'CastlevaniaCTMPlugin', 'AAME'), id='castlevania_ctm'),
    pytest.param(('plugins.gba_castlevania_hod', 'CastlevaniaHODPlugin', 'ACHP'), id='castlevania_hod'),
    pytest.param(('plugins.gba_ct_special_forces', 'CTSpecialForcesPlugin', 'AC7E'), id='ct_special_forces'),
    pytest.param(('plugins.gba_custom_robo_gx', 'CustomRoboGXPlugin', 'ARJJ'), id='custom_robo_gx'),
    pytest.param(('plugins.gba_ff6_advance', 'FF6AdvancePlugin', 'BZ6E'), id='ff6_advance'),
    pytest.param(('plugins.gba_ff12_dawn_of_souls', 'FF12DawnOfSoulsPlugin', 'BFFE'), id='ff12_dawn_of_souls'),
    pytest.param(('plugins.gba_golden_sun_tla', 'GoldenSunTLAPlugin', 'AGFE'), id='golden_sun_tla'),
    pytest.param(('plugins.gba_megaman_battle_network', 'MegaManBattleNetworkPlugin', 'AREP'), id='megaman_battle_network'),
    pytest.param(('plugins.gba_megaman_battle_network_2', 'MegaManBattleNetwork2Plugin', 'AM2P'), id='megaman_battle_network_2'),
    pytest.param(('plugins.gba_megaman_zero', 'MegaManZeroPlugin', 'AZCE'), id='megaman_zero'),
    pytest.param(('plugins.gba_metroid_zero_mission', 'MetroidZeroMissionPlugin', 'BMXE'), id='metroid_zero_mission'),
    pytest.param(('plugins.gba_shining_force', 'ShiningForcePlugin', 'AF5E'), id='shining_force'),
]


@pytest.fixture(params=STUB_PLUGINS)
def stub_case(request):
    module_name, cls_name, game_code = request.param
    module = __import__(module_name, fromlist=[cls_name])
    plugin = getattr(module, cls_name)()
    return plugin, game_code


def test_stub_plugin_detects_game_code(stub_case):
    plugin, game_code = stub_case
    assert isinstance(plugin, GamePlugin)
    pattern = plugin.game_id_pattern
    assert re.match(pattern, f'GBA_{game_code}'), \
        f"game_id_pattern {pattern!r} не матчит GBA_{game_code}"


def test_stub_plugin_returns_empty_and_is_stub(stub_case):
    plugin, game_code = stub_case
    rom = GameBoyROM.__new__(GameBoyROM)
    rom.data = b'\x00' * 0x800000
    rom.header = {'game_code': game_code}
    segments = plugin.get_text_segments(rom)
    assert isinstance(segments, list)
    assert len(segments) == 0, \
        f"Stub {plugin.__class__.__name__} вернул сегменты для {game_code}"
    assert getattr(plugin, 'is_stub', False), (
        f"{plugin.__class__.__name__} должен быть помечен is_stub=True"
    )
