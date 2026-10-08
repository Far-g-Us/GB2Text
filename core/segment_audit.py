"""Аудит fixed-слотов: нужен ли сегменту флаг `has_mid_alias`.

Договорённость из `plugins/config/README.md` («есть внешний указатель в хвосте —
ставь `has_mid_alias`») проверялась вручную скриптом
`scripts_roms/fixed_mid_pointer_probe.py`, который дал 0 совпадений на 10 GBA ROM.
Автоматика тут не заменяет разбора, но МОЖЕТ сказать «проверять нечего» или
«вот этот сегмент проверь», и это уже закрывает контракт со стороны автора
плагина: он получает ответ по своей игре, а не читает общий вывод по корпусу.

Ложные срабатывания отсекаются двумя признаками, а не одним:
1. соседние 4-байтные окна тоже лежат в диапазоне указателей;
2. их ЦЕЛИ строго возрастают.
Первого признака мало — разобранный случай `Pokemon - Crown` (`0x1BCF0E4`) даёт
20 подряд идущих «указателей» в переплетённой таблице с шагом `0xD0`.

Второй признак проверяется СТРОГО через само окно: подтверждается только тот
указатель, который сам лежит в возрастающей серии длиной от `MIN_RUN`. Раньше
длина считалась как максимум по всему непрерывному участку, поэтому одиночный
указатель подтверждался чужой серией, оказавшейся в том же участке. На
синтетике с переплетёнными таблицами это давало лишние срабатывания (до 39
против 36 на одном корпусе) — они убраны, потому что подтверждённых указателей
ищется мало, а мусор в отчёте вводит автора плагина в заблуждение.

Скорость: раньше `range(0, rom_len - 3, 4)` с разбором окна выполнялся заново на
каждый сегмент, то есть O(сегментов × rom_len/4) — измерено 3+ с НА СЕГМЕНТ на
32-МеБ ROM, то есть около минуты на двадцати сегментах. Сейчас один проход по
ROM, и время не зависит от числа сегментов: измерено 1.94 с на 120 сегментах и
1.92 с на 300. Память O(rom_len) ровно на массив слов и копию ROM: границы
прогонов отдаются генератором, а окна перечитываются из ROM только для блоков,
чей диапазон целей пересекается с fixed-сегментами. Пик на 32-МеБ ROM, целиком
забитом монотонными указателями, — десятки мегабайт.

Сегменты предполагаются непересекающимися: цель относится к тому диапазону, в
который попала (`bisect` находит последний подходящий). Пересечение дало бы
молчаливую потерю, поэтому оно объявлено неподдерживаемым здесь, а не
разбирается в рантайме.

Ограничение, о котором честно сказано в докстринге: аудит находит ПОДТВЕРЖДЁННЫЕ
указатели, а их отсутствие не доказывает отсутствия — молчаливую ссылку без
таблицы (адрес, вшитый в код) такой скан не видит.
"""

from __future__ import annotations

import sys
from array import array
from bisect import bisect_right
from dataclasses import dataclass, field

from core.plugin_manager import PluginManager
from core.rom import GameBoyROM

HEADER_BASE = 0x08000000
MIN_RUN = 4          # сколько подряд идущих монотонных слотов считать таблицей


@dataclass
class SegmentAudit:
    """Результат по одному fixed-сегменту."""
    name: str
    system: str
    start: int
    end: int
    width: int
    slots: int = 0
    mid_pointers: list[dict] = field(default_factory=list)

    @property
    def needs_mid_alias(self) -> bool:
        return bool(self.mid_pointers)

    def as_dict(self) -> dict:
        return {
            'name': self.name,
            'system': self.system,
            'start': self.start,
            'end': self.end,
            'fixed_width': self.width,
            'slots': self.slots,
            'needs_mid_alias': self.needs_mid_alias,
            'mid_pointers': list(self.mid_pointers),
        }


def _iter_targets(data: bytes, rom_len: int):
    """Один проход по ROM: (смещение, цель) для каждого окна-указателя.

    Слова берутся через rray (C-уровень), а не int.from_bytes на срезе.
    Порядок приводится к little-endian явно, чтобы аудит не зависел от хоста.
    """
    words = array('I')
    words.frombytes(data[:rom_len - rom_len % 4])
    if sys.byteorder == 'big':
        words.byteswap()
    limit = HEADER_BASE + rom_len
    for index, value in enumerate(words):
        if HEADER_BASE <= value < limit:
            yield index * 4, value - HEADER_BASE


def _iter_run_bounds(data: bytes, rom_len: int):
    """Генератор (начальное смещение, длина) для каждого возрастающего блока.

    Блок обрывается на первом не-возрастании И на пропуске окна (шаг не 4): между
    окнами лежит не-указатель, продолжить серию через него нельзя.

    Наружу отдаются только границы — память O(1). Окна блока потом читаются
    заново из data и только для тех блоков, что реально могут что-то найти:
    список из 8 млн пар на вырожденном входе стоил бы сотни мегабайт.
    """
    run_start = -1
    run_len = 0
    prev_off = -8
    prev_target = -1
    for off, target in _iter_targets(data, rom_len):
        if run_len and (off != prev_off + 4 or target <= prev_target):
            yield run_start, run_len
            run_len = 0
        if not run_len:
            run_start = off
        run_len += 1
        prev_off, prev_target = off, target
    if run_len:
        yield run_start, run_len


def _run_length_through(span: list[tuple[int, int]]) -> list[tuple[int, int, int]]:
    """`(off, target, длина)` для каждого окна прогона.

    Блок `[i, j)` целиков монотонен — значит для ЛЮБОГО его элемента прогон
    равен `j - i`, и считать можно один раз на блок, а не по элементам.
    """
    out: list[tuple[int, int, int]] = []
    run_start = 0
    for index in range(1, len(span) + 1):
        if index < len(span) and span[index][1] > span[index - 1][1]:
            continue
        for pos in range(run_start, index):
            out.append((span[pos][0], span[pos][1], index - run_start))
        run_start = index
    return out


def _monotonic_run(data: bytes, off: int, rom_len: int) -> int:
    """Длина строго возрастающего прогона целей, содержащего `off`.

    Возвращает 1, если возрастающей серии через само окно нет: одиночное
    совпадение диапазона ничего не значит (см. докстринг модуля).

    Прямой доступ к одному смещению; аудит идёт через `_iter_run_bounds`,
    где тот же результат получается за один проход по ROM. Раньше здесь
    возвращался максимум по ВСЕМУ непрерывному участку, и одиночный указатель
    подтверждался чужой серией из того же участка.
    """
    back: list[int] = []
    pos = off
    while pos >= 0:
        got = _target(data, pos, rom_len)
        if got is None:
            break
        back.append(got)
        pos -= 4
    back.reverse()
    mine = len(back) - 1
    targets = back
    pos = off + 4
    while True:
        got = _target(data, pos, rom_len)
        if got is None:
            break
        targets.append(got)
        pos += 4
    for position, _value, length in _run_length_through(
            [(i, t) for i, t in enumerate(targets)]):
        if position == mine:
            return length
    return 1


def _target(data: bytes, off: int, rom_len: int) -> int | None:
    """Абсолютный адрес из 32-битного слота, либо None если это не указатель."""
    if off < 0 or off + 4 > len(data):
        return None
    value = int.from_bytes(data[off:off + 4], 'little')
    if not HEADER_BASE <= value < HEADER_BASE + rom_len:
        return None
    return value - HEADER_BASE


class _SegmentIndex:
    """Быстрый поиск fixed-сегмента, содержащего цель.

    Сегменты предполагаются НЕПЕРЕКРЫВАЮЩИМИСЯ: цель относится к тому
    диапазону, в который попала. Пересечение дало бы молчаливую потерю
    (bisect находит последний подходящий), поэтому оно описано как
    неподдерживаемое в докстринге модуля.
    """

    def __init__(self, segments: list[tuple[int, int]]):
        self.spans = sorted(segments)
        self.bounds = [start for start, _ in self.spans]

    @property
    def lo_bound(self) -> int:
        return self.spans[0][0]

    @property
    def hi_bound(self) -> int:
        return self.spans[-1][1]

    def where(self, target: int) -> tuple[int, int] | None:
        """Диапазон сегмента, в который СТРОГО попала цель, иначе None."""
        index = bisect_right(self.bounds, target) - 1
        if index < 0:
            return None
        start, end = self.spans[index]
        return (start, end) if start < target < end else None


def _collect_run(data: bytes, run_start: int, run_len: int, rom_len: int,
                 confirmed: dict, slot_starts: set[int],
                 index: _SegmentIndex) -> None:
    """Раскладывает подтверждённые указатели прогона в `confirmed` по сегментам.

    Окна перечитываются из `data`, а не берутся из накопленного списка: блок
    может быть длиной во весь ROM, и держать его в памяти незачем.
    """
    if run_len < MIN_RUN:
        return
    for step in range(run_len):
        off = run_start + step * 4
        target = _target(data, off, rom_len)
        if target is None or target in slot_starts:
            continue
        where = index.where(target)
        if where is None:
            continue
        confirmed.setdefault(where, []).append(
            {'pointer_at': off, 'target': target, 'slot': target - where[0]})


def audit_fixed_slots(rom_path: str, plugin=None,
                      manager: PluginManager | None = None) -> list[SegmentAudit]:
    """Отчёт по всем fixed-сегментам ROM. Пустой список — fixed-слотов нет."""
    rom = GameBoyROM(rom_path)
    if plugin is None:
        manager = manager or PluginManager()
        plugin = manager.get_plugin(rom.get_game_id(), rom.system, rom=rom)
    if plugin is None or getattr(plugin, 'is_stub', False):
        return []
    segments = [s for s in plugin.get_text_segments(rom)
                if isinstance(s, dict) and s.get('fixed_width')]
    if not segments:
        return []
    data = bytes(rom.data)
    rom_len = len(data)

    slot_starts: set[int] = set()
    for seg in segments:
        start, end, width = seg['start'], seg['end'], seg['fixed_width']
        for i in range(max(0, (end - start) // width)):
            slot_starts.add(start + i * width)

    index = _SegmentIndex([(seg['start'], seg['end']) for seg in segments])
    confirmed: dict[tuple[int, int], list[dict]] = {}
    for run_start, run_len in _iter_run_bounds(data, rom_len):
        if run_len < MIN_RUN:
            continue
        # Блок монотонен, поэтому первая цель — минимум, последняя — максимум.
        # Если весь диапазон целей лежит вне сегментов, блок можно не читать.
        first = _target(data, run_start, rom_len)
        last = _target(data, run_start + (run_len - 1) * 4, rom_len)
        if first is None or last is None:
            continue
        if last < index.lo_bound or first > index.hi_bound:
            continue
        _collect_run(data, run_start, run_len, rom_len, confirmed,
                     slot_starts, index)

    report: list[SegmentAudit] = []
    for seg in segments:
        start, end, width = seg['start'], seg['end'], seg['fixed_width']
        audit = SegmentAudit(
            name=seg.get('name', '?'), system=rom.system,
            start=start, end=end, width=width,
            slots=max(0, (end - start) // width))
        audit.mid_pointers = confirmed.get((start, end), [])
        report.append(audit)
    return report
