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
Сжатие текста в играх GB/GBC (Gen1/2): RLE с управляющим байтом и LZ.

ЧЕСТНОСТЬ ФОРМАТОВ
==================
В проекте уже есть `core/compression.py` с обработчиками `LZSSHandler` и
`RLEHandler`, но это эвристики для «похожего на сжатие»: они угадывают
формат по первым байтам, ни один реальный формат не описывают и жёстко
обрезают вывод 64 КиБ. Им нельзя доверять при обратной вставке — сжатый
поток после декодирования не воспроизводится.

Здесь только два формата, описанные точно, и для каждого есть и чтение, и
ЗАПИСЬ (`compress`), чтобы round-trip был честным:

1) `ControlByteRLEHandler` — RLE с управляющим байтом:
       ctrl < 0x80  →  литеральная серия (ctrl + 1) байт
       ctrl >= 0x80 →  повтор следующего байта (ctrl & 0x7F) + 3 раза
   Применяется в Gen1/2 (например, RLE в Pokemon Gen1 для описаний
   предметов/ходов) и в ряде сторонних игр.

2) `NintendoLZHandler` — LZ «по-флаговому байту» со ссылкой из двух байт:
       флаг-байт, затем 8 элементов; старший бит = ссылка, иначе литерал;
       ссылка: два байта `hi, lo` → смещение = ((hi & 0x0F) << 8 | lo) + 1,
               длина = (hi >> 4) + 3.
   Это схема GBA-LZ77 без заголовка вида, применённая к GB/GBC-тексту.

ЧЕГО МОДУЛЬ НЕ ДЕЛАЕТ
=====================
Не выбирает формат за игру. `guess_format` — эвристика по КПД распаковки,
и её результат можно перепроверить: если после переупаковки поток не
воспроизводится, формат не тот, и подменять им ROM нельзя.
"""

import logging
from bisect import bisect_left
from typing import Protocol

from core.decoder import CompressionHandler

logger = logging.getLogger('gb2text.gb_compression')

#: Предохранитель против распаковки «болота» (испорченный или не тот формат).
DEFAULT_MAX_OUTPUT = 0x10000
#: Максимальная длина ЛИТЕРАЛЬНОЙ серии в RLE (7 бит + 1).
#: Ровно 128: ctrl обязан остаться < 0x80, иначе он будет прочитан как повтор.
RLE_MAX_LITERAL = 0x80
#: Максимальная длина серии в RLE (7 бит + 3).
RLE_MAX_RUN = 0x7F + 3
#: Максимальная длина ссылки в LZ (4 бит + 3).
LZ_MAX_LENGTH = 0x0F + 3
#: Максимальное смещение в LZ (12 бит + 1).
LZ_MAX_OFFSET = 0x0FFF + 1


class CompressibleHandler(Protocol):
    """Обработчик, умеющий и читать, и писать поток.

    Чисто типовой Protocol: тел нет, код не исполняется, а сам класс
    нельзя инстанцировать, поэтому обе строки исключены из покрытия.
    """

    def decompress(  # pragma: no cover
        self, data: bytes, start: int) -> tuple[bytes, int]: ...

    def compress(self, raw: bytes) -> bytes: ...  # pragma: no cover


class ControlByteRLEHandler(CompressionHandler):
    """RLE с управляющим байтом (описан в докстринге модуля)."""

    def __init__(self, max_output: int = DEFAULT_MAX_OUTPUT):
        self.max_output = max_output

    def decompress(self, data: bytes, start: int) -> tuple[bytes, int]:
        if start >= len(data):
            return b'', 0
        out = bytearray()
        i = start
        end = len(data)
        while i < end and len(out) < self.max_output:
            ctrl = data[i]
            i += 1
            if ctrl >= 0x80:
                if i >= end:  # оборванный поток: возвращаем что распаковали
                    break
                out.extend(bytes([data[i]]) * ((ctrl & 0x7F) + 3))
                i += 1
            else:
                count = ctrl + 1
                chunk = data[i:i + count]
                out.extend(chunk)
                if len(chunk) < count:
                    # Хвост обрезан: не дорисовываем мусор и НЕ выдаём за
                    # consumed больше, чем реально лежит в потоке.
                    i += len(chunk)
                    break
                i += count
        consumed = i - start
        logger.debug('RLE: 0x%X -> %d байт, использовано %d',
                     start, len(out), consumed)
        return bytes(out), consumed

    def compress(self, raw: bytes) -> bytes:
        """Упаковывает по тому же формату (для round-trip и вставки).

        Серия из `N` одинаковых байт короче `3 + N` байт только при
        `N >= 4`: RLE берёт 1 (ctrl) + 1 (байт) и заменяет `N` байт, то есть
        при N=4 экономия нулевая, при N=3 — отрицательная. Поэтому порог 4,
        а не 3.
        """
        out = bytearray()
        i = 0
        n = len(raw)
        while i < n:
            byte = raw[i]
            run = 1
            while (run < RLE_MAX_RUN and i + run < n
                   and raw[i + run] == byte):
                run += 1
            if run >= 4:
                out.append(0x80 | (run - 3))
                out.append(byte)
                i += run
                continue
            # Литеральная серия: копим до RLE_MAX_LITERAL байт или до
            # появления выгодной серии.
            start = i
            lit = 0
            while (i < n and lit < RLE_MAX_LITERAL
                   and not _run_is_worthwhile(raw, i)):
                i += 1
                lit += 1
            if lit == 0:  # pragma: no cover - защита от бесконечного цикла
                i = start + 1
                lit = 1
            out.append(lit - 1)
            out.extend(raw[start:start + lit])
        return bytes(out)


def _run_is_worthwhile(raw: bytes, i: int) -> bool:
    """Есть ли в позиции `i` серия, которую выгодно кодировать RLE."""
    byte = raw[i]
    run = 1
    while i + run < len(raw) and raw[i + run] == byte and run < RLE_MAX_RUN:
        run += 1
    return run >= 4


class NintendoLZHandler(CompressionHandler):
    """LZ по флаговому байту с 12-битным смещением и 4-битной длиной."""

    def __init__(self, max_output: int = DEFAULT_MAX_OUTPUT):
        self.max_output = max_output

    def decompress(self, data: bytes, start: int) -> tuple[bytes, int]:
        if start >= len(data):
            return b'', 0
        out = bytearray()
        i = start
        end = len(data)
        while i < end and len(out) < self.max_output:
            flags = data[i]
            i += 1
            for bit in range(8):
                if i >= end or len(out) >= self.max_output:
                    break
                if flags & (0x80 >> bit):
                    if i + 1 >= end:
                        i = end
                        break
                    hi = data[i]
                    lo = data[i + 1]
                    i += 2
                    length = (hi >> 4) + 3
                    offset = ((hi & 0x0F) << 8) | lo
                    offset += 1
                    if offset > len(out):
                        # Ссылка в пустоту: поток битый. Обрываем, а не
                        # читаем мусор — иначе в отчёт уйдёт правдоподобный
                        # «текст» из нулей.
                        logger.debug('LZ: ссылка %d при выходе %d',
                                     offset, len(out))
                        return bytes(out), i - start
                    # Перекрывающееся копирование допустимо (offset < length).
                    src = len(out) - offset
                    for k in range(length):
                        out.append(out[src + k])
                else:
                    out.append(data[i])
                    i += 1
        consumed = i - start
        logger.debug('LZ: 0x%X -> %d байт, использовано %d',
                     start, len(out), consumed)
        return bytes(out), consumed

    def compress(self, raw: bytes) -> bytes:
        """Упаковывает: ссылка выгодна, только если длина >= 4.

        Поиск совпадения — хеш-цепочка по 2-байтовым префиксам, а не перебор
        всех расстояний. Прежний вариант стоил O(n x окно): измерено 1.1 с на
        4 КиБ, 8.2 с на 16 КиБ и **36 с на 64 КиБ** — то есть на собственном
        заявленном пределе вывода `DEFAULT_MAX_OUTPUT` блок сжимался полминуты,
        и в GUI это был бы замороз окна.

        Хеш-цепочка даёт ТОТ ЖЕ результат: кандидаты перебираются от
        ближайшего к дальнему, выигрывает строго более длинное совпадение, то
        есть при равной длине остаётся ближайшее расстояние — ровно как в
        брутфорсе. Пропускаются только позиции с несовпадающим префиксом, а
        совпадение короче префикса невозможно.
        """
        chain: dict[int, list[int]] = {}
        for i in range(0, max(0, len(raw) - 1)):
            chain.setdefault(raw[i] | (raw[i + 1] << 8), []).append(i)
        out = bytearray()
        pos = 0
        n = len(raw)
        while pos < n:
            flags_pos = len(out)
            out.append(0)
            flags = 0
            for bit in range(8):
                if pos >= n:
                    break
                offset, length = self._find_match(raw, pos, chain)
                if length >= 4:
                    value = offset - 1
                    hi = ((value >> 8) & 0x0F) | ((length - 3) << 4)
                    out.append(hi)
                    out.append(value & 0xFF)
                    flags |= 0x80 >> bit
                    pos += length
                else:
                    out.append(raw[pos])
                    pos += 1
            out[flags_pos] = flags
        return bytes(out)

    @staticmethod
    def _find_match(raw: bytes, pos: int,
                    chain: dict[int, list[int]]) -> tuple[int, int]:
        """Лучшее (смещение, длина) для повтора, начинающегося в `pos`.

        Только НАЗАД: позиции после `pos` пропускаются, иначе смещение
        становится отрицательным и чтение уходит за конец буфера.
        """
        limit = min(LZ_MAX_LENGTH, len(raw) - pos)
        if limit <= 0:
            return 0, 0
        max_offset = min(LZ_MAX_OFFSET, pos)
        best_offset = 0
        best_length = 0
        if pos + 1 >= len(raw):
            # Хвост из одного байта: префикса из двух нет.
            for offset in range(1, max_offset + 1):
                src = pos - offset
                if raw[src] == raw[pos]:
                    return offset, 1
            return 0, 0
        key = raw[pos] | (raw[pos + 1] << 8)
        bucket = chain.get(key)
        if not bucket:
            return 0, 0
        # Цепочка отсортирована по возрастанию, поэтому последний элемент
        # Строго меньше pos находится бисектом. Без этого приходилось
        # пропускать все позиции >= pos по одной, а их ровно столько же,
        # сколько всего прошло, — то есть O(n) на позицию и O(n²) на блок
        # (на блоке из нулей это давало 2.2 с).
        end = bisect_left(bucket, pos) - 1
        for index in range(end, -1, -1):
            src = bucket[index]
            offset = pos - src
            if offset > max_offset:
                break
            length = 2
            while length < limit and raw[src + length] == raw[pos + length]:
                length += 1
            if length > best_length:
                best_length = length
                best_offset = offset
                if best_length == limit:
                    break
        return best_offset, best_length


#: Минимальная доля «печатных» байт в распакованном выводе.
#: Проверено на 5 реальных GB/GBC ROM: критерий «только коэффициент роста»
#: объявлял RLE в 48 блоках из 40 на КАЖДОЙ игре, включая Zelda, которая
#: этим форматом не сжата, — потому что RLE-распаковка произвольных байт
#: почти всегда «растёт» (управляющий байт 0x80..0xFF выдаёт 3..130 копий).
#: Настоящий RLE-поток даёт 1.00, мусор — 0.00.
TEXT_LIKENESS_MIN = 0.80


def _text_likeness(data: bytes, printable: frozenset[int] | None) -> float:
    """Доля «печатных» байт: грубый признак «это текст».

    `printable` — множество байт, которые в ИГРЕ означают текст. Без него
    берётся ASCII-окно, и вот тут важная оговорка: **для Gen1/2 оно
    непригодно**. В `plugins/gb_pokemon_gen1.py` буквы лежат в 0x80..0x99,
    то есть вне ASCII на 100%; настоящий текст Gen1 давал likeness 0.018 и
    `guess_format` отвечал `none` на ВСЁМ. Поэтому charmap игр обязателен
    для GB/GBC, а ASCII — только дефолт для латиницы.
    """
    if not data:
        return 0.0
    if printable is None:
        ok = sum(1 for b in data
                 if 0x20 <= b <= 0x7E or b in (0x0A, 0x0D, 0x09))
    else:
        ok = sum(1 for b in data if b in printable)
    return ok / len(data)


def guess_format(data: bytes, start: int,
                 charmap: dict | None = None) -> tuple[str, float]:
    """Предполагает формат по двум признакам: `(имя, коэффициент роста)`.

    Эвристика, а не определение, и по замыслу она СКЛОННА ОТКАЗЫВАТЬСЯ.
    Требуются два условия: вывод заметно длиннее потока И вывод похож на
    текст. Без второго условия формат определяется на любом мусоре (на пяти
    реальных GB/GBC ROM старый код объявлял RLE в 48 блоках из 40 на
    КАЖДОЙ игре). Если сомнения — возвращается `none`: неверно назвать
    формат хуже, чем не назвать его вовсе.

    `charmap` — словарь `байт -> символ` конкретной игры (например
    `plugins.gb_pokemon_gen1.CHARMAP_GB`). Без него используется
    ASCII-окно, и для Gen1/2 это даёт ложный `none`: см. `_text_likeness`.

    Дальше формат ОБЯЗАН быть подтверждён RE на конкретной игре: модуль
    описывает формат, но не знает, какой именно ROM его использует.
    """
    if charmap is not None:
        printable = frozenset(
            b for b in charmap
            if isinstance(b, int) and not isinstance(b, bool)
        ) or None
    else:
        printable = None
    best_name = 'none'
    best_ratio = 0.0
    for name, handler in (('rle', ControlByteRLEHandler()),
                          ('lz', NintendoLZHandler())):
        out, consumed = handler.decompress(data, start)
        if consumed <= 0 or len(out) < 8:
            continue
        if _text_likeness(out[:1024], printable) < TEXT_LIKENESS_MIN:
            continue
        ratio = len(out) / consumed
        # Ветка «второй обработчик не лучше» недостижима: RLE- и
        # LZ-потоки взаимоисключающи по построению (управляющий байт
        # значит разное), поэтому оба обработчика не могут дать текст
        # на одном потоке. Проверено на потоках, сгенерированных обоими
        # компрессорами, и на 15 ручных комбинациях RLE-хвостов.
        if ratio > best_ratio:  # pragma: no branch
            best_name = name
            best_ratio = ratio
    if best_ratio < 1.05:
        return 'none', best_ratio
    return best_name, best_ratio


__all__ = [
    'DEFAULT_MAX_OUTPUT',
    'LZ_MAX_LENGTH',
    'LZ_MAX_OFFSET',
    'RLE_MAX_LITERAL',
    'RLE_MAX_RUN',
    'TEXT_LIKENESS_MIN',
    'CompressibleHandler',
    'ControlByteRLEHandler',
    'NintendoLZHandler',
    'guess_format',
]
