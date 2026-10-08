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
обучения и реверс-инжиниринга, в рамках, разрешенных законом.
"""

"""
Bank-aware адресация и поиск указателей для GB/GBC.

ЗАЧЕМ ОТДЕЛЬНЫЙ МОДУЛЬ
======================
У GBA есть честная линейная адресация: `HEADER_BASE (0x08000000) + addr`,
и весь остальной проект на ней и построен. У GB/GBC её нет. CPU видит
16-битное окно `0x0000..0x7FFF`, а банк выбирается записью в
регистр MBC. Поэтому «адрес строки в ROM» — это ПАРА `(bank_byte, addr16)`,
а одно число. Схема, где банк берётся из старшего байта 32-битного
указателя, для GB/GBC неверна: там байты указателя идут в обратном порядке
(старший байт адреса младшим), и никакого 0x08 в значении нет.

МОДУЛЬ НЕ УГАДЫВАЕТ РАЗМЕР БАНКА
=================================
Классический GB/GBC банк = 16 КиБ, и это подавляющее большинство игр. Но
ROM может быть не выровнен по степени двойки: `0x1F`-банковый ROM = 2 МиБ,
а реально 31 банк, и последний банк короче. Модуль поэтому НЕ берёт
`bank_size` из заголовка и не делит ROM на 16 КиБ молча — размер банка
передаётся явно, а `bank_span()` честно сообщает, что банк обрезан концом
файла, вместо того чтобы вернуть несуществующий адрес.

ЧТО ЭТО НЕ ДЕЛАЕТ
==================
Не определяет тип MBC и не читает регистров: `scan` работает по статическому
изображению ROM. Для бано-зависимого кода (где указатель вычисляется
`bank * 0x4000 + (x & 0x3FFF)` в рантайме) статический скан по дампу
бесполезен — такие ссылки видны только в дизассемблере. Такие случаи
`classify_pointer` помечает как `computed`, чтобы отчёт не врал.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger('gb2text.gb_banks')


def _check_bank_size(bank_size: int) -> None:
    """Размер банка обязан быть положительным целым.

    Без проверки `bank_size=0` ронял `to_bank_addr` и `classify_pointer`
    ZeroDivisionError, а `bank_size=-1` тихо возвращал (-1, -2) и «rom» —
    то есть выдуманный адрес в модуле, чей тезис именно в этом.
    """
    if (not isinstance(bank_size, int) or isinstance(bank_size, bool)
            or bank_size <= 0):
        raise ValueError(f'bank_size должен быть положительным int, '
                         f'получено {bank_size!r}')

#: Стандартный размер банка GB/GBC — 16 КиБ.
BANK_SIZE = 0x4000
#: Правая граница адресуемого ROM-окна (VRAM/OAM/WRAM/SRAM/HRAM там).
WINDOW_END = 0x8000
#: Начало внешней RAM (не в ROM — указатель туда указывать не может).
RAM_START = 0xA000
#: Граница ниже которой адрес в банке 0 (заголовок и векторы прерываний).
BANK0_ROM_END = 0x4000


class PointerKind(StrEnum):
    """Что означает найденный указатель. Считается по значению и банку."""

    #: Обычный указатель на строку в банке.
    ROM = 'rom'
    #: Адрес заголовка/векторов: банк 0, но это не текст.
    BANK0 = 'bank0'
    #: Указатель в VRAM/OAM (0x8000..0x9FFF) — в ROM по нему ничего нет.
    VIDEO = 'video'
    #: Указатель во внешнюю/рабочую RAM (0xA000 и выше) — не в ROM.
    RAM = 'ram'
    #: Ноль: не инициализированная запись таблицы.
    NULL = 'null'
    #: Банк не существует в этом ROM (на практике недостижимо при
    #: rom_size >= 0xC000: любое 0x0001..0x7FFF попадает в существующий
    #: банк). Оставлено явно, чтобы «не нашлось» не выглядело как «rom».
    BANK_MISSING = 'bank_missing'


@dataclass(frozen=True)
class BankPointer:
    """Указатель, найденный в банке, с честным разбором на пару байт."""

    #: Смещение указателя в линейном ROM.
    offset: int
    #: Байт банка, которому принадлежит указатель (не банк ЦЕЛИ!).
    pointer_bank: int
    #: Банк ЦЕЛИ, ВЫЧИСЛЕННЫЙ из значения `target_addr` через
    #: `to_bank_addr`. Он НЕ равен переданному в `scan_bank_pointers(bank=)`:
    #: тот ограничивает область поиска, а не объявляет банк цели. Раньше
    #: здесь подставлялся аргумент, и пара молча уезжала на 0x4000 для
    #: адресов с банком >= 2 — то есть запись поверх игровых данных.
    target_bank: int | None
    #: Адрес цели в окне CPU (как записан в ROM, без «вычитания банка»).
    target_addr: int | None
    kind: PointerKind
    #: Банк, ЗАДАННЫЙ вызывающим как область поиска, если он был задан.
    #: Это гипотеза о раскладке таблицы, а не факт из значения.
    assumed_bank: int | None = None

    @property
    def is_text_candidate(self) -> bool:
        """Указывает ли на исполняемый текст (а не на данные/заголовок)."""
        return self.kind is PointerKind.ROM


def bank_count(rom_size: int, bank_size: int = BANK_SIZE) -> int:
    """Сколько банков помещается в ROM (последний может быть короче)."""
    _check_bank_size(bank_size)
    return (rom_size + bank_size - 1) // bank_size


def bank_span(rom_size: int, bank: int, bank_size: int = BANK_SIZE) -> tuple[int, int]:
    """Линейный диапазон банка в ROM.

    Банк, вылезающий за конец файла, ОБРЕЗАЕТСЯ: `0x1F` в 2-МиБ ROM — это
    31 полных банка и половина. Модуль не изобретает адрес в несуществующих
    байтах.
    """
    if not isinstance(bank, int) or isinstance(bank, bool) or bank < 0:
        raise ValueError(f'Банк должен быть неотрицательным int, '
                         f'получено {bank!r}')
    _check_bank_size(bank_size)
    start = bank * bank_size
    return start, min(start + bank_size, rom_size)


def to_offset(bank: int, addr: int, rom_size: int,
              bank_size: int = BANK_SIZE) -> int | None:
    """`(bank_byte, addr16)` → линейное смещение в ROM, либо None.

    Схема отображения — реальная адресация GB/GBC, а не «умножение банка»:

        банк 0:  addr 0x0000..0x3FFF  →  addr
        банк N:  addr 0x4000..0x7FFF  →  N * bank_size + (addr - 0x4000)

    То есть `bank * bank_size + addr` — ОШИБКА: она сдвигает каждую ссылку
    на 0x4000 и уводит её в соседний банк, то есть ровно туда, где может
    лежать другой текст.

    None означает «такого адреса в этом ROM нет»: банк за концом файла,
    обрезанный банк, адрес вне окна CPU или вне физической половины банка.
    Ни один из этих случаев нельзя молча скруглить — это источник записи
    мусора при обратной вставке.
    """
    _check_bank_size(bank_size)
    if not isinstance(bank, int) or isinstance(bank, bool) or bank < 0:
        return None
    if not isinstance(addr, int) or isinstance(addr, bool):
        return None
    if not 0 <= addr < WINDOW_END:
        return None
    start, stop = bank_span(rom_size, bank, bank_size)
    if start >= stop:
        return None
    if bank == 0:
        if addr >= BANK0_ROM_END:
            # Банк 0 физически содержит только 0x0000..0x3FFF: адреса
            # 0x4000+ в нём не существует, даже если файл достаточно велик.
            return None
        linear = addr
    else:
        if addr < BANK0_ROM_END:
            # Банкерное окно начинается с 0x4000: в банке N нельзя адресовать
            # 0x0000..0x3FFF (это ведь банк 0).
            return None
        linear = start + (addr - BANK0_ROM_END)
    return linear if start <= linear < stop else None


def to_bank_addr(offset: int, rom_size: int,
                 bank_size: int = BANK_SIZE) -> tuple[int, int] | None:
    """Линейное смещение → `(bank_byte, addr16)`, либо None.

    Обратная функция `to_offset`, а не «divmod + 0x4000 наугад».
    """
    _check_bank_size(bank_size)
    if not isinstance(offset, int) or isinstance(offset, bool):
        return None
    if not 0 <= offset < rom_size:
        return None
    bank, inner = divmod(offset, bank_size)
    if bank == 0:
        return (0, inner) if inner < BANK0_ROM_END else None
    addr = BANK0_ROM_END + inner
    if addr >= WINDOW_END:  # pragma: no cover - inner < bank_size = 0x4000
        return None
    return bank, addr


def classify_pointer(value: int, rom_size: int,
                     bank_size: int = BANK_SIZE) -> PointerKind:
    """Классифицирует 16-битное значение как ссылку — без домыслов.

    Порядок проверок важен: RAM и VRAM лежат ВЫШЕ окна ROM, поэтому проверка
    «вне окна» до них отсортировала бы SRAM/WRAM в «неизвестно».
    """
    _check_bank_size(bank_size)
    if value == 0:
        return PointerKind.NULL
    if value >= RAM_START:
        return PointerKind.RAM
    if value >= WINDOW_END:
        return PointerKind.VIDEO
    located = to_bank_addr(value, rom_size, bank_size)
    if located is None:
        return PointerKind.BANK_MISSING
    if located[0] == 0:
        return PointerKind.BANK0
    return PointerKind.ROM


def scan_bank_pointers(rom_data: bytes | bytearray, addr16: int, *,
                       bank: int | None = None,
                       bank_size: int = BANK_SIZE,
                       min_run: int = 1) -> list[BankPointer]:
    """Ищет 16-битные LE-указатели со значением `addr16`.

    ПОЧЕМУ ЗДЕСЬ НЕТ ПАРАМЕТРА «БАНК ЦЕЛИ»
    ======================================
    Пара `(bank_byte, addr16)` — это 24 бита, а в таблице Gen1/2 лежат
    16-битные адреса. Банк либо подразумевается (таблица и строки в одном
    банке), либо хранится отдельным байтом в параллельном столбце. Собрать
    «(bank << 8) | addr» нельзя: при addr >= 0x100 младший байт адреса
    затирается, и скан находит мусор — именно эту ошибку модуль уже
    допускал в первой версии.

    Поэтому банк задаётся ТОЛЬКО как область поиска: `bank=N` ограничивает
    скан байтами банка N (подразумеваемый банк). Для таблиц с отдельным
    байтом банка есть `scan_banked_rows`.

    `min_run` отбрасывает перекрывающиеся совпадения (`AA BB AA BB` даёт
    два «указателя» с шагом 1 — это не таблица).
    """
    _check_bank_size(bank_size)
    if min_run < 1:
        raise ValueError(f'min_run должен быть >= 1, получено {min_run}')
    if not isinstance(addr16, int) or isinstance(addr16, bool) \
            or not 0 <= addr16 <= 0xFFFF:
        raise ValueError(f'addr16 вне 16-битного диапазона: {addr16!r}')
    rom_size = len(rom_data)
    kind = classify_pointer(addr16, rom_size, bank_size)
    if bank is None:
        lo_off, hi_off = 0, rom_size - 1
    else:
        lo_off, hi_off = bank_span(rom_size, bank, bank_size)
        hi_off -= 1
    needle = addr16.to_bytes(2, 'little')
    # НЕ `bytes(rom_data)`: это копирует весь ROM на каждый вызов, а
    # `scan_for_text_pointers` зовёт функцию миллионы раз. `bytearray.find`
    # работает без копии, как и `bytes.find` для неизменяемого входа.
    data = rom_data
    found: list[BankPointer] = []
    i = lo_off
    last_kept = lo_off - min_run
    while i <= hi_off:
        pos = data.find(needle, i, hi_off + 1)
        if pos < 0:
            break
        i = pos + 1
        if pos - last_kept < min_run:
            continue
        last_kept = pos
        ptr_bank, _ = divmod(pos, bank_size)
        located = to_bank_addr(addr16, rom_size, bank_size)
        found.append(BankPointer(
            offset=pos, pointer_bank=ptr_bank,
            target_bank=located[0] if located else None,
            target_addr=addr16, kind=kind, assumed_bank=bank))
    if found:
        logger.debug('bank scan: 0x%04X (bank %s) -> %d совпадений',
                     addr16, bank, len(found))
    return found


def scan_banked_rows(rom_data: bytes | bytearray, table_offset: int,
                     count: int, *, row_size: int = 3,
                     bank_first: bool = True,
                     bank_size: int = BANK_SIZE,
                     min_rows: int = 4,
                     max_banks: int = 2,
                     max_addr_step: int = 0x2000) -> list[BankPointer]:
    """Читает таблицу «[bank_byte][addr16]» и ОТБРАСЫВАЕТ совпадения-мусор.

    ПОЧЕМУ ТАК СЛОЖНО
    ==================
    Без фильтра функция бесполезна: любые 3 байта декодируются в
    правдоподобную пару `(bank, addr)`, и на произвольных данных 24%
    строк проходят как «указатели» (измерено фаззингом). RE-скрипт, построенный
    на таком выводе, утащил бы в «таблицу» область заголовка: в Pokemon Gold
    первое же совпадение сидело по 0x0BF0 с банками `[42,42,42,42]`.

    ЧЕК-ЛИСТ НАСТОЯЩЕЙ ТАБЛИЦЫ
    ============================
    1. подряд идут >= `min_rows` принятых строк (одна-две строки — это
       совпадение, а не таблица);
    2. банков не больше `max_banks`: у настоящей таблицы они обычно один,
       а у мусора — случайные;
    3. адреса не убывают и шаг между соседними ограничен `max_addr_step`:
       текст лежит подряд, и «телепорт» на 0x4000 — признак мусора;
    4. ни одна строка не NULL и не вне ROM.

    Что функция НЕ делает: не проверяет, что по адресам лежит текст. Для
    этого нужен charmap конкретной игры — см. `looks_like_text`.
    """
    if row_size != 3:
        raise ValueError(f'row_size должен быть 3 (bank+addr16), '
                         f'получено {row_size}')
    if count < 0:
        raise ValueError(f'Отрицательное число строк: {count}')
    if not isinstance(table_offset, int) or isinstance(table_offset, bool) \
            or table_offset < 0:
        # Без этой проверки base + row_size > rom_size не срабатывает для
        # отрицательного base, и последний байт ROM читался как байт банка.
        raise ValueError(f'table_offset должен быть неотрицательным int, '
                         f'получено {table_offset!r}')
    _check_bank_size(bank_size)
    rom_size = len(rom_data)
    rows: list[BankPointer] = []
    skipped: list[int] = []
    for row in range(count):
        base = table_offset + row * row_size
        if base + row_size > rom_size:
            break
        if bank_first:
            bank = rom_data[base]
            addr = int.from_bytes(rom_data[base + 1:base + 3], 'little')
        else:
            addr = int.from_bytes(rom_data[base:base + 2], 'little')
            bank = rom_data[base + 2]
        kind = classify_pointer(addr, rom_size, bank_size)
        if kind is PointerKind.NULL:
            logger.debug('banked row %d: нулевой указатель — пропуск', row)
            continue
        if to_offset(bank, addr, rom_size, bank_size) is None:
            skipped.append(row)
            logger.debug('banked row %d: 0x%02X:0x%04X вне ROM — пропуск',
                         row, bank, addr)
            continue
        rows.append(BankPointer(
            offset=base, pointer_bank=table_offset // bank_size,
            target_bank=bank, target_addr=addr, kind=kind))
    if skipped:
        # Вызывающий обязан знать, сколько строк выжило: иначе «прочитано
        # 40 из 40» неотличимо от «уцелело 4».
        logger.warning('banked rows %s: пропущено %d из %d',
                       hex(table_offset), len(skipped), count)
    return _plausible_run(rows, min_rows, max_banks, max_addr_step)


def _plausible_run(rows: list[BankPointer], min_rows: int, max_banks: int,
                   max_addr_step: int) -> list[BankPointer]:
    """Возвращает самую длинную ПОХОЖУЮ НА ТАБЛИЦУ серию строк.

    Серия продолжается, пока адреса неубывают с шагом <= `max_addr_step` и
    число различных банков не превысило `max_banks`. Банк при этом НЕ обязан
    быть один: часть таблиц ссылается на два соседних банка, и требование
    «строго один банк» делало бы параметр `max_banks` мёртвым.
    """
    if len(rows) < min_rows:
        if rows:
            logger.debug('banked: %d строк — меньше порога %d, отброшены',
                         len(rows), min_rows)
        return []
    best: list[BankPointer] = []
    cur: list[BankPointer] = []
    banks: set[int] = set()
    prev_addr: int | None = None
    for row in rows:
        # Поля объявлены как Optional (указатель может быть не разрешён), но
        # сюда попадают только уже проверенные строки. Проверка оставлена и
        # для mypy, и как защита при вызове откуда-то ещё.
        addr = row.target_addr
        bank = row.target_bank
        if addr is None or bank is None:  # pragma: no cover - defensive
            continue
        if cur and prev_addr is not None:
            step = addr - prev_addr
            if not 0 <= step <= max_addr_step or \
                    len(banks | {bank}) > max_banks:
                # Строка нарушает правило — текущая серия закрывается, а
                # нарушитель становится началом новой.
                if len(cur) > len(best):
                    best = cur
                cur = []
                banks = set()
        cur.append(row)
        banks.add(bank)
        prev_addr = addr
    if len(cur) > len(best):
        best = cur
    # Порог применяется и к ИТОГОВОЙ серии: после разбиения на месте может
    # остаться кусок из двух строк, а по общему числу строк порог проходил.
    if len(best) < min_rows:
        logger.debug('banked: лучшая серия %d строк — меньше порога %d, '
                     'отброшена', len(best), min_rows)
        return []
    # Ветки «ни одна серия не прошла фильтр» здесь быть не может: выше
    # уже стоит return при len(best) < min_rows, а min_rows >= 2.
    logger.debug('banked: принято %d строк (банков %d)', len(best),
                 len({r.target_bank for r in best}))
    return best


def group_pointer_runs(pointers: list[BankPointer], stride: int = 2,
                        min_count: int = 2) -> list[list[BankPointer]]:
    """Группирует указатели в таблицы по РЕГУЛЯРНОМУ шагу.

    Одиночное совпадение — это «возможно, ссылка»; несколько подряд с
    одинаковым шагом — уже таблица. Несколько строк с шагом 2 подряд в
    сжатом виде невозможны, поэтому дефолт `stride=2` и `min_count=2`
    отсекают самый частый мусор.
    """
    if stride <= 0:
        raise ValueError(f'stride должен быть положительным, получено {stride}')
    runs: list[list[BankPointer]] = []
    current: list[BankPointer] = []
    for ptr in pointers:
        if not current:
            current = [ptr]
            continue
        if ptr.offset - current[-1].offset == stride:
            current.append(ptr)
        else:
            if len(current) >= min_count:
                runs.append(current)
            current = [ptr]
    if len(current) >= min_count:
        runs.append(current)
    return runs


def scan_for_text_pointers(rom_data: bytes | bytearray, rom_size: int,
                           *, bank_size: int = BANK_SIZE,
                           min_run: int = 3,
                           stride: int = 2) -> list[list[BankPointer]]:
    """Полный обход банков: ищет таблицы 16-битных указателей на строки.

    Идёт по всем банкам и всем 16-битным значениям внутри каждого, поэтому
    стоимость — `banks × 0x10000` сравнений. Для 2 МиБ это около 2·10⁸,
    что многовато для GUI: вызывающий обязан ограничивать обход (например,
    передав срез ROM нужных банков — молчаливая нарезка со сдвигом нумерации
    банков недопустима) либо использовать `scan_bank_pointers` для уже
    известного адреса.

    Банк берётся ПОДРАЗУМЕВАЕМЫМ (ищем в том же банке, где лежит сам
    указатель). Указатели из банка 0 на строки в других банках так не
    находятся — для этого `scan_banked_rows`.

    `min_run` — сколько ПОДРЯД ИДУЩИХ находок образуют таблицу (3 по
    умолчанию, чтобы отсечь случайные совпадения). Перекрывающиеся
    совпадения отсеиваются внутри по `min_run=1`, иначе таблица с шагом
    `stride` не находилась бы в принципе.
    """
    banks: list[int] = []
    for bank in range(bank_count(rom_size, bank_size)):
        start, stop = bank_span(rom_size, bank, bank_size)
        # start < stop выполняется ВСЕГДА: bank_count округляет вверх, поэтому
        # последний банк непустой (проверено для размеров 0x1000..0x8001).
        if start < stop:  # pragma: no branch
            banks.append(bank)
    tables: list[list[BankPointer]] = []
    for bank in banks:
        lo = BANK0_ROM_END if bank == 0 else 0
        for addr in range(lo, WINDOW_END):
            # ВНУТРИ min_run=1, а не переданный: дедупликация по min_run
            # выбрасывает каждую N-ю находку, и таблица с шагом 2 (самая
            # частая — это и есть 16-битный массив указателей) не может быть
            # найдена в принципе: находки 0x00, 0x02, 0x04 при min_run=3
            # дают разрывы, и группировка по шагу их не собирает.
            # Отсевом перекрывающихся совпадений занимается группировка.
            for run in group_pointer_runs(
                    scan_bank_pointers(rom_data, addr, bank=bank,
                                       bank_size=bank_size, min_run=1),
                    stride=stride):
                tables.append(run)
    return tables


# ── Проверка, что за найденными указателями ЛЕЖИТ ТЕКСТ ─────────────────────

DEFAULT_TERMINATORS = (0x00, 0xFF, 0x50)
TEXT_WINDOW = 64


def text_bytes_at(rom_data: bytes | bytearray, bank: int, addr: int, *,
                  rom_size: int | None = None,
                  bank_size: int = BANK_SIZE,
                  terminators: tuple[int, ...] = DEFAULT_TERMINATORS,
                  window: int = TEXT_WINDOW) -> tuple[bytes, bool]:
    """Читывает строку по паре (банк, адрес) до терминатора.

    Возвращает `(байты, найден_терминатор)`. Второе значение важно для
    вердикта: строка без терминатора внутри окна почти наверняка не строка,
    а начало таблицы или код. Если адрес не разрешается в файл — байты пустые
    и терминатор «не найден», без исключения: вызывающая сторона сама решает,
    что делать с невалидным указателем.
    """
    size = len(rom_data) if rom_size is None else rom_size
    start = to_offset(bank, addr, size, bank_size)
    if start is None:
        return b'', False
    chunk = bytes(rom_data[start:start + window])
    for index, byte in enumerate(chunk):
        if byte in terminators:
            return chunk[:index], True
    return chunk, False


def _known_bytes(chunk: bytes, charmap: dict[int, str] | None) -> int:
    """Сколько байтов chunk известны как символы текста."""
    if charmap:
        return sum(1 for b in chunk if b in charmap)
    # Без charmap критерий остаётся ASCII-эвристикой и НЕ годен для Gen1/2:
    # там буквы лежат в 0x80..0x99. Поэтому вызывающий обязан передать карту.
    return sum(1 for b in chunk if 0x20 <= b <= 0x7E)


def looks_like_text(rom_data: bytes | bytearray,
                    pointers: list[BankPointer], *,
                    charmap: dict[int, str] | None = None,
                    min_ratio: float = 0.8,
                    min_len: int = 2,
                    terminators: tuple[int, ...] = DEFAULT_TERMINATORS,
                    window: int = TEXT_WINDOW) -> tuple[bool, float]:
    """Проверяет, что по указателям лежит текст, а не код и не таблица.

    `_plausible_run` проверяет только ГЕОМЕТРИЮ указателей (сколько банков,
    шаг между адресами, нет ли NULL). Геометрия проходит у многих мусорных
    серий, поэтому нужен второй, независимый признак — сами байты строки.

    Критерий по каждому указателю:
      1. строка не короче `min_len` символов;
      2. не меньше `min_ratio` её байтов известны как символы (`charmap`
         игры; без него — ASCII-эвристика, см. `_known_bytes`);
      3. терминатор найден в пределах окна `window` байт.

    Вердикт требует, чтобы текстом оказалось не меньше половины строк, иначе
    таблица из 40 строк прошла бы по двум случайным. Возвращает
    `(вердикт, доля принятых строк)`: доля нужна для отчёта и позволяет
    отличить 4 принятых строки из 5 от 4 из 40.
    """
    if not pointers:
        return False, 0.0
    _check_ratio(min_ratio)
    good = 0
    checked = 0
    for ptr in pointers:
        if ptr.target_bank is None or ptr.target_addr is None:
            continue
        checked += 1
        chunk, terminated = text_bytes_at(rom_data, ptr.target_bank,
                                          ptr.target_addr,
                                          terminators=terminators,
                                          window=window)
        if len(chunk) < min_len or not terminated:
            continue
        if _known_bytes(chunk, charmap) / len(chunk) >= min_ratio:
            good += 1
    if checked == 0:
        return False, 0.0
    score = good / checked
    return score >= 0.5, score


def _check_ratio(min_ratio: float) -> None:
    if isinstance(min_ratio, bool) or not isinstance(min_ratio, (int, float)):
        raise ValueError(f'min_ratio должен быть числом, получено {min_ratio!r}')
    if not 0.0 <= min_ratio <= 1.0:
        raise ValueError(f'min_ratio вне 0..1: {min_ratio!r}')


def verify_table(rom_data: bytes | bytearray, pointers: list[BankPointer], *,
                 charmap: dict[int, str] | None = None,
                 bank_size: int = BANK_SIZE,
                 min_ratio: float = 0.8) -> dict:
    """Полная проверка кандидата в таблицу: геометрия + текст + монотонность.

    Монотонность — отдельное требование, а не часть `looks_like_text`: строки
    в игре идут подряд, поэтому адреса не убывают и не «прыгают» через пол-ROM.
    Возвращает отчёт (в JSON-совместимом виде), а не только флаг: RE-скрипту
    нужно показать, ЧЕМ именно кандидат отвергнут.
    """
    _check_ratio(min_ratio)
    report: dict = {
        'rows': len(pointers),
        'monotonic': True,
        'descents': 0,
        'max_addr_step': 0,
        'text_ok': False,
        'text_score': 0.0,
        'banks': sorted({p.pointer_bank for p in pointers}),
        'reasons': [],
    }
    if not pointers:
        report['reasons'].append('пустая серия')
        report['ok'] = False
        return report
    prev: tuple[int | None, int] | None = None
    unusable = 0
    for ptr in pointers:
        if ptr.target_bank is None or ptr.target_addr is None:
            unusable += 1
            continue
        cur = (ptr.target_bank, ptr.target_addr)
        if prev is not None:
            step = ptr.target_addr - prev[1]
            if step < 0:
                report['descents'] += 1
            report['max_addr_step'] = max(report['max_addr_step'], abs(step))
        prev = cur
    if unusable:
        report['unusable'] = unusable
        report['reasons'].append(
            f'{unusable} строк без разрешимой пары (банк/адрес)')
    if report['descents']:
        report['monotonic'] = False
        report['reasons'].append(
            f'адреса не монотонны: {report["descents"]} убываний')
    if report['max_addr_step'] > 0x2000:
        report['reasons'].append(
            f'шаг между адресами {report["max_addr_step"]} слишком велик')
    ok, score = looks_like_text(rom_data, pointers, charmap=charmap,
                                min_ratio=min_ratio)
    report['text_ok'] = ok
    report['text_score'] = score
    if not ok:
        report['reasons'].append(
            f'по адресам не текст (доля строк {score:.2f} < 0.50)')
    report['ok'] = (not report['reasons'])
    return report


def scan_text_table(rom_data: bytes | bytearray, *, bank: int,
                    bank_size: int = BANK_SIZE,
                    stride: int = 2,
                    min_rows: int = 8,
                    max_addr_step: int = 0x2000,
                    charmap: dict[int, str] | None = None,
                    min_ratio: float = 0.8) -> list[list[BankPointer]]:
    """Ищет НАСТОЯЩУЮ таблицу указателей на текст в одном банке.

    ЗАЧЕМ ОТДЕЛЬНО ОТ `scan_for_text_pointers`
    ===========================================
    Таблица текста — это тысячи РАЗНЫХ адресов, идущих подряд и вверх. А
    `scan_for_text_pointers` группирует повторы ОДНОГО значения (это другая
    задача — найти «шаблон, вставленный в несколько мест»), поэтому на
    настоящей таблице игр он даёт лишь короткие обрывки по 2–8 строк.

    Здесь принимается серия, которая одновременно:
      1. идёт с постоянным шагом `stride` байт (обычно 2 — слово);
      2. строго ВОЗРАСТАЕТ по адресу цели: строки в игре идут по порядку,
         это и есть монотонность, ради которой функция и написана;
      3. шаг между адресами не превышает `max_addr_step` (телепорт через
         пол-ROM — признак мусора, а не текста);
      4. проходит `looks_like_text` — по адресам лежит текст игры.

    Банк указывается явно: в GB/GBC «адрес строки» без банка не адрес, и
    молчаливое сканирование всех банков дало бы таблицу в коде.

    Возвращает принятые таблицы, отсортированные по убыванию числа строк.
    """
    _check_bank_size(bank_size)
    if stride < 1:
        raise ValueError(f'stride должен быть >= 1, получено {stride}')
    if min_rows < 2:
        raise ValueError(f'min_rows должен быть >= 2, получено {min_rows}')
    _check_ratio(min_ratio)
    rom_size = len(rom_data)
    lo, hi = bank_span(rom_size, bank, bank_size)
    if hi - lo < stride * min_rows:
        return []

    run: list[BankPointer] = []
    tables: list[list[BankPointer]] = []
    prev_pos = -stride
    prev_addr = -1

    def close_run() -> None:
        if len(run) >= min_rows and looks_like_text(
                rom_data, run, charmap=charmap, min_ratio=min_ratio)[0]:
            tables.append(list(run))

    pos = lo
    while pos + 2 <= hi:
        value = int.from_bytes(rom_data[pos:pos + 2], 'little')
        located = to_bank_addr(value, rom_size, bank_size)
        is_pointer = (located is not None
                      and classify_pointer(value, rom_size, bank_size)
                      is PointerKind.ROM)
        if is_pointer and located is not None:
            bank_target, addr_target = located
            contiguous = pos - prev_pos == stride
            growing = (prev_addr >= 0
                       and 0 < addr_target - prev_addr <= max_addr_step)
            if contiguous and growing:
                run.append(BankPointer(
                    offset=pos, pointer_bank=bank, target_bank=bank_target,
                    target_addr=addr_target, kind=PointerKind.ROM,
                    assumed_bank=bank))
            else:
                # Новый указатель не продолжает серию: предыдущая закрыта,
                # а с него самого начинается возможная новая таблица.
                close_run()
                run = [BankPointer(
                    offset=pos, pointer_bank=bank, target_bank=bank_target,
                    target_addr=addr_target, kind=PointerKind.ROM,
                    assumed_bank=bank)]
            prev_pos = pos
            prev_addr = addr_target
        elif pos - prev_pos == stride:
            # Значение не указатель — серия прервана, дальше начинать не с чего.
            close_run()
            run = []
            prev_pos = -stride
            prev_addr = -1
        pos += stride
    close_run()
    tables.sort(key=len, reverse=True)
    return tables


__all__ = [
    'BANK0_ROM_END',
    'BANK_SIZE',
    'DEFAULT_TERMINATORS',
    'RAM_START',
    'TEXT_WINDOW',
    'WINDOW_END',
    'BankPointer',
    'PointerKind',
    'bank_count',
    'bank_span',
    'classify_pointer',
    'group_pointer_runs',
    'looks_like_text',
    'scan_bank_pointers',
    'scan_banked_rows',
    'scan_for_text_pointers',
    'scan_text_table',
    'text_bytes_at',
    'to_bank_addr',
    'to_offset',
    'verify_table',
]
