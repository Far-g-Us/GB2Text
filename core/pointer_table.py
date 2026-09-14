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
Релокация блоков текста, адресуемых таблицей указателей (LE + 0x08000000).

Применяется для игр, где записи текста располагаются непрерывно и
индексируются абсолютными целями: пересборка записей меняет их длины,
поэтому каждый путь вставки (in-place и reloсation) переписывает цели
поддиапазона таблицы.
"""

HEADER_BASE = 0x08000000


def _intersects(run: tuple[int, int], excluded: list[tuple[int, int]]) -> bool:
    start, end = run
    for e_start, e_end in excluded:
        if start < e_end and e_start < end:
            return True
    return False


def assemble_block(records: list[bytes], padding: bytes = b'\x00\x00') -> bytes:
    """Записи подряд с паддингом после каждой (по умолчанию 2x0x00)."""
    return b''.join(record + padding for record in records)


def find_free_space(data: bytes | bytearray, size: int,
                    excluded: list[tuple[int, int]] | None = None) -> int | None:
    """Смещение run'а 0x00 длиной >= size вне excluded-диапазонов (или None)."""
    excluded = excluded or []
    n = len(data)
    i = 0
    while i < n:
        if data[i] != 0x00:
            i += 1
            continue
        j = i
        while j < n and data[j] == 0x00:
            j += 1
        if j - i >= size and not _intersects((i, j), excluded):
            return i
        i = j
    return None


def patch_pointer_range(data: bytearray, table_offset: int,
                        idx_start: int, idx_end: int,
                        record_offsets: list[int],
                        index_of=None) -> None:
    """Прописывает цели записей в поддиапазон таблицы (idx_start..idx_end).

    index_of: необязательный callable idx->table_idx. Для таблиц, где записи
    индексируются не подряд (например, interleaved-мультиязычные: один логический
    индекс использует несколько слотов таблицы), плагин передаёт функцию маппинга
    логического индекса в индекс элемента таблицы. По умолчанию — identity.
    """
    index_of = index_of or (lambda i: i)
    for k, offset in enumerate(record_offsets):
        idx = idx_start + k
        if idx >= idx_end:
            break
        value = offset + HEADER_BASE
        p = table_offset + 4 * index_of(idx)
        if p + 4 > len(data):
            break
        data[p:p + 4] = value.to_bytes(4, 'little')
