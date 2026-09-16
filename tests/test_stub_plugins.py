"""Тесты stub-плагинов: детекция игры и честный пустой результат."""

import re

import pytest

from core.plugin import GamePlugin
from core.rom import GameBoyROM

STUB_PLUGINS = [
    pytest.param(('plugins.gba_astro_boy', 'AstroBoyPlugin', 'GBA_BTAE'), id='astro_boy'),
    pytest.param(('plugins.gba_sonic_advance', 'SonicAdvancePlugin', 'GBA_ASOE'), id='sonic_advance_1'),
    pytest.param(('plugins.gba_sonic_advance', 'SonicAdvancePlugin', 'GBA_A2NE'), id='sonic_advance_2'),
    pytest.param(('plugins.gba_kingdom_hearts_com', 'KingdomHeartsCOMPlugin', 'GBA_B8CE'), id='kingdom_hearts_com'),
    pytest.param(('plugins.gba_phoenix_wright', 'PhoenixWrightPlugin', 'GBA_ASBJ'), id='phoenix_wright'),
    pytest.param(('plugins.gba_fire_emblem', 'FireEmblemGBAPlugin', 'GBA_BE7E'), id='fire_emblem_fe7'),
    pytest.param(('plugins.gba_fire_emblem', 'FireEmblemGBAPlugin', 'GBA_BE8E'), id='fire_emblem_fe8'),
    pytest.param(('plugins.gba_breath_of_fire', 'BreathOfFirePlugin', 'GBA_ABFE'), id='breath_of_fire'),
    pytest.param(('plugins.gba_telefang_2', 'Telefang2Plugin', 'GBA_ATPJ'), id='telefang_2'),
    pytest.param(('plugins.gba_advance_wars', 'AdvanceWarsPlugin', 'GBA_AWRE'), id='advance_wars'),
    pytest.param(('plugins.gba_castlevania_ctm', 'CastlevaniaCTMPlugin', 'GBA_AAME'), id='castlevania_ctm'),
    pytest.param(('plugins.gba_castlevania_hod', 'CastlevaniaHODPlugin', 'GBA_ACHP'), id='castlevania_hod'),
    pytest.param(('plugins.gba_ct_special_forces', 'CTSpecialForcesPlugin', 'GBA_AC7E'), id='ct_special_forces'),
    pytest.param(('plugins.gba_custom_robo_gx', 'CustomRoboGXPlugin', 'GBA_ARJJ'), id='custom_robo_gx'),
    pytest.param(('plugins.gba_ff6_advance', 'FF6AdvancePlugin', 'GBA_BZ6E'), id='ff6_advance'),
    pytest.param(('plugins.gba_ff12_dawn_of_souls', 'FF12DawnOfSoulsPlugin', 'GBA_BFFE'), id='ff12_dawn_of_souls'),
    pytest.param(('plugins.gba_megaman_battle_network', 'MegaManBattleNetworkPlugin', 'GBA_AREP'), id='megaman_battle_network'),
    pytest.param(('plugins.gba_megaman_battle_network_2', 'MegaManBattleNetwork2Plugin', 'GBA_AM2P'), id='megaman_battle_network_2'),
    pytest.param(('plugins.gba_megaman_zero', 'MegaManZeroPlugin', 'GBA_AZCE'), id='megaman_zero'),
    pytest.param(('plugins.gba_metroid_zero_mission', 'MetroidZeroMissionPlugin', 'GBA_BMXE'), id='metroid_zero_mission'),
    pytest.param(('plugins.gba_shining_force', 'ShiningForcePlugin', 'GBA_AF5E'), id='shining_force'),
    # GB/GBC stub plugins (game_id = GB_/GBC_ + sanitized title)
    pytest.param(('plugins.gbc_harvest_moon_2', 'HarvestMoon2Plugin', 'GBC_HMOON2CGBBM2E'), id='harvest_moon_2'),
    pytest.param(('plugins.gbc_pokemon_gsc', 'PokemonGSCPlugin', 'GBC_POKEMONSILVER'), id='pokemon_gsc_silver'),
    pytest.param(('plugins.gbc_pokemon_gsc', 'PokemonGSCPlugin', 'GBC_POKEMONCRYSTAL'), id='pokemon_gsc_crystal'),
    pytest.param(('plugins.gbc_fire_emblem_reincarnation', 'FireEmblemReincarnationPlugin', 'GBC_SUPERSLG'), id='fire_emblem_reincarnation'),
    pytest.param(('plugins.gbc_harvest_moon', 'HarvestMoonPlugin', 'GBC_HARVESTMOONGB'), id='harvest_moon'),
    pytest.param(('plugins.gbc_harvest_moon_3', 'HarvestMoon3Plugin', 'GBC_HMOON3CGBBWAE'), id='harvest_moon_3'),
    pytest.param(('plugins.gbc_resident_evil_gaiden', 'ResidentEvilGaidenPlugin', 'GBC_RESEVILGDARHE'), id='resident_evil_gaiden'),
    pytest.param(('plugins.gbc_smt_devil_children', 'SMTDevilChildrenPlugin', 'GBC_DEBITIRUBBHEJ'), id='smt_devil_children'),
    pytest.param(('plugins.gbc_super_mario_bros_deluxe', 'SuperMarioBrosDeluxePlugin', 'GBC_MARIODELUXAHYE'), id='super_mario_bros_deluxe'),
]


@pytest.fixture(params=STUB_PLUGINS)
def stub_case(request):
    module_name, cls_name, game_id = request.param
    module = __import__(module_name, fromlist=[cls_name])
    plugin = getattr(module, cls_name)()
    return plugin, game_id


def test_stub_plugin_detects_game_code(stub_case):
    plugin, game_id = stub_case
    assert isinstance(plugin, GamePlugin)
    pattern = plugin.game_id_pattern
    assert re.match(pattern, game_id), \
        f"game_id_pattern {pattern!r} не матчит {game_id}"


def test_stub_plugin_returns_empty_and_is_stub(stub_case):
    plugin, game_id = stub_case
    rom = GameBoyROM.__new__(GameBoyROM)
    rom.data = b'\x00' * 0x800000
    rom.header = {'game_code': game_id}
    segments = plugin.get_text_segments(rom)
    assert isinstance(segments, list)
    assert len(segments) == 0, \
        f"Stub {plugin.__class__.__name__} вернул сегменты для {game_id}"
    assert getattr(plugin, 'is_stub', False), (
        f"{plugin.__class__.__name__} должен быть помечен is_stub=True"
    )
