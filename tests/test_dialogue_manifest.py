"""Манифесты диалогов Pokemon GBA (core/manifests/*.json).

Проверяет: структуру манифестов (только адреса, никакого текста ROM),
сортировку, консервативность free_after и загрузку с проверкой CRC (кеш
по game_code+crc32). ROM-зависимые тесты помечены rom_required и скипаются
без файлов в test_roms/.
"""
import itertools
import json
import os

import pytest

from core.dialogue_manifest import (
    KNOWN_CODES,
    entries_for_rom,
    manifest_path,
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM_DIR = os.path.join(BASE, 'test_roms')

GAME_ROMS = {
    'BPEE': 'Pokemon - Emerald Version (USA, Europe).gba',
    'BPRE': 'Pokemon - FireRed Version (USA).gba',
    'BPGE': 'Pokemon - LeafGreen Version (USA).gba',
    'AXVE': 'Pokemon - Ruby Version (USA).gba',
    'AXPE': 'Pokemon - Sapphire Version (USA).gba',
}

# Регрессия на известные связи слот->target (обнаружены при RE Emerald).
KNOWN_SLOTS = {
    'BPEE': {0x01E0699: [0x1DF415], 0x01E29E5: [0x1E2628],
             0x01E6604: [0x1E615F], 0x01F16C6: [0x1F10AF]},
}

_ALLOWED_KEYS = {'game_code', 'revision', 'rom_size', 'guard', 'entries',
                 'target', 'free_after', 'slots'}


def _load_raw(game_code):
    path = manifest_path(game_code)
    assert path is not None, f'Манифест {game_code} отсутствует'
    with open(path, encoding='utf-8') as f:
        return json.load(f)


@pytest.mark.parametrize('game_code', KNOWN_CODES)
def test_manifest_shipped_and_wellformed(game_code):
    raw = _load_raw(game_code)
    assert raw['game_code'] == game_code
    assert raw['guard'] > 0
    assert raw['rom_size'] > 0
    entries = raw['entries']
    assert entries, 'Манифест не должен быть пустым'
    targets = [e['target'] for e in entries]
    assert targets == sorted(targets), 'entries должны быть отсортированы'
    for e in entries:
        assert e['free_after'] >= 3
        assert isinstance(e['slots'], list) and e['slots']


@pytest.mark.parametrize('game_code', KNOWN_CODES)
def test_manifest_contains_no_rom_text(game_code):
    """Манифест — чистые адреса, в нём не может быть текстовых полей."""
    raw = _load_raw(game_code)
    flat_keys = set(raw.keys())
    for e in raw['entries']:
        flat_keys.update(e.keys())
    assert flat_keys <= _ALLOWED_KEYS


def test_known_slot_regressions():
    """Проверенные связи указатель-адрес не должны «съехать» при ресканe."""
    for game_code, pairs in KNOWN_SLOTS.items():
        raw = _load_raw(game_code)
        by_target = {e['target']: e['slots'] for e in raw['entries']}
        for target, slots in pairs.items():
            assert target in by_target, f'{game_code}: target 0x{target:X}'
            for s in slots:
                assert s in by_target[target], f'{game_code}: slot 0x{s:X}'


@pytest.mark.rom_required
@pytest.mark.parametrize('game_code', KNOWN_CODES)
def test_entries_for_rom(game_code):
    path = os.path.join(ROM_DIR, GAME_ROMS[game_code])
    if not os.path.exists(path):
        pytest.skip(f'Нет ROM: {os.path.basename(path)}')
    from core.rom import GameBoyROM
    rom = GameBoyROM(path)
    entries = entries_for_rom(rom)
    assert entries, 'Манифест должен подходить под эту ревизию'
    n = len(rom.data)
    for e in entries:
        assert 0 <= e['target'] < n
        assert e['target'] + e['free_after'] <= n
        for s in e['slots']:
            assert 0 <= s < n


@pytest.mark.rom_required
@pytest.mark.parametrize('game_code', KNOWN_CODES)
def test_free_after_does_not_overlap_next(game_code):
    path = os.path.join(ROM_DIR, GAME_ROMS[game_code])
    if not os.path.exists(path):
        pytest.skip(f'Нет ROM: {os.path.basename(path)}')
    from core.rom import GameBoyROM
    rom = GameBoyROM(path)
    entries = entries_for_rom(rom)
    for prev, cur in itertools.pairwise(entries):
        assert prev['target'] + prev['free_after'] <= cur['target']


def test_wrong_crc_returns_none():
    class FakeROM:
        pass
    fake = FakeROM()
    fake.header = {'game_code': 'BPEE'}
    fake.data = bytes(0x1000)
    assert entries_for_rom(fake) is None


def test_unknown_code_returns_none():
    class FakeROM:
        pass
    fake = FakeROM()
    fake.header = {'game_code': 'ZZZZ'}
    fake.data = bytes(0x1000)
    assert entries_for_rom(fake) is None


def test_cache_returns_same_object():
    class FakeROM:
        pass
    fake = FakeROM()
    fake.header = {'game_code': 'BPEE'}
    fake.data = bytes(0x1000)
    assert entries_for_rom(fake) is None
    assert entries_for_rom(fake) is None
