"""Тесты Хаффмана Golden Sun, работающие БЕЗ реального ROM.

В CI реальных ROM нет, и весь `test_golden_sun.py` уходит в `skip` — то есть
переписанный декодер не исполнялся бы ни одной строкой. Здесь топология и
данные собираются синтетически, поэтому проверки работают на любой машине.

Эталон рекурсивного разбора и обхода приведён здесь целиком: без него
утверждение «итеративный разбор даёт то же, что рекурсивный» нечем
проверять. Он остаётся отдельной реализацией намеренно — как `_foreign_ranges`
для индекса чужих диапазонов.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.gba_golden_sun import GoldenSunHuffmanDecoder, _BitReader

TREES_BASE = 0x100
OFFSETS_BASE = 0x40
# Смещение дерева внутри таблицы: 0 означает «дерева нет» (так в игре), поэтому
# первое дерело обязано лежать не в нуле. Таблица смещений занимает
# 0x40..0x23E, деревья начинаются за ней — иначе запись смещений затирает
# топологии.
FIRST_TREE = 0x400
ROM_SIZE = 0x8000


def build_bits(bits: list[int], offset: int = 0) -> bytearray:
    """Биты в байты, начиная со смещения `offset` (младший бит первым)."""
    out = bytearray(offset + (len(bits) + 7) // 8 + 2)
    for i, b in enumerate(bits):
        if b:
            out[offset + i // 8] |= 1 << (i % 8)
    return out


def make_rom(trees: dict[int, list[int]]) -> bytes:
    """ROM с заданными топологиями: prev-байт -> биты топологии."""
    data = bytearray(ROM_SIZE)
    for i in range(256):
        rel = 0x8000  # GS_NO_TREE
        if i in trees:
            rel = FIRST_TREE + i * 0x40
            start = TREES_BASE + rel
            chunk = build_bits(trees[i])
            data[start:start + len(chunk)] = chunk
        data[OFFSETS_BASE + i * 2] = rel & 0xFF
        data[OFFSETS_BASE + i * 2 + 1] = (rel >> 8) & 0xFF
    return bytes(data)


def leaf(leaf_id: int, topo_start: int, rom: bytes) -> int:
    """Значение листа — тот же формат упаковки, что в игре."""
    off = leaf_id + (leaf_id >> 1)
    if leaf_id & 1:
        return rom[topo_start - off - 2]
    return ((rom[topo_start - off - 1] & 0x0F) << 4) | \
        ((rom[topo_start - off - 2] >> 4) & 0x0F)


# ── эталон: рекурсивный разбор топологии ───────────────────────────────────

def reference_parse(data: bytes, topo_start: int) -> list[int]:
    """Дословно прежний рекурсивный разбор (в коде его больше нет)."""
    nodes: list[int] = []
    state = [topo_start, 0]

    def read_bit() -> int:
        bit = (data[state[0]] >> state[1]) & 1
        state[1] += 1
        if state[1] == 8:
            state[1] = 0
            state[0] += 1
        return bit

    def parse(leaf_id: int) -> int:
        my = len(nodes)
        if read_bit() == 1:
            nodes.append(leaf_id)
            return 1
        nodes.append(0)
        left = parse(leaf_id)
        right = parse(leaf_id + left)
        nodes[my] = -left
        return left + right

    parse(0)
    return nodes


# ── эталон: прежний обход при декодировании ────────────────────────────────

def reference_decode_symbol(rom: bytes, dr: _BitReader, prev: int,
                            trees_base: int, offsets: list[int]) -> int:
    """Прежний декодер символа: рекурсивный подсчёт пропущенных листьев."""
    topo_start = trees_base + offsets[prev]
    tp = _BitReader(rom, topo_start)

    def count_skipped() -> int:
        total = 0

        def walk() -> None:
            nonlocal total
            if tp.read_bit() == 1:
                total += 1
            else:
                walk()
                walk()

        walk()
        return total

    leaf_count = 0
    while True:
        if tp.read_bit() == 1:
            return leaf(leaf_count, topo_start, rom)
        if dr.read_bit() == 1:
            leaf_count += count_skipped()


# ── тесты ──────────────────────────────────────────────────────────────────

CASES = {
    # один лист
    'single_leaf': [1],
    # 3 листа: корень, левое поддерево из 1, правое из 2
    'three_leaves': [0, 1, 0, 1, 1],
    # 4 листа: обе стороны по 2
    'four_leaves': [0, 0, 1, 1, 0, 1, 1],
    # 7 листьев: глубокий левый хребет
    'deep_left': [0, 0, 0, 1, 1, 1, 1, 1, 1, 1],
    # глубокий ПРАВЫЙ хребет — там прежний обход тоже спускался глубоко
    'deep_right': [0, 1, 0, 1, 0, 1, 0, 1, 1, 1, 1],
}


@pytest.mark.parametrize('name', sorted(CASES))
def test_parse_matches_recursive_reference(name):
    bits = CASES[name]
    rom = make_rom({0: bits})
    dec = GoldenSunHuffmanDecoder(rom, offsets_base=OFFSETS_BASE,
                                  trees_base=TREES_BASE)
    topo_start = TREES_BASE + dec.offsets[0]
    assert dec._parse_tree(topo_start) == reference_parse(rom, topo_start)


def test_parse_degenerate_left_chain_does_not_recurse():
    """Хребет из 20000 узлов: рекурсивный разбор упал бы с RecursionError.

    В стоковом Golden Sun 6 из 239 деревьев выше 900 по высоте, так что это не
    экзотика, а нормальные данные.
    """
    n = 20000
    bits = [0] * n + [1] * (n + 1)
    rom = make_rom({0: bits})
    dec = GoldenSunHuffmanDecoder(rom, offsets_base=OFFSETS_BASE,
                                  trees_base=TREES_BASE)
    nodes = dec._parse_tree(TREES_BASE + dec.offsets[0])
    assert len(nodes) == 2 * n + 1
    assert sum(1 for x in nodes if x >= 0) == n + 1


@pytest.mark.parametrize('name', sorted(CASES))
def test_decode_matches_reference_walk(name):
    """Декодирование символов совпадает со старым обходом по топологии."""
    bits = CASES[name]
    rom = make_rom({0: bits, 0x41: bits})
    dec = GoldenSunHuffmanDecoder(rom, offsets_base=OFFSETS_BASE,
                                  trees_base=TREES_BASE)
    offsets = dec.offsets
    for data_bits in ([0], [1], [0, 1], [1, 0], [1, 1, 0], [0, 0, 1, 1]):
        dr_new = _BitReader(build_bits(data_bits))
        dr_old = _BitReader(build_bits(data_bits))
        got = dec._decode_symbol(dr_new, 0)
        want = reference_decode_symbol(rom, dr_old, 0, TREES_BASE, offsets)
        assert got == want, (name, data_bits)
        # столько же битов данных израсходовано — иначе символы «поедут»
        assert dr_new.bitpos == dr_old.bitpos and \
            dr_new.bytepos == dr_old.bytepos, (name, data_bits)


def test_consumed_data_bits_match_reference():
    """Сколько именно битов съедает символ — тоже часть контракта."""
    bits = CASES['four_leaves']
    rom = make_rom({0: bits})
    dec = GoldenSunHuffmanDecoder(rom, offsets_base=OFFSETS_BASE,
                                  trees_base=TREES_BASE)
    for data_bits in ([0], [1], [1, 1, 0, 0], [0, 1, 1]):
        a = _BitReader(build_bits(data_bits))
        b = _BitReader(build_bits(data_bits))
        dec._decode_symbol(a, 0)
        reference_decode_symbol(rom, b, 0, TREES_BASE, dec.offsets)
        assert (a.bytepos, a.bitpos) == (b.bytepos, b.bitpos)


def test_no_tree_refuses():
    rom = make_rom({})
    dec = GoldenSunHuffmanDecoder(rom, offsets_base=OFFSETS_BASE,
                                  trees_base=TREES_BASE)
    with pytest.raises(ValueError):
        dec._decode_symbol(_BitReader(build_bits([0, 1, 1])), 0)


def test_tree_out_of_bounds_refuses():
    rom = bytearray(make_rom({}))
    rom[OFFSETS_BASE] = 0xF0  # rel за пределами ROM
    rom[OFFSETS_BASE + 1] = 0x7F
    dec = GoldenSunHuffmanDecoder(bytes(rom), offsets_base=OFFSETS_BASE,
                                  trees_base=TREES_BASE)
    with pytest.raises(ValueError):
        dec._decode_symbol(_BitReader(build_bits([0, 1, 1])), 0)


def test_rom_too_small_refuses():
    with pytest.raises(ValueError):
        GoldenSunHuffmanDecoder(b'\x00' * 16, offsets_base=OFFSETS_BASE,
                                trees_base=TREES_BASE)


def test_broken_topology_degrades_instead_of_crashing():
    """Обрезанная топология обязана дать усечение, а не исключение наружу."""
    rom = make_rom({0: [0, 0, 1]})  # требует битов дальше конца
    dec = GoldenSunHuffmanDecoder(rom, offsets_base=OFFSETS_BASE,
                                  trees_base=TREES_BASE)
    assert isinstance(dec.decode_string(build_bits([1, 1, 1])), bytes)
