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
"""

"""
Проверка орфографии переводов через pyspellchecker.

Подсвечивает опечатки в поле перевода редактора (red underline),
не трогая управляющие токены: [XX], {VAR}, %s, числа, переводы строк.
"""

import bisect
import re

# Слово: буквы кириллицы/латиницы (минимум 2) — одиночные буквы
# (артикли, предлоги) не считаем опечатками.
_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]{2,}")
# Фрагменты, которые не проверяются: [XX], {VAR}, %s, числа
# (включая hex-литералы 0xFF — иначе \d+ съедает только "0", а "xFF"
# находится как слово и даёт ложную опечатку).
_IGNORED_SPANS_RE = re.compile(
    r"0[xX][0-9A-Fa-f]+|"
    r"\[[^\]]*\]|"
    r"\{[^}]*\}|"
    r"%\S*|"
    r"\d+"
)

# Русская кириллица — для автоопределения языка
_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")

_CACHE_MAX = 512

# pyspellchecker.candidates() комбинаторно дорог и растёт с длиной слова.
# Для очень длинных токенов (имена собственные, звукоподражания) подсказки
# не считаем — слово всё равно попадает в отчёт как неизвестное.
_MAX_SUGGESTION_WORD_LEN = 10


def _auto_lang(text: str) -> str:
    """Выбирает язык по наличию кириллицы."""
    if _CYRILLIC_RE.search(text):
        return "ru"
    return "en"


def _iter_word_spans(text: str) -> list[tuple[int, int, str]]:
    """Все слова (start, end, word) — длины 2+ букв."""
    return [(m.start(), m.end(), m.group()) for m in _WORD_RE.finditer(text)]


def _in_ignored(start: int, ignored_starts, ignored_ends) -> bool:
    """Пересекается ли начало слова с игнор-диапазоном."""
    i = bisect.bisect_right(ignored_starts, start) - 1
    return 0 <= i < len(ignored_ends) and start < ignored_ends[i]


def _copy_errors(
    errors: list[tuple[int, int, str, list[str]]],
) -> list[tuple[int, int, str, list[str]]]:
    """Копия результата: кэш отдаёт копии, мутация caller'ом его не травит."""
    return [(s, e, w, list(sg)) for s, e, w, sg in errors]


class SpellCheckService:
    """Проверка орфографии с игнором токенов и кэшем результатов.

    Словари pyspellchecker загружаются лениво — при первом вызове
    check_text (при выключенной проверке словарь не грузится).
    """

    def __init__(self):
        self._checkers: dict[str, object] = {}
        self._cache: dict[
            tuple[str, str, bool],
            list[tuple[int, int, str, list[str]]],
        ] = {}

    @property
    def initialized(self) -> bool:
        """Словари ещё не подгружены."""
        return bool(self._checkers)

    def _get_checker(self, lang: str):
        if lang not in self._checkers:
            from spellchecker import SpellChecker

            if lang == "ru":
                self._checkers[lang] = SpellChecker(language=["ru", "en"])
            else:
                self._checkers[lang] = SpellChecker(language=["en"])
        return self._checkers[lang]

    def check_text(
        self,
        text: str,
        lang: str | None = "auto",
        with_suggestions: bool = True,
    ) -> list[tuple[int, int, str, list[str]]]:
        """Ищет опечатки в тексте.

        Args:
            text: исходная строка.
            lang: "ru", "en" или "auto" (по алфавиту).
            with_suggestions: считать ли варианты исправления через
                pyspellchecker.candidates(). GUI передаёт True (по
                умолчанию). Массовый инжект передаёт False: кандидаты —
                ~99% времени проверки на больших корпусах, а позиции и
                сами слова находятся и без них.

        Returns:
            Список (start, end, word, suggestions) — позиции 0-based
            в исходной строке. Токены ([XX], {VAR}, %s, числа) игнорируются.
        """
        if not text or not text.strip():
            return []

        if lang in (None, "", "auto"):
            lang_used = _auto_lang(text)
        else:
            lang_used = lang
        if lang_used not in ("ru", "en"):
            lang_used = "auto"

        cache_key = (text, lang_used, with_suggestions)
        if cache_key in self._cache:
            return _copy_errors(self._cache[cache_key])

        checker = self._get_checker(lang_used)

        ignored = list(_IGNORED_SPANS_RE.finditer(text))
        ignored_starts = [m.start() for m in ignored]
        ignored_ends = [m.end() for m in ignored]

        errors: list[tuple[int, int, str, list[str]]] = []
        for start, end, word in _iter_word_spans(text):
            if _in_ignored(start, ignored_starts, ignored_ends):
                continue
            if checker.unknown([word]):
                if with_suggestions and len(word) <= _MAX_SUGGESTION_WORD_LEN:
                    suggestions = list(checker.candidates(word) or ())
                else:
                    suggestions = []
                errors.append((start, end, word, suggestions))

        if len(self._cache) >= _CACHE_MAX:
            self._cache.clear()
        self._cache[cache_key] = errors
        return _copy_errors(errors)

    def clear_cache(self) -> None:
        self._cache.clear()


# Единый экземпляр для GUI/CLI
_service = SpellCheckService()


def check_text(
    text: str,
    lang: str | None = "auto",
    with_suggestions: bool = True,
) -> list[tuple[int, int, str, list[str]]]:
    """Module-level фасад."""
    return _service.check_text(
        text, lang=lang, with_suggestions=with_suggestions)
