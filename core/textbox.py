"""Симулятор textbox: влезает ли перевод в ширину слота (F1, 1.4).

Символьная эвристика (попиксельных glyph-width данных нет — честный
fallback): ширина в символах, перенос по словам. Управляющие токены
([XX], {VAR}, %s) не рвутся по границам слов, НО режутся жёстко, если
сам токен длиннее ширины; считаются посимвольно (не zero-width:
консервативно — лучше ложный флаг, чем пропуск). '\n' —
принудительный разрыв. Game-specific control-коды вне скоупа.

Интеграция: TextInjector.last_fit_report (мягкий паттерн — report-only,
запись не блокируется). Дисциплина отчётов: last_fit_report сбрасывается
в КАЖДОЙ точке входа инжектора (inject_segment, inject_language_block,
inject_interleaved_language); три отчёта (overflow/spellcheck/fit) живут
параллельно и не затирают друг друга. Вычисляется только там, где есть
данные о ширине (inject_segment: max_length/fixed_width сегмента);
в языковых блоках без сегментных данных — честное [].
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"\[[^\]]*\]|\{[^}]*\}|%\S")


def _visible_len(chunk: str) -> int:
    """Видимая длина: токены считаются как есть, посимвольно."""
    return len(chunk)


def _split_words(paragraph: str) -> list[tuple[str, bool]]:
    """Слова параграфа токен-осознанно: (слово, был_ли_пробел_после).

    Скобочные токены отделяются от слитного текста, а %-формат (100%s)
    держится слитно. Незакрытые [/ { съедаются по одному символу (без
    вечного цикла). Пробел после слова запоминается, чтобы склейка
    не вставляла пробелов туда, где их не было ('ab[CD]ef').
    """
    words: list[tuple[str, bool]] = []
    pos = 0
    while pos < len(paragraph):
        if paragraph[pos] == " ":
            pos += 1
            continue
        m = _TOKEN_RE.match(paragraph, pos)
        if m:
            end = m.end()
        else:
            end = pos
            while end < len(paragraph) and paragraph[end] != " ":
                # Скобочные токены отделяем, а %-формат держим слитно.
                if paragraph[end] in "[{":
                    break
                end += 1
            if end == pos:
                end = pos + 1
        word = paragraph[pos:end]
        rest = paragraph[end:]
        spaced = rest[:1] == " "
        words.append((word, spaced))
        pos = end
    return words


def split_lines(text: str, width: int) -> list[str]:
    """Разбивает текст на строки шириной не более width символов.

    Перенос по пробелам; токены [XX]/{VAR}/%s не рвутся; длинные слова
    без пробелов режутся жёстко; '\n' — принудительный разрыв. Пустые
    куски от крайних пробелов отбрасываются. width < 1 трактуется как 1.
    """
    width = max(1, width)
    out: list[str] = []
    for paragraph in text.split("\n"):
        words = _split_words(paragraph)
        current = ""
        current_spaced = True
        for word, spaced in words:
            while _visible_len(word) > width:
                if current:
                    out.append(current)
                    current = ""
                    current_spaced = True
                out.append(word[:width])
                word = word[width:]
            if not current:
                current = word
            elif current_spaced and _visible_len(current) + 1 + _visible_len(word) <= width:
                current += " " + word
            elif not current_spaced and _visible_len(current) + _visible_len(word) <= width:
                current += word
            else:
                out.append(current)
                current = word
            current_spaced = spaced
        if current:
            out.append(current)
        if not words:
            out.append("")
    return out


def segment_width(segment: dict) -> int | None:
    """Ширина слота сегмента в символах (None — данных нет).

    Зеркалит семантику injector (max_length приоритетен, иначе
    fixed_width-1): max_length=0 означает окно нулевой ширины (возврат 0,
    не None); bool-значения игнорируются как мусор.
    """
    if "max_length" in segment:
        max_length = segment["max_length"]
        if isinstance(max_length, bool):
            return None
        if isinstance(max_length, int) and max_length >= 0:
            return int(max_length)
        return None
    fixed_width = segment.get("fixed_width")
    if isinstance(fixed_width, bool):
        return None
    if isinstance(fixed_width, int) and fixed_width > 1:
        return int(fixed_width) - 1
    return None


def fit_report(segment: dict, translations: list[str] | None, width: int | None = None) -> list[dict]:
    """Отчёт о влезании переводов: [{index, ok, overflow_chars, lines_used}].

    width явно или из сегмента (max_length / fixed_width-1); width<=0 —
    окно нулевой ширины (всё непустое не влезает). translations=None
    трактуется как []. Без данных о ширине (None) все записи ok=True
    с lines_used=1 (ограничение неизвестно — не шуммим).
    ok = ни одно слово не пришлось рвать посередине; overflow_chars =
    суммарно символов сверх ширины в порванных словах; lines_used =
    число строк после переноса (информативно: лимита строк в данных
    сегментов нет).
    """
    if translations is None:
        translations = []
    if width is None:
        width = segment_width(segment)
    if width is not None:
        width = max(0, width)
    report: list[dict] = []
    for i, text in enumerate(translations):
        if not isinstance(text, str):
            text = str(text)
        if width is None:
            report.append({"index": i, "ok": True, "overflow_chars": 0, "lines_used": 1})
            continue
        words: list[str] = []
        for paragraph in text.split("\n"):
            words.extend(word for word, _ in _split_words(paragraph))
        overflow = sum(max(0, _visible_len(word) - width) for word in words)
        lines = split_lines(text, max(1, width))
        report.append(
            {
                "index": i,
                "ok": overflow == 0,
                "overflow_chars": overflow,
                "lines_used": len(lines),
            }
        )
    return report
