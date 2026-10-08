"""Общие помощники плагинов: слияние алиасов записей в указательной таблице.

Многие игры ссылаются на ОДНУ физическую запись из нескольких слотов
указательной таблицы. Встречаются две формы:

  1. Точные дубли — слоты указывают на один и тот же адрес (FF5: 98 окон
     на 729 слотов, до 107 слотов на одно окно).
  2. Суффиксные ссылки — слот указывает в середину чужой записи, её конец
     совпадает (FF5: 68 групп / 147 слотов, FF4: 630 групп / 1621 слот).
     Это тот же текст, просто обрезанный с начала.

Если отдавать сегмент на каждый слот, редактор показывает одну строку
десятки раз, а инжектор пишет пересекающиеся окна многократно: при разных
переводах результат зависит от порядка обхода, а пересечение он вынужден
отклонять — текст молча остаётся на исходном языке.

Правило слияния: записи самозавершающиеся, поэтому у двух РЕАЛЬНЫХ разных
записей не может совпасть конец. Значит группируем по end и оставляем
канонический сегмент с наименьшим start, а ссылки на остальные слоты
складываем в 'pointer_offsets' канонического.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger('gb2text.plugins.aliased_records')


def _int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def merge_aliased_records(segments: list[dict],
                         name_key: str = 'pointer_offset') -> list[Any]:
    """Сливает сегменты с ОДИНАКОВЫМИ (start, end).

    Контракт безусловный: границы не важны, сливаются только точные дубли
    одного физического окна (FF5: 98 окон на 729 слотов, до 107 слотов на
    одно окно).

    Сегменты без числового 'pointer_offset' не сливаются: для них неизвестно,
    какие слоты ссылаются на окно.
    """
    return _merge(segments, name_key, by_end=False)


def merge_terminated_records(segments: list[dict],
                             name_key: str = 'pointer_offset') -> list[Any]:
    """Дополнительно сливает суффиксные ссылки (общий конец, больший start).

    ВАЖНО: вызывать только для плагинов, у которых 'end' — позиция реального
    терминатора записи (самотерминирующий формат). Тогда у двух РАЗНЫХ
    записей конец совпасть не может, и одинаковый конец означает общий
    текст. Для плагинов, где 'end' — искусственная граница (следующий
    указатель или конец блока, как в FF4), слитие неверно и ломает записи.
    """
    return _merge(segments, name_key, by_end=True)


def _merge(segments: list[dict], name_key: str, *, by_end: bool) -> list[Any]:
    members: dict[tuple[int, ...], list[tuple[int, dict]]] = {}
    loose: dict[int, list[Any]] = {}
    for pos, segment in enumerate(segments):
        if not isinstance(segment, dict):
            loose.setdefault(pos, []).append(segment)
            continue
        start, end = _int(segment.get('start')), _int(segment.get('end'))
        cell = _int(segment.get(name_key))
        if start is None or end is None or start > end or cell is None:
            loose.setdefault(pos, []).append(segment)
            continue
        key = (end,) if by_end else (start, end)
        members.setdefault(key, []).append((pos, segment))

    drop: set[int] = set()
    merged_at: dict[int, dict] = {}
    had_suffixes = False
    for group in members.values():
        best = min(group, key=lambda item: (item[1]['start'], item[0]))
        canonical_start = best[1]['start']
        exact = [item for item in group if item[1]['start'] == canonical_start]
        suffixes = [item for item in group if item[1]['start'] != canonical_start]
        if len(exact) == 1 and not suffixes:
            merged_at[best[0]] = best[1]
            continue
        canonical = dict(best[1])
        cells = [_int(seg.get(name_key)) for _, seg in exact]
        canonical['pointer_offsets'] = [c for c in cells if c is not None]
        canonical['aliased_slots'] = len(canonical['pointer_offsets'])
        canonical['aliased_suffixes'] = len(suffixes)
        merged_at[best[0]] = canonical
        drop.update(pos for pos, _ in exact if pos != best[0])
        # Суффиксные записи НЕ удаляются: их окно лежит внутри канонической
        # записи, и после её перезаписи extent сдвигается — удалённый
        # сегмент просто исчезает из манифеста при повторном скане. Вместо
        # этого они остаются отдельными read-only сегментами ('injectable':
        # False, 'alias_of'): их читать можно, писать нельзя, иначе запись
        # портит каноническую.
        for pos, seg in suffixes:
            had_suffixes = True
            alias = dict(seg)
            alias['injectable'] = False
            alias['alias_of'] = canonical.get('name')
            alias['alias_start'] = canonical_start
            merged_at[pos] = alias

    out: list[dict] = []
    merged_windows = 0
    for pos, segment in enumerate(segments):
        if pos in merged_at:
            out.append(merged_at[pos])
            if merged_at[pos].get('aliased_slots', 1) > 1:
                merged_windows += 1
        elif pos in drop:
            continue
        elif pos in loose:
            out.extend(loose[pos])
        else:  # pragma: no cover - defensive: позиция без представления
            out.append(segment)
    if merged_windows or had_suffixes:
        logger.info(
            'Слито алиасов: %d окон, сегментов %d -> %d (ссылок на записи: %d)',
            merged_windows, len(segments), len(out),
            sum(len(s.get('pointer_offsets', ())) for s in out))
    return out
