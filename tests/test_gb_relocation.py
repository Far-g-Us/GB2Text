"""16-битная банковая релокация для GB/GBC (Oracle of Seasons).

Формат слота в Oracle: 16-битное значение по адресу `_text_table + index*2`,
отсчитанное от базы группы, а банк выбирается индексом записи, а НЕ этим
значением. Отсюда два ограничения, которые проверяются здесь: перенос
обязан остаться в одном банке с оригиналом и в пределах 0..0xFFFF от базы.

Тесты синтетические (реальных ROM в CI нет), но контракт — тот же, что в
`scripts_roms/gb_oracle_slot_probe.py`, который measures его на US ROM.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.injector import TextInjector, _gb_bank_of

ROM_SIZE = 0x80000
BANK = 0x4000


@pytest.fixture
def injector():
    inj = TextInjector.__new__(TextInjector)
    import logging
    inj.logger = logging.getLogger('test')
    inj.modified_data = bytearray(ROM_SIZE)
    inj._written_spans = []
    inj.last_relocate_report = []
    return inj


def _write16(data: bytearray, at: int, value: int) -> None:
    data[at:at + 2] = value.to_bytes(2, 'little')


def _make_entry(target: int, base: int, slot: int) -> dict:
    return {
        'target': target,
        'free_after': 8,
        'slots': [slot],
        'slot_size': 2,
        'reloc_base': base,
    }


def _relocate_ok(inj, base=0x30000, target=None, slot=0x200, span=0x40):
    """Готовит запись со слотом и свободным местом после окна базы."""
    target = target if target is not None else base
    _write16(inj.modified_data, slot, target - base)
    entry = _make_entry(target, base, slot)
    payload = b'X' * 8
    free = [(base + span, base + span + 0x400)]
    return entry, payload, free


def test_gb_bank_of():
    assert _gb_bank_of(0) == 0
    assert _gb_bank_of(BANK - 1) == 0
    assert _gb_bank_of(BANK) == 1
    assert _gb_bank_of(3 * BANK + 5) == 3


def test_relocate_writes_16bit_offset(injector):
    """Перенос пишет в слот 16-битное смещение от базы, а не GBA-указатель."""
    base = 0x30000
    target = base + 0x40
    slot = 0x200
    _write16(injector.modified_data, slot, target - base)
    entry = _make_entry(target, base, slot)
    payload = b'Y' * 8
    free = [(base + 0x200, base + 0x600)]
    assert injector._relocate_dialogue([entry], entry, target, payload,
                                       free_runs=free) is True
    stored = int.from_bytes(injector.modified_data[slot:slot + 2], 'little')
    dest = stored + base
    assert injector.modified_data[dest:dest + 8] == payload
    # Старый блок освобождён — это признак переноса для обратного извлечения.
    assert set(injector.modified_data[target:target + 8]) == {0}


def test_relocate_refuses_when_offset_exceeds_16_bits(injector):
    """Адрес дальше базы +0xFFFF в слот не помещается — отказ, а не запись."""
    base = 0x10000
    target = base + 0x40
    slot = 0x200
    _write16(injector.modified_data, slot, target - base)
    entry = _make_entry(target, base, slot)
    payload = b'Z' * 8
    free = [(base + 0x20000, base + 0x20400)]
    assert injector._relocate_dialogue([entry], entry, target, payload,
                                       free_runs=free) is False
    assert injector.modified_data[slot:slot + 2] == \
        (target - base).to_bytes(2, 'little')


def test_relocate_refuses_cross_bank(injector):
    """Банк выбирается индексом, поэтому перенос в чужой банк запрещён."""
    base = 0x30000
    target = base + 0x40
    slot = 0x200
    _write16(injector.modified_data, slot, target - base)
    entry = _make_entry(target, base, slot)
    payload = b'W' * 8
    # Свободное место — в следующем банке, и в пределах 0xFFFF от базы.
    dest = ((base // BANK) + 1) * BANK + 0x100
    free = [(dest, dest + 0x400)]
    assert injector._relocate_dialogue([entry], entry, target, payload,
                                       free_runs=free) is False


def test_relocate_requires_base_for_16bit(injector):
    """16-битный слот без базы — отказ: база определяет смысл значения."""
    base = 0x30000
    target = base + 0x40
    slot = 0x200
    _write16(injector.modified_data, slot, 0x40)
    entry = {'target': target, 'free_after': 8, 'slots': [slot], 'slot_size': 2}
    assert injector._relocate_dialogue([entry], entry, target, b'A' * 8,
                                       free_runs=[(base + 0x200, base + 0x600)]) \
        is False


def test_relocate_rejects_bad_slot_size(injector):
    base = 0x30000
    slot = 0x200
    entry = {'target': base, 'free_after': 8, 'slots': [slot], 'slot_size': 3}
    assert injector._relocate_dialogue([entry], entry, base, b'A' * 8) is False


def test_gba_path_still_writes_32bit_pointer(injector):
    """GBA-ветка не сломана: 32-битный указатель 0x08+addr в слоте."""
    target = 0x1000
    slot = 0x200
    injector.modified_data[slot:slot + 4] = (0x08000000 + target).to_bytes(
        4, 'little')
    entry = {'target': target, 'free_after': 8, 'slots': [slot]}
    payload = b'G' * 8
    free = [(0x2000, 0x2400)]
    assert injector._relocate_dialogue([entry], entry, target, payload,
                                       free_runs=free) is True
    stored = int.from_bytes(injector.modified_data[slot:slot + 4], 'little')
    assert stored >= 0x08000000
    assert stored - 0x08000000 != target


def test_relocated_dialogue_addr_follows_16bit_slot(tmp_path):
    """Extractor идёт за новым адресом по 16-битному слоту."""
    from core.extractor import _relocated_dialogue_addr
    base = 0x30000
    target = base + 0x40
    slot = 0x200
    dest = base + 0x220
    # Буфер покрывает и слот, и окно базы (адреса около 0x30000).
    data = bytearray(0x40000)
    _write16(data, slot, dest - base)
    # Старый блок обнулён инжектором — без этого перенос не подтверждён.
    entry = _make_entry(target, base, slot)
    assert _relocated_dialogue_addr(data, entry, target) == dest


def test_relocated_dialogue_addr_requires_blank_old_block():
    """Слот указывает на новое место, но старый блок НЕ обнулён — это не перенос.

    Именно от этого спасает вторая проверка: на ROM-хаках слоты расходятся с
    манифестом уже на чистой ROM, и без требования пустоты мы бы сочли
    переносом то, что переносом не является.
    """
    from core.extractor import _relocated_dialogue_addr
    base = 0x30000
    target = base + 0x40
    slot = 0x200
    dest = base + 0x220
    data = bytearray(0x40000)
    _write16(data, slot, dest - base)
    data[target:target + 8] = b'ORIGINAL'  # старый блок на месте
    entry = _make_entry(target, base, slot)
    assert _relocated_dialogue_addr(data, entry, target) is None


def test_relocated_dialogue_addr_gba_path_unchanged():
    """GBA-путь по-прежнему снимает базу 0x08."""
    from core.extractor import _relocated_dialogue_addr
    data = bytearray(0x1000)
    slot = 0x200
    dest = 0x900
    data[slot:slot + 4] = (0x08000000 + dest).to_bytes(4, 'little')
    entry = {'target': 0x800, 'free_after': 8, 'slots': [slot]}
    assert _relocated_dialogue_addr(data, entry, 0x800) == dest


def test_manifest_provides_slots_on_real_rom():
    """На реальном ROM у каждой записи есть слот, база и размер слота."""
    rom_path = (r'C:\Users\EndY\AppData\Local\Temp\opencode\rom_work'
                r'\Legend of Zelda, The - Oracle of Seasons (USA).gbc')
    if not os.path.exists(rom_path):
        pytest.skip('нет копии ROM для проверки манифеста')
    from plugins.zelda_oracle_common import OracleTextDecoder
    data = open(rom_path, 'rb').read()
    man = OracleTextDecoder().build_manifest(data)
    assert man
    for entry in man[:200]:
        assert entry.get('slot_size') == 2
        assert isinstance(entry.get('reloc_base'), int)
        slots = entry.get('slots')
        assert isinstance(slots, list) and len(slots) == 1
        stored = int.from_bytes(data[slots[0]:slots[0] + 2], 'little')
        assert stored == entry['target'] - entry['reloc_base'], (
            'значение слота должно совпадать с target минус база')
