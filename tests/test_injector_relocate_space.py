"""Тесты вспомогательных функций инжектора: выбор места переноса.

Четыре хелпера, добавленных при устранении квадратичности
`_relocate_dialogue`, стоят на границе с порчей ROM, а в CI (реальных ROM
нет) все `rom_required` пропускаются — то есть эти строки иначе не
исполнялись бы вообще. Проверяем их без ROM.
"""
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.injector import TextInjector


@pytest.fixture
def inj(tmp_path):
    rom = tmp_path / 'fake.gba'
    rom.write_bytes(b'\x00' * 4096)
    i = TextInjector(str(rom))
    i.logger = logging.getLogger('test')
    i.last_relocate_report = []
    return i


# ── _disjoint_intervals ────────────────────────────────────────────────────

def test_disjoint_merges_overlapping():
    starts, ends = TextInjector._disjoint_intervals(
        [(10, 20), (15, 25), (30, 40)])
    assert list(zip(starts, ends, strict=True)) == [(10, 25), (30, 40)]


def test_disjoint_absorbs_nested_and_adjacent():
    starts, ends = TextInjector._disjoint_intervals(
        [(10, 50), (20, 30), (50, 60)])
    assert list(zip(starts, ends, strict=True)) == [(10, 60)]


def test_disjoint_empty():
    assert TextInjector._disjoint_intervals([]) == ([], [])


@pytest.mark.parametrize('bad', [
    [(10, 10)],          # пустой
    [(30, 10)],          # инвертированный
    [('a', 20)],          # не-int
    [(10, None)],         # мусор вместо конца
    [(1, 2, 3)],          # не пара
])
def test_disjoint_rejects_malformed(bad):
    """Мусор во входе обязан ОТКАЗАТЬ, а не молча выбросить окно.

    Иначе «забытый» чужой интервал разрешил бы запись поверх игровых
    данных: `_check_write_overlap` чужие диапазоны не видит, и это
    единственный барьер.
    """
    with pytest.raises(ValueError):
        TextInjector._disjoint_intervals(bad)


# ── _hits_disjoint ─────────────────────────────────────────────────────────

def brute_hits(intervals, a, b):
    return any(a < stop and start < b for start, stop in intervals)


@pytest.mark.parametrize('intervals', [
    [],
    [(10, 20)],
    [(10, 20), (30, 40)],
    [(0, 100), (40, 50), (200, 210)],
    [(40, 50), (50, 60), (60, 70)],   # цепочка касаний
    [(100, 200)],
])
def test_hits_disjoint_matches_bruteforce(intervals):
    starts, ends = TextInjector._disjoint_intervals(list(intervals))
    probes = [(0, 1), (5, 12), (9, 11), (10, 20), (19, 21), (20, 21),
              (39, 41), (40, 50), (49, 51), (55, 65), (99, 101), (105, 195),
              (150, 260), (210, 300)]
    for a, b in probes:
        got = TextInjector._hits_disjoint(starts, ends, a, b)
        assert got == brute_hits(intervals, a, b), (intervals, a, b)


# ── _consume_free_run ──────────────────────────────────────────────────────

def test_consume_top_of_run(inj):
    """Запись в верх прогона: остаётся левая часть."""
    runs = [(100, 200)]
    assert inj._consume_free_run(runs, 190, 10) is True
    assert runs == [(100, 190)]


def test_consume_whole_run(inj):
    runs = [(100, 110)]
    assert inj._consume_free_run(runs, 100, 10) is True
    assert runs == [(100, 100)]


def test_consume_middle_keeps_right_leftover(inj):
    """Аллокация не в верху (внешний вызывающий) — место не теряется."""
    runs = [(100, 200)]
    assert inj._consume_free_run(runs, 120, 10) is True
    assert runs == [(100, 120), (130, 200)]


def test_consume_middle_keeps_sorting_and_starts(inj):
    runs = [(100, 200), (300, 400)]
    assert inj._consume_free_run(runs, 120, 10) is True
    assert inj._free_starts(runs) == [100, 130, 300]
    # второй вызов обязан найти уже другой прогон по обновлённым началам
    assert inj._consume_free_run(runs, 390, 10) is True
    assert runs == [(100, 120), (130, 200), (300, 390)]


def test_consume_picks_the_containing_run(inj):
    runs = [(0, 50), (100, 200), (300, 400)]
    assert inj._consume_free_run(runs, 390, 10) is True
    assert runs == [(0, 50), (100, 200), (300, 390)]


def test_consume_outside_any_run(inj):
    runs = [(0, 50), (100, 200)]
    assert inj._consume_free_run(runs, 80, 10) is False
    assert runs == [(0, 50), (100, 200)]


def test_consume_unsorted_list_falls_back(inj):
    """Чужой неотсортированный список обязан обработаться, а не зависнуть."""
    runs = [(100, 200), (0, 50)]
    assert inj._consume_free_run(runs, 190, 10) is True
    assert (100, 190) in runs


def test_consume_empty_list(inj):
    assert inj._consume_free_run([], 10, 5) is False


# ── _free_starts ───────────────────────────────────────────────────────────

def test_free_starts_detects_unsorted(inj):
    assert inj._free_starts([(10, 20), (30, 40)]) == [10, 30]
    assert inj._free_starts([(30, 40), (10, 20)]) is None


def test_free_starts_cached_by_object(inj):
    first = [(10, 20), (30, 40)]
    assert inj._free_starts(first) == [10, 30]
    other = [(10, 20), (30, 40), (50, 60)]  # другой объект, та же длина пар
    assert inj._free_starts(other) == [10, 30, 50]


def test_free_starts_empty(inj):
    assert inj._free_starts([]) == []


# ── эталон прежнего алгоритма ──────────────────────────────────────────────

def legacy_choose_dest(free_runs, occupied, payload_len, rom_len):
    """Кандидат по СТАРОМУ коду: линейный any() по занятым интервалам."""
    for start, stop in reversed(free_runs):
        if stop - start < payload_len:
            continue
        if start < 0 or stop > rom_len or start >= stop:
            continue
        cand = stop - payload_len
        if cand < 0:
            continue
        if not any(cand < b and a < cand + payload_len for a, b in occupied):
            return cand
    return None


def legacy_consume(free_runs, dest, payload_len):
    """Прежний учёт съеденного прогона: линейный поиск, del + append."""
    for i in range(len(free_runs)):
        start, stop = free_runs[i]
        if start <= dest and dest + payload_len <= stop:
            del free_runs[i]
            if start < dest:
                free_runs.append((start, dest))
            if dest + payload_len < stop:
                free_runs.append((dest + payload_len, stop))
            break


def modern_consume(inj, free_runs, dest, payload_len):
    """Новый учёт — ровно то, что вызывает `_relocate_dialogue`."""
    return inj._consume_free_run(free_runs, dest, payload_len)


SCENARIOS = [
    # (список прогонов, список занятых интервалов, rom_len, payload_len)
    ([(0, 100), (200, 300)], [], 1000, 10),
    ([(0, 100), (200, 300)], [(200, 210)], 1000, 10),
    ([(0, 100), (200, 300)], [(290, 300)], 1000, 10),
    ([(0, 100), (200, 300)], [(200, 300)], 1000, 10),
    ([(500, 600), (300, 400), (0, 50)], [(320, 330)], 1000, 20),
    ([(0, 1000)], [(990, 1000)], 1000, 10),
    ([(0, 40), (100, 130), (200, 260), (300, 310)], [(110, 120)], 1000, 15),
    ([(0, 100), (100, 200)], [], 1000, 50),
]


@pytest.mark.parametrize('runs,occupied,rom_len,plen', SCENARIOS)
def test_dest_matches_legacy_algorithm(inj, runs, occupied, rom_len, plen):
    """Выбор места совпадает с прежним алгоритмом.

    Оптимизация обязана менять только скорость, поэтому эталон живёт здесь
    целиком: без него утверждение «то же самое, только быстрее» нечем
    проверить. Раньше такую сверку можно было сделать только на реальном ROM,
    которых в репозитории нет.
    """
    want = legacy_choose_dest(list(runs), list(occupied), plen, rom_len)
    starts, ends = TextInjector._disjoint_intervals(list(occupied))
    got = None
    for start, stop in reversed(list(runs)):
        if stop - start < plen or start < 0 or stop > rom_len or start >= stop:
            continue
        cand = stop - plen
        if cand < 0:
            continue
        if not TextInjector._hits_disjoint(starts, ends, cand, cand + plen):
            got = cand
            break
    assert got == want


@pytest.mark.parametrize('runs,occupied,rom_len,plen', SCENARIOS)
def test_consume_matches_legacy_and_keeps_index_in_sync(inj, runs, occupied,
                                                         rom_len, plen):
    """Учёт прогона даёт ту же картину свободного места и не ломает индекс.

    Старый код дописывал остатки в КОНЕЦ списка (ломая сортировку), новый
    укорачивает прогон на месте. На практике правый остаток не возникает
    (кандидат всегда в верху прогона), поэтому на этих сценариях результаты
    совпадают — и это фиксируется здесь явно.
    """
    dest = legacy_choose_dest(list(runs), list(occupied), plen, rom_len)
    if dest is None:
        return
    legacy_runs = list(runs)
    legacy_consume(legacy_runs, dest, plen)
    modern_runs = list(runs)
    modern_consume(inj, modern_runs, dest, plen)
    # Свободное место то же самое (как отсортированный набор прогонов).
    assert sorted(modern_runs) == sorted(legacy_runs)
    if runs == sorted(runs):
        # Для отсортированного входа порядок обязан остаться пригодным для
        # бисекта — на этом держится кэш начал. Для чужого неотсортированного
        # списка новый код работает линейным запасным путём и порядок не
        # чинит (это документировано в `_free_starts`).
        assert modern_runs == sorted(modern_runs)
        assert inj._free_starts(modern_runs) == [r[0] for r in modern_runs]


def test_repeated_consumes_keep_index_in_sync(inj):
    """Много последовательных аллокаций: кэш не должен разъехаться.

    Единственная проверка самого кэша: после каждого шага нача��а в кэше
    обязаны совпадать с реальным списком, иначе бисект указывает не на тот
    прогон.
    """
    runs = [(i * 100, i * 100 + 60) for i in range(20)]
    assert inj._free_starts(runs) == [r[0] for r in runs]
    consumed = 0
    for plen in (10, 20, 30, 40, 50, 60):
        for _ in range(6):
            # Так же, как выбирает `_relocate_dialogue`: первый сверху прогон,
            # в который влезает payload.
            dest = next((stop - plen for start, stop in reversed(runs)
                         if stop - start >= plen), None)
            if dest is None:
                continue
            assert inj._consume_free_run(runs, dest, plen) is True
            consumed += 1
            assert runs == sorted(runs)
            assert inj._free_starts(runs) == [r[0] for r in runs]
            assert len(runs) == 20  # остатки не добавляются и не теряются
    assert consumed >= 30
