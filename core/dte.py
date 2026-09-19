"""DTE-хелпер: построитель byte-pair таблицы по биграммам (план 1.4).

DTE (dual tile encoding): частые пары символов кодируются одним байтом.
Модуль — чистые функции + DTEHandler (наследник CompressionHandler).

Контракты (заморожены пре-ревью):
- NET-профит пары = freq - table_entry_cost; profit_net <= 0 не берутся.
- Токены [XX]/{VAR}/%s и '\n' внутрь пар не входят (hard-break границ).
- free_bytes — ОТСОРТИРОВАННЫЙ список от вызывающей (disjoint от байтов
  текста/charset — предусловие); derive_free_bytes помогает его получить.
- Детерминизм: пары сортируются по (-profit_net, pair), байты назначаются
  из отсортированного free_bytes по порядку.
- Greedy left-to-right: совпало — шаг 2, иначе шаг 1 (round-trip однозначен).
- Одиночные символы кодируются ord() (ASCII-дефолт для синтетики; игры
  со своим charmap маппят заранее или расширяют обёрткой).
- DTEHandler(table) — subclass CompressionHandler (injector проверяет
  isinstance); в сегмент кладётся готовым instance, реестр не трогаем.
"""

from __future__ import annotations

import re

from core.compression import CompressionHandler

_TOKEN_RE = re.compile(r"\[[^\]]*\]|\{[^}]*\}|%(\d+\$)?[#+ 0-]*\d*(\.\d+)?[a-zA-Z%]|%")


def _masked_spans(text: str) -> list[tuple[int, int]]:
    """Диапазоны токенов и переносов (внутрь пар не входить).

    Незакрытые [/ { маскируются посимвольно (иначе пары режут формат).
    """
    spans = [(m.start(), m.end()) for m in _TOKEN_RE.finditer(text)]
    covered = [False] * len(text)
    for start, end in spans:
        for i in range(start, min(end, len(text))):
            covered[i] = True
    for i, ch in enumerate(text):
        if ch in "[{" and not covered[i]:
            spans.append((i, i + 1))
        if ch == "\n":
            spans.append((i, i + 1))
    return spans


def _in_masked(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


def _checked_rev(table: dict[str, int]) -> dict[int, str]:
    """Reverse-map с проверкой дубликатов кодов (иначе round-trip молча врёт)."""
    rev: dict[int, str] = {}
    for pair, byte in table.items():
        if byte in rev:
            raise ValueError(f"duplicate DTE code {byte:#x}: {rev[byte]!r} and {pair!r}")
        rev[byte] = pair
    return rev


def derive_free_bytes(used: set[int], reserved: tuple[int, ...] = (0x00,)) -> list[int]:
    """Отсортированные свободные значения 0x01-0xFF минус used/reserved.

    Вызывающая собирает used из ключей charset + байтов закодированных
    текстов; 0x00 зарезервирован (терминатор) по умолчанию.
    """
    reserved_set = set(reserved)
    return sorted(b for b in range(0x01, 0x100) if b not in used and b not in reserved_set)


def build_table(
    texts: list[str],
    free_bytes: list[int],
    max_pairs: int | None = None,
    table_entry_cost: int = 2,
) -> dict[str, int]:
    """Таблица {пара: байт} по NET-профиту биграмм.

    Пара — ровно 2 символа, целиком вне токенов/переносов. Профит =
    freq - table_entry_cost; неположительные отбрасываются. Байты
    назначаются топ-N парам (сортировка (-profit, pair)) из
    отсортированного free_bytes по порядку.
    """
    for byte in free_bytes:
        if not isinstance(byte, int) or isinstance(byte, bool):
            raise TypeError(f"free byte must be int 1-255, got {byte!r}")
        if byte < 0x01 or byte > 0xFF:
            raise ValueError(f"free byte out of range: {byte:#x}")
    if len(set(free_bytes)) != len(list(free_bytes)):
        raise ValueError("duplicate free_bytes")
    ordered_free = sorted(free_bytes)
    freq: dict[str, int] = {}
    for text in texts:
        if not isinstance(text, str):
            raise TypeError(f"translation must be str, got {type(text).__name__}")
        spans = _masked_spans(text)
        for i in range(len(text) - 1):
            if _in_masked(i, spans) or _in_masked(i + 1, spans):
                continue
            pair = text[i : i + 2]
            freq[pair] = freq.get(pair, 0) + 1
    ranked = sorted(
        ((f - table_entry_cost, pair) for pair, f in freq.items()),
        key=lambda item: (-item[0], item[1]),
    )
    profitable = [(profit, pair) for profit, pair in ranked if profit > 0]
    if max_pairs is not None:
        profitable = profitable[: max(0, max_pairs)]
    table: dict[str, int] = {}
    # strict=False: пар больше, чем байтов — лишние отбрасываются
    # (контролируется через max_pairs); байтов больше — остаток не used.
    for (_, pair), byte in zip(profitable, ordered_free, strict=False):
        table[pair] = byte
    return table


def encode(text: str, table: dict[str, int]) -> bytes:
    """Greedy left-to-right: совпала пара — шаг 2, иначе одиночный ord().

    Литерал, чей байт совпадает с DTE-кодом (нарушен disjoint), —
    громкий ValueError вместо тихой порчи (decode отдал бы пару).
    """
    rev = _checked_rev(table)
    out = bytearray()
    i = 0
    while i < len(text):
        pair = text[i : i + 2]
        if len(pair) == 2 and pair in table:
            out.append(table[pair])
            i += 2
        else:
            code = ord(text[i])
            if code > 255:
                raise ValueError(f"char out of byte range: {text[i]!r}")
            if code in rev:
                raise ValueError(f"literal {text[i]!r} (byte {code:#x}) collides with a DTE code: disjoint violated")
            out.append(code)
            i += 1
    return bytes(out)


def decode(data: bytes | bytearray, table: dict[str, int]) -> str:
    """Точное обратное к encode (коды различаются принадлежностью к table)."""
    rev = _checked_rev(table)
    out: list[str] = []
    for byte in data:
        if byte in rev:
            out.append(rev[byte])
        else:
            out.append(chr(byte))
    return "".join(out)


class DTEHandler(CompressionHandler):
    """DTE-кодек как CompressionHandler (compress сверх ABC-контракта)."""

    def __init__(self, table: dict[str, int]):
        self.table = dict(table)

    def compress(self, text: str) -> bytes:
        """Текст -> DTE-байты (см. encode)."""
        return encode(text, self.table)

    def decompress(self, data: bytes, start: int) -> tuple[bytes, int]:
        """DTE-байты -> исходный текст в байтах (длина потреблённого).

        Блоки DTE не self-delimiting: декодируется всё от start до конца;
        возвращается (bytes, потреблено). Текст возвращается UTF-8
        (для ASCII-текстов побайтово совпадает с encode-входом).
        start вне [0, len] — как у соседних хендлеров: пустой результат,
        а не исключение (конвейерная склейка блоков).
        """
        if start < 0:
            raise ValueError(f"bad start: {start}")
        if start >= len(data):
            return b"", 0
        text = decode(bytes(data[start:]), self.table)
        raw = text.encode("utf-8")
        return raw, len(data) - start
