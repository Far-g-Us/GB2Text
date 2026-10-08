"""Защита от записи в чужой сегмент (generic-путь).

Контекст: на Pokémon Odyssey окно сегмента способностей
`[0x24FC40, 0x250036)` накрывает запись диалога 607 по `0x250026`.
Generic-путь писал от своей базы, не сверяясь с чужими диапазонами, и
затирал запись диалога; обратное извлечение показывало вместо перевода
чужой текст. Здесь зафиксированы все три правила `_foreign_ranges`:

  1. свой сегмент в чужие не попадает;
  2. диалоговый пул даёт ПОЗАПИСНЫЕ окна, а не весь coarse-блок —
     иначе любой соседний сегмент отвергался бы целиком;
  3. read-only алиасы (`injectable: False`, `alias_of`) чужими НЕ считаются:
     их окна по построению лежат внутри окон канонических записей,
     и без этого правила запись в хост FF4 отвергалась бы как
     пересечение с собственным алиасом.
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.injector import TextInjector

ROM_SIZE = 512


class _AsciiDecoder:
    def decode(self, data, start, length):
        return bytes(data[start:start + length]).split(b'\x00')[0].decode(
            'ascii', 'replace')

    def encode(self, text):
        return text.encode('ascii')


def _injector(segments: dict[str, list[dict]]) -> TextInjector:
    inj = TextInjector.__new__(TextInjector)

    class _FakeROM:
        data: bytearray

        def __init__(self, data):
            self.data = bytearray(data)

    inj.rom = _FakeROM(bytearray(ROM_SIZE))
    inj.original_data = bytearray(ROM_SIZE)
    inj.modified_data = bytearray(ROM_SIZE)
    inj._segment_cache = {k: list(v) for k, v in segments.items()}
    inj._bank_segments = []
    inj._taken_free_blocks = []
    inj._written_spans = []
    inj.last_overflow_report = []
    inj.last_relocate_report = []
    inj.last_overlap_report = []
    inj.last_spellcheck_report = []
    inj.last_fit_report = []
    inj.last_unmapped_chars = []
    inj.logger = logging.getLogger('test')
    return inj


def _plain(name: str, start: int, end: int) -> dict:
    return {'name': name, 'kind': 'pointer_text', 'start': start,
            'end': end, 'injectable': True, 'decoder': _AsciiDecoder(),
            'terminator': b'\x00', 'terminators': [0x00], 'pad_byte': 0x00}


def _dialogue_pool(name: str, records: list[tuple[int, int]]) -> dict:
    return {
        'name': name, 'kind': 'pointer_dialogues',
        # coarse-блок шире любой записи: именно его нельзя отдавать как
        # «чужой диапазон» целиком
        'start': records[0][0], 'end': records[-1][0] + records[-1][1] + 64,
        'injectable': True, 'decoder': _AsciiDecoder(),
        'terminator': b'\x00', 'terminators': [0x00],
        'manifest': [{'target': t, 'free_after': r} for t, r in records],
    }


def test_own_segment_is_not_foreign():
    seg = _plain('own', 100, 200)
    inj = _injector({'game': [seg]})
    assert inj._foreign_ranges('own') == []


def test_plain_segment_contributes_its_window():
    other = _plain('other', 300, 320)
    inj = _injector({'game': [_plain('own', 100, 200), other]})
    assert inj._foreign_ranges('own') == [(300, 320)]


def test_dialogue_pool_contributes_per_record_not_coarse_block():
    pool = _dialogue_pool('dialogues', [(400, 16), (450, 16)])
    inj = _injector({'game': [_plain('own', 100, 200), pool]})
    assert inj._foreign_ranges('own') == [(400, 416), (450, 466)]


def test_read_only_catalog_is_still_protected():
    """`injectable: False` сам по себе сегмент из защиты НЕ выводит.

    Такой флаг стоит у каталогов, которые фреймворк всё равно
    пересобирает (Castlevania `cvas_*`, MLSS `mlss_*`).
    """
    ro = _plain('cvas_en_3', 300, 320)
    ro['injectable'] = False
    inj = _injector({'game': [_plain('own', 100, 200), ro]})
    assert inj._foreign_ranges('own') == [(300, 320)]


def test_mid_alias_inside_own_window_is_not_foreign():
    """FF4: отдельная запись указывает В СЕРЕДИНУ другой — это алиас.

    Её окно лежит внутри окна хоста, поэтому хост обязан остаться
    записываемым. Окна взяты ВНУТРИ тестовой ROM (512 байт): прежний вариант
    использовал реальные адреса FF4 (0x2e9b39), `_coarse_range` их
    отбрасывал по `end <= rom_size`, и проверка была пустой.
    """
    host = _plain('host', 400, 440)
    alias = _plain('host_mid', 410, 420)
    alias['injectable'] = False
    alias['alias_of'] = 'host'
    inj = _injector({'game': [host, alias]})
    assert inj._foreign_ranges('host', host['start'], host['end']) == []
    lo, hi = inj._own_span(host)
    assert inj._foreign_hit(inj._foreign_index(), 'host', host,
                           410, 10, lo, hi) is False


def test_suffix_alias_inside_own_window_is_not_foreign():
    """FF4/FF5: суффиксный алиас — тоже окно внутри окна хоста."""
    host = _plain('host', 400, 440)
    alias = _plain('host_tail', 420, 440)
    alias['injectable'] = False
    alias['alias_of'] = 'host'
    inj = _injector({'game': [host, alias]})
    assert inj._foreign_ranges('host', host['start'], host['end']) == []


def test_read_only_window_outside_own_window_still_protected():
    """Окно снаружи окна хоста — даже read-only остаётся чужим."""
    host = _plain('host', 100, 140)
    far = _plain('cvas_en_3', 300, 320)
    far['injectable'] = False
    inj = _injector({'game': [host, far]})
    assert inj._foreign_ranges('host', host['start'], host['end']) == [(300, 320)]


def test_writable_window_inside_own_window_still_protected():
    """Внутри окна хоста, но записываемый — это уже чужой сегмент.

    Именно этот случай на Odyssey: окно способностей накрывает записи
    диалога, и он обязан остаться защищённым.
    """
    abilities = _plain('abilities', 100, 400)
    dialogue = _plain('dialogues', 300, 320)
    inj = _injector({'game': [abilities, dialogue]})
    assert inj._foreign_ranges('abilities', 100, 400) == [(300, 320)]


def _idx(*pairs, alias_of=None):
    """Индекс из пар (start, end); `alias_of` — хозяин для правила алиаса.

    Последний элемент — префиксный максимум концов; для одноэлементного
    индекса он равен концу самого окна.
    """
    return [(a, b, -1, 'other', True, alias_of, False, 0, ROM_SIZE, b)
            for a, b in pairs]


def test_containment_is_still_an_overlap():
    """Регрессия Odyssey: окно способностей СОВПАДАЕТ с записью диалога.

    Таблица способностей начинается с 0x24FC40, ширина слота 13 ⇒ слот 15
    это ровно 0x24FD03, а это адрес записи диалога (free_after 13). Раньше
    здесь стояло исключение «чужое окно внутри моей записи — не пересечение»,
    и оно проглатывало ровно ту запись, ради защиты которой всё затевалось:
    13 байт затирались, отчёт был пуст.

    Исключение теперь только для АЛИАСОВ, поэтому обычное окно внутри нашей
    записи остаётся пересечением.
    """
    idx = _idx((0x24FD03, 0x24FD10))
    assert TextInjector._foreign_hit(idx, 'own', None, 0x24FD03, 13) is True


def test_partial_overlap_is_overlap():
    """Чужое окно, вылезающее за пределы нашей записи, — конфликт."""
    # запись [400, 440), чужая [430, 450) — вылезает направо
    idx = _idx((430, 450))
    assert TextInjector._foreign_hit(idx, 'own', None, 400, 40) is True
    # вылезает налево
    idx = _idx((390, 410))
    assert TextInjector._foreign_hit(idx, 'own', None, 400, 40) is True


def test_touching_ranges_are_not_overlap():
    """FF4-записи идут вплотную: касание концом пересечением не считается."""
    assert TextInjector._foreign_hit(
        _idx((440, 460)), 'own', None, 400, 40) is False
    assert TextInjector._foreign_hit(
        _idx((380, 400)), 'own', None, 400, 40) is False


def test_overlap_uses_full_written_width_not_payload():
    """Ключевой случай: non-fixed запись паддится до room и пишется целиком.

    Проверка по длине payload пропускала бы затирание хвоста чужой записи,
    когда перевод КОРОЧЕ оригинала (именно Odyssey).
    """
    # запись [300, 313): пишем 5 байт текста, в ROM уходит 13 (room=13)
    idx = _idx((306, 314))  # вылезает за 313 => настоящее пересечение
    assert TextInjector._foreign_hit(idx, 'own', None, 300, 13) is True
    # «по payload» старая проверка здесь дала бы False — баг был именно тут
    assert TextInjector._foreign_hit(idx, 'own', None, 300, 5) is False


def test_non_alias_inside_own_window_is_still_overlap():
    """Широкий пишущий сегмент не должен разрешать запись внутрь себя.

    Именно из-за этого правило ограничено алиасами: каталог способностей на
    Odyssey — 1014 байт, и обычное «чужое окно внутри моего» превратило бы
    симметричный бан в приоритет каталога (решение, которое отвергнуто:
    порча хуже непереведённой строки).
    """
    own = _plain('abilities', 300, 400)
    dialogue = _plain('dialogues', 306, 314)
    inj = _injector({'game': [own, dialogue]})
    lo, hi = inj._own_span(own)
    assert inj._foreign_hit(inj._foreign_index(), 'abilities', own,
                           306, 8, lo, hi) is True


def test_alias_inside_own_window_is_not_overlap():
    """Алиас внутри окна хозяина — те же байты, не конфликт."""
    host = _plain('host', 100, 200)
    alias = _plain('host_alias', 120, 140)
    alias['injectable'] = False
    alias['alias_of'] = 'host'
    inj = _injector({'game': [host, alias]})
    lo, hi = inj._own_span(host)
    assert inj._foreign_hit(inj._foreign_index(), 'host', host,
                           120, 20, lo, hi) is False


def test_pool_without_manifest_falls_back_to_coarse_window():
    """fail-closed: пул без валидного манифеста защищает coarse-окном.

    Молчаливое «не защищено» повторило бы ровно тот баг, ради которого
    написан гард.
    """
    pool = _dialogue_pool('dialogues', [(400, 16)])
    pool['manifest'] = None
    own = _plain('own', 100, 200)
    inj = _injector({'game': [own, pool]})
    idx = inj._foreign_index()
    assert (400, 480) in [(a, b) for a, b, *_ in idx]


def test_window_validation():
    """Мусор в границах окна не должен превращаться в «нет окна» или падать."""
    pair = TextInjector._window_pair
    assert pair(100, 200) == (100, 200)
    assert pair(200, 100) is None      # перевёрнутое
    assert pair(True, 200) is None     # bool
    assert pair(100, False) is None
    assert pair(None, 200) is None
    assert pair('a', 'b') is None


def test_coarse_range_validation():
    inj = _injector({'game': []})
    assert inj._coarse_range({'start': 100, 'end': 200}) == [(100, 200)]
    # за пределами ROM, bool, перевёрнутое, мусор — окна нет
    assert inj._coarse_range({'start': 0, 'end': ROM_SIZE + 1}) == []
    assert inj._coarse_range({'start': True, 'end': 200}) == []
    assert inj._coarse_range({'start': 200, 'end': 100}) == []
    assert inj._coarse_range({}) == []


def test_same_name_segments_are_not_treated_as_own():
    """Имена сегментов не уникальны: свой определяется по identity+окну.

    Два экземпляра плагина держат сегменты с одинаковым именем, но разными
    окнами (tests/test_injector.py::test_instances_with_distinct_segments_
    not_contaminated). Исключение по имени выбросило бы чужое окно из защиты.
    """
    mine = _plain('test', 100, 200)
    theirs = _plain('test', 150, 250)
    inj = _injector({'game': [mine, theirs]})
    assert inj._foreign_ranges('test', 100, 200, mine) == [(150, 250)]


def test_same_name_same_window_copy_is_treated_as_own():
    """Вызывающий может передать КОПИЮ сегмента — identity тогда не совпадёт.

    Тот же сегмент, пересозданный вызывающим (`segments=[...]` заново),
    не должен защищаться от самого себя.
    """
    mine = _plain('test', 100, 200)
    copy = _plain('test', 100, 200)
    inj = _injector({'game': [mine, copy]})
    assert inj._foreign_ranges('test', 100, 200, mine) == []


def test_mid_alias_is_excluded_only_by_alias_of():
    """Read-only без alias_of — не алиас, даже если окно внутри нашего."""
    host = _plain('host', 400, 440)
    ro = _plain('cvas_en_3', 410, 420)
    ro['injectable'] = False
    inj = _injector({'game': [host, ro]})
    assert inj._foreign_ranges('host', host['start'], host['end']) == [(410, 420)]
    # а тот же сегмент, помеченный как алиас хоста, — уже не чужой
    ro['alias_of'] = 'host'
    assert inj._foreign_ranges('host', host['start'], host['end']) == []


def test_missing_manifest_falls_back_to_coarse_window():
    """Без манифеста позаписных окон нет — защита не отключается (fail-closed)."""
    pool = _dialogue_pool('dialogues', [(400, 16)])
    pool['manifest'] = None
    inj = _injector({'game': [_plain('own', 100, 200), pool]})
    assert inj._foreign_ranges('own') == [(400, 480)]


def test_dialogue_record_ranges_validation():
    """Мусор в манифесте не должен ни падать, ни защищать что попало."""
    seg = {'kind': 'pointer_dialogues', 'manifest': [
        'не-dict',
        {'target': True, 'free_after': 8},        # bool вместо int
        {'target': 400},                           # нет free_after
        {'target': 410, 'free_after': 0},          # нулевая комната
        {'target': 410, 'free_after': -4},         # отрицательная
        {'target': 10_000, 'free_after': 8},       # за пределами ROM
        {'target': 500, 'free_after': 8},          # валидная
    ]}
    assert TextInjector._dialogue_record_ranges(seg, ROM_SIZE) == [(500, 508)]
    assert TextInjector._dialogue_record_ranges({'kind': 'x'}, ROM_SIZE) == []


# Поведение generic-пути целиком (пропуск чужой записи + запись в отчёт)
# проверяется реальным ROM-тестом на Pokémon Odyssey, где окно сегмента
# способностей накрывает запись диалога: см.
# tests/test_realrom_pipeline.py. Здесь фиксируется чистая геометрия
# диапазонов, чтобы правка не вернулась молча.


# --------------------------------------------------------------------------
# Индекс чужих диапазонов: `_foreign_index` + `_foreign_hit`.
#
# Список строится ОДИН раз и кэшируется по сигнатуре кэша сегментов: старый
# вариант пересобирал его на каждый сегмент (на Golden Sun это 10863 x 10863
# окон, 118 млн вызовов и 711 секунд на один тест). Здесь зафиксированы
# правила ответа, а не только производительность: индексация не должна
# менять того, что считается пересечением.
# --------------------------------------------------------------------------


def test_index_is_cached_and_not_rebuilt_per_segment():
    seg_a = _plain('a', 16, 32)
    seg_b = _plain('b', 40, 56)
    inj = _injector({'game': [seg_a, seg_b]})
    first = inj._foreign_index()
    assert inj._foreign_index() is first, 'индекс пересобирается на каждый вызов'
    # Новый список сегментов (тот же состав) — пересборка обязательна.
    inj._segment_cache = {'game': [_plain('a', 16, 32), _plain('b', 40, 56)]}
    assert inj._foreign_index() is not first


def test_hit_detects_foreign_window():
    """Чужое окно, начавшееся ДО base и кончившееся после, — пересечение.

    Регрессия: ранний выход по «первому b <= base» при обходе назад
    пропускал именно это окно, потому что массив отсортирован по НАЧАЛУ, а
    не по концу. Префиксный максимум концов в индексе нужен именно для этого.
    """
    mine = _plain('mine', 100, 200)
    other = _plain('other', 90, 110)
    inj = _injector({'game': [mine, other]})
    idx = inj._foreign_index()
    assert inj._foreign_hit(idx, 'mine', mine, 100, 5) is True


def test_hit_ignores_touching_window():
    """Касание концом пересечением не считается (FF4-записи идут вплотную)."""
    mine = _plain('mine', 100, 200)
    other = _plain('other', 200, 240)
    inj = _injector({'game': [mine, other]})
    idx = inj._foreign_index()
    assert inj._foreign_hit(idx, 'mine', mine, 100, 100) is False


def test_hit_ignores_own_segment_by_identity():
    mine = _plain('mine', 100, 200)
    inj = _injector({'game': [mine]})
    idx = inj._foreign_index()
    assert inj._foreign_hit(idx, 'mine', mine, 100, 100) is False


def test_hit_ignores_same_name_and_window_copy():
    """Вызывающий мог передать копию сегмента — прежний код отсекал по паре
    «имя + окно», и на этом стоит тест с двумя одноимёнными банками."""
    original = _plain('bank', 64, 192)
    copy = _plain('bank', 64, 192)
    inj = _injector({'game': [original, copy]})
    idx = inj._foreign_index()
    assert inj._foreign_hit(idx, 'bank', original, 64, 8) is False


def test_hit_ignores_alias_inside_own_segment():
    """Суффиксный алиас лежит ВНУТРИ окна своей записи — не пересечение.

    Окно алиаса может кончаться на границе окна сегмента, тогда как сама
    запись пишется на байт короче (FF5). Поэтому граница «своих байтов»
    берётся по окну СЕГМЕНТА, а не по спану записи.

    Окна лежат ВНУТРИ тестовой ROM (прежние реальные адреса FF4 давали
    пустой индекс, и тест был вакуумным), плюс НЕГАТИВНЫЙ контроль: тот же
    фикстуар со снятым признаком алиаса обязан дать пересечение — иначе
    пустой индекс снова «проверит» что угодно.
    """
    host = _plain('ff5_text_1', 0x100, 0x13E)
    alias = _plain('ff5_text_2', 0x103, 0x13E)
    alias['injectable'] = False
    alias['alias_of'] = 'ff5_text_1'
    inj = _injector({'game': [host, alias]})
    idx = inj._foreign_index()
    assert idx, 'индекс пуст — тест ничего не проверяет'
    lo, hi = inj._own_span(host)
    # запись короче окна сегмента на байт — алиас всё равно свой
    assert inj._foreign_hit(idx, 'ff5_text_1', host, 0x100, 61, lo, hi) is False

    # Негативный контроль: то же окно БЕЗ признака алиаса — конфликт.
    plain = _plain('ff5_text_3', 0x103, 0x13E)
    inj2 = _injector({'game': [host, plain]})
    idx2 = inj2._foreign_index()
    assert idx2, 'индекс пуст'
    assert inj2._foreign_hit(idx2, 'ff5_text_1', host, 0x100, 61, lo, hi) is True


def test_index_matches_full_scan_oracle():
    """Эквивалентность индексной проверки и полного перебора.

    Эталон — `_foreign_ranges`, до-индексная реализация. Он намеренно
    остаётся отдельным кодом: если он начнёт делегировать индексу, тест
    станет тавтологией. Плюс рукописная таблица ожиданий ниже.

    Гард индекс — это оптимизация, а не новое правило: на любом сочетании
    сегментов и адресов он должен совпадать с полным перебором
    `_foreign_ranges` + проверкой пересечения. Синтетический набор покрывает
    все виды сегментов, которые встречаются в проекте: обычный, алиас,
    read-only каталог, пул диалогов с манифестом и без, одноимённую копию.
    """
    plain = _plain('plain', 40, 80)
    other = _plain('other', 100, 140)
    alias = _plain('alias', 60, 70)
    alias['injectable'] = False
    alias['alias_of'] = 'plain'
    readonly = _plain('catalog', 200, 240)
    readonly['injectable'] = False
    readonly['fixed_width'] = 13
    pool = _dialogue_pool('pool', [(300, 16), (320, 16)])
    poolless = _dialogue_pool('poolless', [(400, 16)])
    poolless['manifest'] = None
    twin = _plain('plain', 40, 80)

    # Класс 1: алиас, чьё окно ВЫХОДИТ за окно хозяина. `alias_of` совпадает,
    # но containment не выполняется — эталон такой алиас блокирует.
    outside = _plain('outside', 76, 96)
    outside['injectable'] = False
    outside['alias_of'] = 'plain'
    # Класс 2: `alias_of` на ИНЖЕКТИРУЕМОМ сегменте: эталон требует
    # `injectable is False`, поэтому пересечение блокируется.
    tagged = _plain('tagged', 60, 72)
    tagged['alias_of'] = 'plain'
    # Класс 3: сегмент, у которого `alias_of` равен имени ПУЛА. Эталон для
    # пулов делает `continue` до правила алиаса — правило не применяется.
    pool_alias = _plain('pool_alias', 300, 310)
    pool_alias['injectable'] = False
    pool_alias['alias_of'] = 'pool'

    segments = [plain, other, alias, readonly, pool, poolless, twin,
                outside, tagged, pool_alias]
    # Второй ключ кэша: мультиплагиновый путь (два независимых списка).
    second = _plain('second_game_only', 440, 470)
    inj = _injector({'game': segments, 'other_game': [second]})
    idx = inj._foreign_index()
    assert len(idx) >= 12

    probes = [(30, 10), (40, 5), (45, 10), (40, 40), (60, 10), (65, 5),
              (76, 8), (80, 16), (90, 6), (100, 40), (200, 40),
              (300, 16), (304, 6), (310, 20), (320, 16),
              (400, 16), (410, 8), (440, 30), (42, 0), (490, 10)]
    checked = 0
    for seg in segments:
        lo, hi = inj._own_span(seg)
        for base, length in probes:
            if length == 0:
                # Заведомо известное расхождение, задокументированное в
                # докстринге `_foreign_hit`: запись нулевой длины не пишет
                # ни байта, поэтому конфликта нет, хотя арифметика полного
                # перебора на strictly-содержащем окне дала бы True. Проверяем
                # это поведение явно, а не замалчиваем в цикле.
                assert inj._foreign_hit(idx, seg.get('name'), seg, base,
                                        length, lo, hi) is False
                continue
            expected = any(
                base < b and a < base + length
                for a, b in inj._foreign_ranges(seg.get('name'), lo, hi, seg))
            got = inj._foreign_hit(idx, seg.get('name'), seg, base, length,
                                   lo, hi)
            assert got == expected, (
                f'{seg.get("name")} @{base:#x}+{length}: '
                f'индекс={got}, перебор={expected}')
            checked += 1
    assert checked >= 90, checked


def test_oracle_classes_blocked_explicitly():
    """Три fail-open класса закрыты — проверяем ожидания явно, не оракулом."""
    plain = _plain('plain', 40, 80)
    outside = _plain('outside', 76, 96)
    outside['injectable'] = False
    outside['alias_of'] = 'plain'
    tagged = _plain('tagged', 60, 72)
    tagged['alias_of'] = 'plain'
    pool = _dialogue_pool('pool', [(300, 16)])
    pool_alias = _plain('pool_alias', 300, 310)
    pool_alias['injectable'] = False
    pool_alias['alias_of'] = 'pool'

    inj = _injector({'game': [plain, outside, tagged, pool, pool_alias]})
    idx = inj._foreign_index()
    lo, hi = inj._own_span(plain)
    # 1. окно алиаса выходит за окно хозяина — конфликт
    assert inj._foreign_hit(idx, 'plain', plain, 78, 4, lo, hi) is True
    # 2. alias_of на инжектируемом сегменте — конфликт
    assert inj._foreign_hit(idx, 'plain', plain, 60, 8, lo, hi) is True
    # 3. алиас с alias_of == имя пула — конфликт (для пулов правило алиаса
    #    в эталоне не применяется вовсе)
    assert inj._foreign_hit(idx, 'pool', pool, 302, 4, *inj._own_span(pool)) \
        is True

    # 4. САМ пул, помеченный как алиас пишущей записи: правило алиаса для
    #    пулов не применяется, поэтому это конфликт, а не «свои байты».
    #    Именно `not is_pool` в предикате это решает; без него `alias_of`
    #    снял бы блок. Ни один плагин сегодня так не делает — ветка
    #    защитная, поэтому и закрепляется синтетикой.
    tagged_pool = _dialogue_pool('plain', [(60, 10)])
    tagged_pool['injectable'] = False
    tagged_pool['alias_of'] = 'plain'
    inj3 = _injector({'game': [plain, tagged_pool]})
    idx3 = inj3._foreign_index()
    assert inj3._foreign_hit(idx3, 'plain', plain, 62, 4, lo, hi) is True

    # Контроль: настоящий алиас внутри окна хозяина — не конфликт.
    inner = _plain('inner', 60, 70)
    inner['injectable'] = False
    inner['alias_of'] = 'plain'
    inj2 = _injector({'game': [plain, inner]})
    idx2 = inj2._foreign_index()
    assert inj2._foreign_hit(idx2, 'plain', plain, 78, 4, lo, hi) is False
    assert inj2._foreign_hit(idx2, 'plain', plain, 60, 4, lo, hi) is False


def test_own_span_is_disabled_for_pool_and_catalogue():
    """Правило «окно сегмента = свои байты» применимо не ко всем сегментам.

    У пула диалогов и у fixed-width каталога окно сегмента — это ВЕСЬ блок
    или сетка слотов, и такое правило разрешило бы запись в чужую запись
    внутри (ровно случай Odyssey с блоком способностей).
    """
    pool = {'name': 'd', 'kind': 'pointer_dialogues', 'start': 0, 'end': 100}
    assert TextInjector._own_span(pool) == (None, None)
    fixed = {'name': 'a', 'start': 0, 'end': 100, 'fixed_width': 13}
    assert TextInjector._own_span(fixed) == (None, None)
    bank = {'name': 'b', 'start': 0, 'end': 100, 'bank_meta': {'offsets': []}}
    assert TextInjector._own_span(bank) == (None, None)
    single = {'name': 'c', 'start': 0, 'end': 100}
    assert TextInjector._own_span(single) == (0, 100)



def test_index_rebuilds_when_list_object_is_replaced():
    """Новый список сегментов — даже той же длины — обязан пересобрать индекс."""
    seg = _plain('a', 16, 32)
    inj = _injector({'game': [seg]})
    first = inj._foreign_index()
    other = _plain('b', 40, 56)
    inj._segment_cache = {'game': [seg, other]}
    assert inj._foreign_index() is not first


def test_index_keeps_reference_so_freed_id_is_not_reused():
    """Кэш держит ССЫЛКУ на списки, а не только их id.

    `id()` освобождённого списка переиспользуется: новый список с тем же id
    и той же длиной получил бы чужой индекс, и защита молча пропала бы. Именно
    это воспроизводилось в `test_pointer_dialogues_branches`.
    """
    seg = _plain('p', 0x4000, 0x4020)
    inj = _injector({'game': [seg]})
    first = inj._foreign_index()
    srcs = getattr(inj, '_foreign_index_src', None)
    assert srcs is not None and any(s is not None for s in srcs), \
        'кэш индекса обязан удерживать ссылки на списки сегментов'
    assert inj._foreign_index() is first


def test_by_name_cache_and_validation_cache_follow_the_list():
    """Кэши словаря имён и валидации привязаны к тому же списку."""
    seg_a = _plain('a', 16, 32)
    inj = _injector({'game': [seg_a]})
    assert inj._segments_by_name([seg_a])['a'] is seg_a
    seg_b = _plain('b', 40, 56)
    fresh = [seg_a, seg_b]
    assert inj._segments_by_name(fresh)['b'] is seg_b
    assert inj._validated(fresh) is fresh



if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
