"""DTE-хелпер: построитель byte-pair таблицы по биграммам (план 1.4).

ЭКСПЕРИМЕНТАЛЬНО: v3-добавки (TextCoder, byte-builder, masked encode)
проверены только синтетикой + in-memory пилотом на toy-кириллице;
ROM extract→insert→extract — follow-up (non-goal v3).

DTE (dual tile encoding): частые пары байтов кодируются одним байтом.
Модуль — чистые функции + DTEHandler (наследник CompressionHandler).

Контракты v1 (frozen, build_table/derive/encode-ascii/decode-ascii/HANDLER-ascii
не меняются; старые тесты зелёные без правок):
- NET-профит пары = freq - table_entry_cost; profit_net <= 0 не берутся.
- Токены [XX]/{VAR}/%s и '\n' внутрь пар не входят (hard-break границ);
  _masked_spans — единый источник истины (фиксированный набор v3,
  плагинизация — follow-up F2).
- free_bytes — ОТСОРТИРОВАННЫЙ список от вызывающей (disjoint от байтов
  текста/charset — предусловие); derive_free_bytes помогает его получить.
- Детерминизм: пары сортируются по (-profit_net, pair), байты назначаются
  из отсортированного free_bytes по порядку.
- Greedy left-to-right: совпало — шаг 2, иначе шаг 1 (round-trip однозначен).
- DTEHandler(table) — subclass CompressionHandler (injector проверяет
  isinstance); в сегмент кладётся готовым instance, реестр не трогаем.

Контракты v3 (байтовое пространство, GB/GBC 1 char → 1 byte):
- TextCoder{encode_char, decode_char} задаётся атомарно; encode_char:
  1 char → byte 0-255, немэппинг → ValueError; decode_char: byte → char,
  вне 0-255 → ValueError; ядро пробрасывает fail-fast. ASCII_CODER строгий
  (ord>255 → ValueError, клампа нет).
- build_for_translation(translations, *, extra_used=(), coder=ASCII_CODER,
  max_pairs=None, table_entry_cost=2, reserved=(0x00,)): used = coder-байты
  литеральных ранов ∪ coder-байты token-спанов ∪ extra_used ∪ reserved;
  free = sorted(0x01..0xFF − used). extra_used/reserved: int 0-255 (bool
  reject), иначе ValueError. Пример: extra_used={0x00, 0xFF, control-байты}.
- freq overlapping шагом +1; max_pairs: None=uncapped, 0=valid empty,
  <0 → ValueError (у build_table остался legacy clamp — не трогать).
- table_cost = len(table)*table_entry_cost (estimate до F4); stats —
  литеральные раны only (без токенов/терминаторов/релокейшена).
- Незакрытый opener: masked-singleton (в парах не участвует, одиночно
  кодируется); хвост после него eligible.
- Non-goals/Follow-ups: F1 ROM extract→insert→extract; F2 плагинизация
  токен-паттерна (бинарные контролы — на вызывающей/плагине); F3 реальные
  Cyrillic charmap'ы; F4 привязка table_cost к on-disk формату.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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


def _checked_rev(table: dict[Any, int]) -> dict[int, Any]:
    """Reverse-map с проверкой дубликатов кодов (иначе round-trip молча врёт)."""
    rev: dict[int, str] = {}
    for pair, byte in table.items():
        if byte in rev:
            raise ValueError(f"duplicate DTE code {byte:#x}: {rev[byte]!r} and {pair!r}")
        rev[byte] = pair
    return rev


@dataclass(frozen=True)
class TextCoder:
    """Атомарная пара 1 char ↔ 1 byte (GB/GBC). Немэппинг → ValueError."""

    encode_char: Callable[[str], int]
    decode_char: Callable[[int], str]


def _ascii_encode_char(ch: str) -> int:
    if not isinstance(ch, str) or len(ch) != 1:
        raise ValueError(f"coder needs single char: {ch!r}")
    code = ord(ch)
    if code < 0 or code > 255:
        raise ValueError(f"char out of byte range: {ch!r}")
    return code


def _ascii_decode_char(code: int) -> str:
    if isinstance(code, bool) or not isinstance(code, int) or code < 0 or code > 255:
        raise ValueError(f"byte out of range: {code!r}")
    return chr(code)


ASCII_CODER = TextCoder(_ascii_encode_char, _ascii_decode_char)


def _coder_byte(coder: TextCoder, ch: str) -> int:
    code = coder.encode_char(ch)
    if isinstance(code, bool) or not isinstance(code, int) or code < 0 or code > 255:
        raise ValueError(f"coder byte out of range for {ch!r}: {code!r}")
    return code


def _literal_runs(spans: list[tuple[int, int]], length: int) -> list[tuple[int, int]]:
    """Дополнение merged-масок: интервалы литералов [start, end)."""
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    runs: list[tuple[int, int]] = []
    pos = 0
    for start, end in merged:
        if pos < start:
            runs.append((pos, start))
        pos = max(pos, end)
    if pos < length:
        runs.append((pos, length))
    return runs


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


def encode(text: str, table: dict[str, int], coder: TextCoder = ASCII_CODER) -> bytes:
    """Greedy left-to-right: совпала пара — шаг 2, иначе одиночный coder.

    Пара формируется только если обе позиции вне маски (зеркало freq);
    masked-одиночки кодируются через coder (game-remap токенов — consumer).
    Литерал, чей байт совпадает с DTE-кодом (нарушен disjoint), —
    громкий ValueError вместо тихой порчи (decode отдал бы пару).
    """
    if not isinstance(coder, TextCoder):
        raise TypeError(f"coder must be TextCoder, got {type(coder).__name__}")
    rev = _checked_rev(table)
    spans = _masked_spans(text)
    out = bytearray()
    i = 0
    while i < len(text):
        pair = text[i : i + 2]
        if len(pair) == 2 and pair in table and not _in_masked(i, spans) and not _in_masked(i + 1, spans):
            out.append(table[pair])
            i += 2
        else:
            code = _coder_byte(coder, text[i])
            if code in rev:
                raise ValueError(f"literal {text[i]!r} (byte {code:#x}) collides with a DTE code: disjoint violated")
            out.append(code)
            i += 1
    return bytes(out)


def decode(data: bytes | bytearray, table: dict[str, int], coder: TextCoder = ASCII_CODER) -> str:
    """Точное обратное к encode (коды различаются принадлежностью к table)."""
    if not isinstance(coder, TextCoder):
        raise TypeError(f"coder must be TextCoder, got {type(coder).__name__}")
    rev = _checked_rev(table)
    out: list[str] = []
    for byte in data:
        if byte in rev:
            out.append(rev[byte])
        else:
            out.append(coder.decode_char(byte))
    return "".join(out)


def build_byte_table(
    frags: list[bytes],
    free_bytes: list[int],
    max_pairs: int | None = None,
    table_entry_cost: int = 2,
) -> dict[tuple[int, int], int]:
    """Таблица {(b1,b2): код} по NET-профиту байтовых биграмм (overlapping +1).

    free ∩ байты frags → громкий ValueError ДО построения (precondition
    вызывающей; пустая таблица нарушение тоже ловит).
    max_pairs: None=uncapped, 0=valid empty, <0 → ValueError (намеренно
    строже legacy-clamp build_table — задокументировано).
    table_entry_cost<1 → ValueError.
    """
    if not isinstance(frags, (list, tuple)):
        raise TypeError(f"frags must be a list, got {type(frags).__name__}")
    norm: list[bytes] = []
    for frag in frags:
        if not isinstance(frag, (bytes, bytearray)):
            raise TypeError(f"frag must be bytes, got {type(frag).__name__}")
        norm.append(bytes(frag))
    for byte in free_bytes:
        if not isinstance(byte, int) or isinstance(byte, bool):
            raise TypeError(f"free byte must be int 1-255, got {byte!r}")
        if byte < 0x01 or byte > 0xFF:
            raise ValueError(f"free byte out of range: {byte:#x}")
    if len(set(free_bytes)) != len(list(free_bytes)):
        raise ValueError("duplicate free_bytes")
    if max_pairs is not None:
        if isinstance(max_pairs, bool) or not isinstance(max_pairs, int):
            raise TypeError(f"max_pairs must be int|None, got {max_pairs!r}")
        if max_pairs < 0:
            raise ValueError(f"max_pairs negative: {max_pairs}")
    if isinstance(table_entry_cost, bool) or not isinstance(table_entry_cost, int) or table_entry_cost < 1:
        raise ValueError(f"bad table_entry_cost: {table_entry_cost!r}")
    ordered_free = sorted(free_bytes)
    freq: dict[tuple[int, int], int] = {}
    used: set[int] = set()
    for frag in norm:
        used.update(frag)
        for i in range(len(frag) - 1):
            pair = (frag[i], frag[i + 1])
            freq[pair] = freq.get(pair, 0) + 1
    if set(ordered_free) & used:
        raise ValueError("free bytes overlap used bytes: disjoint violated")
    ranked = sorted(
        ((f - table_entry_cost, pair) for pair, f in freq.items()),
        key=lambda item: (-item[0], item[1]),
    )
    profitable = [(profit, pair) for profit, pair in ranked if profit > 0]
    if max_pairs is not None:
        profitable = profitable[:max_pairs]
    table: dict[tuple[int, int], int] = {}
    # strict=False: пар больше, чем байтов — лишние отбрасываются.
    for (_, pair), byte in zip(profitable, ordered_free, strict=False):
        table[pair] = byte
    return table


def encode_bytes(data: bytes | bytearray, table: dict[tuple[int, int], int]) -> bytes:
    """Greedy 2/1 по байтам (ключи таблицы — 2-кортежи).

    Литерал, равный DTE-коду, — громкий ValueError (зеркало str-encode):
    decode отдал бы пару (данные вне обучающих frags).
    """
    rev = _checked_rev(table)
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        if i + 1 < n and (data[i], data[i + 1]) in table:
            out.append(table[(data[i], data[i + 1])])
            i += 2
        else:
            if data[i] in rev:
                raise ValueError(f"literal byte {data[i]:#x} collides with a DTE code: disjoint violated")
            out.append(data[i])
            i += 1
    return bytes(out)


def decode_bytes(data: bytes | bytearray, table: dict[tuple[int, int], int]) -> bytes:
    """Точное обратное к encode_bytes."""
    rev = _checked_rev(table)
    out = bytearray()
    for byte in data:
        if byte in rev:
            out.extend(rev[byte])
        else:
            out.append(byte)
    return bytes(out)


def _validated_byte_set(values, name: str) -> set[int]:
    if not isinstance(values, (set, frozenset, list, tuple)):
        raise TypeError(f"{name} must be a set/list/tuple, got {type(values).__name__}")
    out: set[int] = set()
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > 255:
            raise ValueError(f"{name} bad byte: {value!r}")
        out.add(value)
    return out


def build_for_translation(
    translations: list[str],
    *,
    extra_used: set[int],
    coder: TextCoder = ASCII_CODER,
    max_pairs: int | None = None,
    table_entry_cost: int = 2,
    reserved: tuple[int, ...] = (0x00,),
) -> dict:
    """Таблица под конкретный перевод: {table, free, stats}.

    used = coder-байты литеральных ранов ∪ coder-байты token-спанов
    ∪ extra_used ∪ reserved; free = sorted(0x01..0xFF − used).
    stats фактическим прогоном encode_bytes: raw/dte по литеральным ранам,
    table_cost = len(table)*cost (estimate), saved = raw − dte − table_cost.
    extra_used без дефолта (fail-safe: терминатор/pad/control-байты ROM).
    """
    if not isinstance(translations, (list, tuple)):
        raise TypeError(f"translations must be a list, got {type(translations).__name__}")
    if not isinstance(coder, TextCoder):
        raise TypeError(f"coder must be TextCoder, got {type(coder).__name__}")
    for text in translations:
        if not isinstance(text, str):
            raise TypeError(f"translation must be str, got {type(text).__name__}")
    extra = _validated_byte_set(extra_used, "extra_used")
    res = _validated_byte_set(reserved, "reserved")
    used: set[int] = set(extra) | res
    frags: list[bytes] = []
    for text in translations:
        spans = _masked_spans(text)
        for start, end in spans:
            for pos in range(start, min(end, len(text))):
                used.add(_coder_byte(coder, text[pos]))
        for start, end in _literal_runs(spans, len(text)):
            frag = bytes(_coder_byte(coder, text[pos]) for pos in range(start, end))
            frags.append(frag)
            used.update(frag)
    free = derive_free_bytes(used)
    table = build_byte_table(frags, free, max_pairs, table_entry_cost)
    encoded = [encode_bytes(frag, table) for frag in frags]
    raw = sum(len(frag) for frag in frags)
    dte = sum(len(item) for item in encoded)
    cost = len(table) * table_entry_cost
    stats = {"raw_bytes": raw, "dte_bytes": dte, "table_cost": cost, "saved_bytes": raw - dte - cost}
    return {"table": table, "free": free, "stats": stats}


class DTEHandler(CompressionHandler):
    """DTE-кодек как CompressionHandler (compress сверх ABC-контракта)."""

    def __init__(self, table: dict[str, int], coder: TextCoder = ASCII_CODER):
        if not isinstance(coder, TextCoder):
            raise TypeError(f"coder must be TextCoder, got {type(coder).__name__}")
        self.table = dict(table)
        self.coder = coder

    def compress(self, text: str) -> bytes:
        """Текст -> DTE-байты (см. encode)."""
        return encode(text, self.table, self.coder)

    def decompress(self, data: bytes, start: int) -> tuple[bytes, int]:
        """DTE-байты -> base-байты coder-пространства (НЕ utf-8).

        Для ASCII 0-127 совпадает побайтово со старым (decode+utf-8);
        128-255 — base-байты (потребитель декодирует через coder/charset,
        не через utf-8).
        Блоки DTE не self-delimiting: декодируется всё от start до конца.
        start вне [0, len] — как у соседних хендлеров: пустой результат,
        а не исключение (конвейерная склейка блоков).
        """
        if start < 0:
            raise ValueError(f"bad start: {start}")
        if start >= len(data):
            return b"", 0
        rev = _checked_rev(self.table)
        out = bytearray()
        for byte in bytes(data[start:]):
            if byte in rev:
                for ch in rev[byte]:
                    out.append(_coder_byte(self.coder, ch))
            else:
                out.append(byte)
        return bytes(out), len(data) - start
