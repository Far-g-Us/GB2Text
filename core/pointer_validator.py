"""
GB Text Extraction Framework

ПРЕДУПРЕЖДЕНИЕ ОБ АВТОРСКИХ ПРАВАХ:
Этот программный инструмент предназначен ТОЛЬКО для анализа ROM-файлов,
законно принадлежащих пользователю. Использование этого инструмента для
нелегального копирования, распространения или модификации защищенных
авторским правом материалов строго запрещено.

Этот проект НЕ содержит и НЕ распространяет никакие ROM-файлы или
защищенные авторским правом материалы. Все ROM-файлы должны быть
законно приобретены пользователем самостоятельно.

Этот инструмент разработан исключительно для исследовательских целей,
обучения и реверс-инжиниринга в рамках, разрешенных законодательством.
"""

"""
Валидация и починка таблиц указателей после ручного патчинга ROM.

Проверяет каждую запись таблицы указателей (адрес, количество, шаг,
размер элемента, база адресации) на согласованность: цель в пределах
ROM, ненулевое значение, не повторяет цели других записей и не ломает
монотонный порядок адресации. Возвращает отчёт по каждой записи;
repair_pointer_table перезаписывает указатели на новые смещения
(например, после релокации текста).

Приоритет статусов записи (одна запись — один статус):
    zero → out_of_bounds → ok → duplicate (поверх ok)
    → non_monotonic (поверх ok, после duplicate-прохода).
"""

from core.pointer_table import HEADER_BASE


class PointerValidationError(ValueError):
    """Некорректные параметры таблицы указателей при валидации."""

    pass


STATUS_OK = "ok"
STATUS_ZERO = "zero"
STATUS_OUT_OF_BOUNDS = "out_of_bounds"
STATUS_DUPLICATE = "duplicate"
STATUS_NON_MONOTONIC = "non_monotonic"


def _validate_common(
    entry_size: int,
    stride: int,
    count: int,
) -> None:
    if entry_size not in (2, 4):
        raise PointerValidationError(
            f"Неподдерживаемый размер указателя: {entry_size} (ожидается 2 или 4)"
        )
    if count < 0:
        raise PointerValidationError(
            f"Отрицательное число записей: {count}"
        )
    if stride < entry_size:
        raise PointerValidationError(
            f"Шаг таблицы ({stride}) меньше размера указателя ({entry_size})"
        )


def validate_pointer_table(
    rom: bytes | bytearray,
    table_offset: int,
    count: int,
    stride: int = 4,
    entry_size: int = 4,
    address_base: int = HEADER_BASE,
) -> list[dict]:
    """Валидирует каждую запись таблицы указателей и возвращает отчёт.

    Каждый элемент отчёта:
        index    — индекс записи (0-based)
        value    — сырое числовое значение записи
        target   — смещение в ROM = value - address_base
        status   — STATUS_OK | STATUS_ZERO | STATUS_OUT_OF_BOUNDS
                   | STATUS_DUPLICATE | STATUS_NON_MONOTONIC
        next     — target следующей записи (для анализа монотонности)

    Требования: таблица целиком помещается в ROM; entry_size ∈ {2, 4};
    stride >= entry_size; address_base вычитается из value для
    получения смещения.
    Не-монотонность фиксируется у записи, чья цель меньше последней
    корректной цели из ok-цепочек записей.
    """
    _validate_common(entry_size, stride, count)
    table_size = stride * (count - 1) + entry_size if count > 0 else 0
    if table_offset < 0 or table_offset + table_size > len(rom):
        raise PointerValidationError(
            f"Таблица указателей (0x{table_offset:X}, {count} записей) "
            f"не помещается в ROM размером {len(rom):#x}"
        )

    records: list[dict] = []
    targets: list[int] = []
    for i in range(count):
        p = table_offset + i * stride
        value = int.from_bytes(rom[p:p + entry_size], "little")
        target = value - address_base
        targets.append(target)
        if value == 0:
            status = STATUS_ZERO
        elif target < 0 or target >= len(rom):
            status = STATUS_OUT_OF_BOUNDS
        else:
            status = STATUS_OK
        records.append({
            "index": i,
            "value": value,
            "target": target,
            "status": status,
        })

    seen: dict[int, int] = {}
    for rec in records:
        status = rec["status"]
        if status != STATUS_OK:
            continue
        tgt = rec["target"]
        prev = seen.get(tgt)
        if prev is not None:
            rec["status"] = STATUS_DUPLICATE
            rec["duplicate_of"] = prev
        else:
            seen[tgt] = rec["index"]

    for i, rec in enumerate(records):
        rec["next"] = targets[i + 1] if i + 1 < count else None

    last_ok: int | None = None
    for rec in records:
        if rec["status"] != STATUS_OK:
            continue
        tgt = rec["target"]
        if last_ok is not None and tgt < last_ok:
            rec["status"] = STATUS_NON_MONOTONIC
        else:
            last_ok = tgt
    return records


def problem_summary(records: list[dict]) -> dict[str, int]:
    """Считает количество записей по каждому статусу."""
    summary = {STATUS_OK: 0, STATUS_ZERO: 0,
               STATUS_OUT_OF_BOUNDS: 0, STATUS_DUPLICATE: 0,
               STATUS_NON_MONOTONIC: 0}
    for rec in records:
        summary[rec["status"]] = summary.get(rec["status"], 0) + 1
    return summary


def repair_pointer_table(
    rom: bytearray,
    table_offset: int,
    new_targets: dict[int, int],
    stride: int = 4,
    entry_size: int = 4,
    address_base: int = HEADER_BASE,
) -> int:
    """Атомарно перезаписывает указатели на новые смещения.

    Сначала валидирует все записи в new_targets; только после полной
    проверки выполняет запись. Если хотя бы одна запись невалидна,
    ROM не модифицируется. Возвращает количество перезаписанных записей.
    """
    _validate_common(entry_size, stride, len(new_targets))

    validated: list[tuple[int, int, int]] = []
    for index, target in new_targets.items():
        p = table_offset + index * stride
        if p < 0 or p + entry_size > len(rom):
            raise PointerValidationError(
                f"Запись {index} таблицы указателей выходит за пределы ROM"
            )
        if target < 0 or target >= len(rom):
            raise PointerValidationError(
                f"Новая цель {index} (0x{target:X}) вне пределов ROM"
            )
        value = target + address_base
        if not (0 <= value < 1 << (8 * entry_size)):
            raise PointerValidationError(
                f"Цель {index} (0x{target:X}) не помещается в "
                f"{entry_size}-байтный указатель"
            )
        validated.append((p, value, entry_size))

    for p, value, es in validated:
        rom[p:p + es] = value.to_bytes(es, "little")
    return len(validated)
