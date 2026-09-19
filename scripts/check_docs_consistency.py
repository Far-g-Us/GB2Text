#!/usr/bin/env python3
"""Детерминированный, офлайн, stdlib-only чекер консистентности
документации GB2Text (docs/en $ docs/ru роутер-тесты, которые мы
раньше чинили вручную). Ловит регрессии трёх типов:

1. links  — все markdown/HTML-ссылки и изображения в *.md резолвятся
            в существующие файлы/директории/якоря; запрещены двойные
            каталоги (en/en, ru/ru) и path-traversal за пределы
            репозитория. Внешние URL/уникальные якоря — валидны.
2. routers — 4 роутера (корневой README.md, docs/index.md,
            docs/en/README.md, docs/ru/README.md) ссылаются на
            download.md (Download-роутер).
3. legal  — семантический legal-канон в en/ru парах 4 файлов:
            (1) только ROM, которыми владеете законно;
            (3a) [в блоке Legal] канон "не содержит/не распространяет
            коммерческие файлы ROM / commercial ROM files";
            (3b) [только в download.md] non-affiliation (не аффилирован
            с Nintendo). README non-affiliation НЕ требуется.

Поведение: ненулевой exit и "file:line: описание" в stderr при любой
проблеме (жёсткий гейт; готово для GitHub annotations). Режимы:
--mode links|routers|legal, --all, --quiet. Без зависимостей и сети.

Спека GitHub-slug (для проверки якорей) — дословный порт
github-slugger (Flet/github-slugger, MIT, master), сверен критиком
побайтово с фактическим index.js + regex.js:
порядок toLowerCase -> replace(blacklist,"") -> replace(/ /g,"-");
БЕЗ NFC/NFKD-нормализации; U+FE0F (VS16) СОХРАНЯЕТСЯ (диапазон
U+FE00-FE0F в blacklist ОТСУТСТВУЕТ); "&" удаляется (двойной пробел ->
двойной дефис); кириллица сохраняется; эмодзи-базы U+1F000-U+1FAFF
(и суррогатные пары в JS-терминах) удаляются; trim отсутствует;
дубликаты заголовков -> суффиксы -1/-2 по счёту вхождений.
Полная спека и эталоны: .agent/tasks/docs-consistency/README.slugger-spec.md.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

# --- GitHub-slug: blacklist — порт regex из github-slugger regex.js.
# U+24EA-U+2BFF (эмодзи/пиктограммы/кит. ТОЧКИ), U+2E30-U+2E7F (punct),
# U+2E80-U+2FFF (CJK-штрихи), U+3000-U+303E+U+3041-U+30FF (CJK/Kana),
# U+3105-U+312F / U+3131-U+318E (Bopomofo/Hangul), U+3190-U+321E,
# U+3220-U+3247, U+3250-U+32FE, U+3300-U+4DBF, U+4E00-U+A48C,
# U+A490-U+A4C6, U+A960-U+A97C, U+AC00-U+D7A3, U+F900-U+FAFF,
# U+FF00-U+FF60, U+FFE0-U+FFE6
# + эмодзи U+1F000-U+1FAFF базы (см. спек). Символ & и прочая ASCII-
# пунктуация удаляются; ASCII-дефис НЕ удаляется; U+FE0F не входит.
_SLUG_BLACKLIST = re.compile(
    "["
    "\u24ea-\u2bff"
    "\u2e30-\u2e7f"
    "\u2e80-\u2fff"
    "\u3000-\u303e"
    "\u3041-\u30ff"
    "\u3105-\u312f"
    "\u3131-\u318e"
    "\u3190-\u321e"
    "\u3220-\u3247"
    "\u3250-\u32fe"
    "\u3300-\u4dbf"
    "\u4e00-\ua48c"
    "\ua490-\ua4c6"
    "\ua960-\ua97c"
    "\uac00-\ud7a3"
    "\uf900-\ufaff"
    "\uff00-\uff60"
    "\uffe0-\uffe6"
    "\U0001f000-\U0001faff"
    "!\"#$%&'()*+,./:;<=>?@[\\]^`{|}~"
    "]"
)
_SLUG_SPACE = re.compile(" ")


def github_slug(value: object, maintain_case: bool = False) -> str:
    """Порт github-slugger index.js дословно по спеке.

    type-guard: не-str -> ""; toLowerCase (если не maintainCase);
    replace(blacklist,""); replace(/ /g,"-").
    """
    if not isinstance(value, str):  # дословно из index.js
        return ""
    if maintain_case:
        slug = value
    else:
        slug = value.lower()
    slug = _SLUG_BLACKLIST.sub("", slug)
    slug = _SLUG_SPACE.sub("-", slug)
    return slug


def split_link_target(target: str) -> tuple[str, str | None]:
    """Разделение target на (путь, якорь). Учитывает # внутри URL."""
    hash_idx = target.find("#")
    if hash_idx == -1:
        return target, None
    return target[:hash_idx], target[hash_idx + 1 :]


_EXTERNAL_PREFIX = ("http://", "https://", "ftp://", "mailto:", "//", "tel:", "data:")
_URL_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:")


def _is_external(target: str) -> bool:
    low = target.lower()
    if low.startswith(_EXTERNAL_PREFIX) or low.startswith("//"):
        return True
    if re.match(r"^[A-Za-z]:[/\\]", target):
        return False  # Windows drive path (C:/...), not URL scheme
    return bool(_URL_SCHEME.match(low)) and ":" in low


def _decode_path(target: str) -> str:
    """Процент-декодирование как браузер резолвит ссылки + разультинг."""
    import urllib.parse

    return urllib.parse.unquote(target)


# --- кэш якорей файла (slug -> сколько раз встретился; -1/-2 суффиксы) ---
_SLUG_CACHE: dict[Path, dict[str, int]] = {}


def _file_slugs(path: Path) -> dict[str, int]:
    """Сканирование заголовков в файле: slug -> количество вхождений.

    GitHub доставляет дубликаты -1/-2 по счёту встречаемости (второй
    с таким же заголовком -> -1, третий -> -2, ...): counts[slug]=N.
    """
    if path in _SLUG_CACHE:
        return _SLUG_CACHE[path]
    counts: dict[str, int] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        _SLUG_CACHE[path] = counts
        return counts
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if not m:
            continue
        heading = re.sub(r"\s+#+$", "", m.group(1))
        slug = github_slug(heading)
        if not slug:
            continue
        counts[slug] = counts.get(slug, 0) + 1
    _SLUG_CACHE[path] = counts
    return counts


def _resolve_anchor(slug: str, path: Path | None) -> bool:
    """Существует ли якорь (slug или slug-1/-2 вариации) в файле."""
    counts = _file_slugs(path) if path else {}
    if not slug:
        return True  # пустой slug от пустого/символьного заголовка
    if slug in counts:
        return True
    # `slug-N`: база встречалась >= N+1 раз (второй заголовок -> -1);
    # N>=1 без ведущих нулей (GitHub не генерирует -0/-01)
    m = re.fullmatch(r"(.+)-([1-9]\d*)$", slug)
    if m and counts.get(m.group(1), 0) >= int(m.group(2)) + 1:
        return True
    return False


def _resolve_local(root: Path, base_dir: Path, target: str, current_file: Path | None = None) -> tuple[bool, str]:
    """Резолв файловой ссылки (путь + якорь) относительно base_dir.

    Возвращает (ok, описание). Проверяет: существование, двойные
    каталоги (en/en, ru/ru), traversal за пределы root, якоря
    (включая #anchor текущего файла и anchor у директорий).
    """
    path_raw, anchor_raw = split_link_target(target)
    path_part = _decode_path(path_raw)
    anchor = _decode_path(anchor_raw) if anchor_raw is not None else None
    if not path_part:
        # только якорь — валидируем против текущего файла
        if anchor and current_file is not None and not _resolve_anchor(anchor, current_file):
            return False, f"anchor not found: #{anchor} in current file"
        return True, ""
    if _is_external(path_part):
        return True, ""

    # убираем query-строку
    path_part = path_part.split("?")[0]
    # нормализация слешей (браузер резолвит слэши)
    path_part = path_part.replace("\\", "/")
    # защита от двойных каталогов en/en, ru/ru (кросс-пары en/ru валидны)
    if re.search(r"(?:^|/)(?:en/en|ru/ru)(?:/|$)", path_part):
        return False, f"double directory in path: {path_part}"

    fspath = (base_dir / path_part).resolve()
    try:
        fspath.relative_to(root.resolve())
    except ValueError:
        return False, f"path escapes repository root: {path_part}"

    exists = fspath.exists()
    if not exists:
        return False, f"missing target: {path_part}"
    if fspath.is_dir():
        # директория — допустимый target, но anchor проверяем по индексу
        if anchor:
            for index in ("README.md", "index.md"):
                idx = fspath / index
                if idx.is_file():
                    if not _resolve_anchor(anchor, idx):
                        return False, f"anchor not found: #{anchor} in {path_part}"
                    return True, ""
            return False, f"anchor not found: #{anchor} in {path_part} (no index)"
        return True, ""
    if anchor:
        if not _resolve_anchor(anchor, fspath):
            return False, f"anchor not found: #{anchor} in {path_part}"
    return True, ""


_LINK_PATTERN = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+(?:\([^)]*\))?[^)]*)\)")
_REF_PATTERN = re.compile(r"^[ \t]*\[([^\]]+)\]:[ \t]*(\S+)(?:[ \t].*)?$", re.M)
_REF_USE_PATTERN = re.compile(r"(?<!!)\[([^\]]+)\]\[([^\]]*)\]")
_REF_IMG_USE_PATTERN = re.compile(r"!\[([^\]]+)\]\[([^\]]*)\]")
_IMG_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)\s]+(?:\([^)]*\))?[^)]*)\)")
_HTML_A_PATTERN = re.compile(r"<a\b[^>]*href\s*=\s*[\"']([^\"']+)[\"'][^>]*>", re.I)
_HTML_IMG_PATTERN = re.compile(r"<img\b[^>]*src\s*=\s*[\"']([^\"']+)[\"'][^>]*>", re.I)


def check_links(root: Path, files: Sequence[Path], exclusions: Sequence[str] = ()) -> list[str]:
    problems: list[str] = []
    exc = [os.path.normpath(e) for e in exclusions]
    for path in files:
        rel = path.relative_to(root).as_posix()
        if any(rel.startswith(e) or rel == e for e in exc):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as err:
            problems.append(f"{path}:unreadable: {err}")
            continue
        base = path.parent
        for m in _LINK_PATTERN.finditer(text):
            ok, why = _resolve_local(root, base, m.group(2), path)
            if not ok:
                problems.append(
                    f"{path}:{text[: m.start()].count(chr(10)) + 1}: broken link [{m.group(1)}]({m.group(2)}): {why}"
                )
        for m in _IMG_PATTERN.finditer(text):
            ok, why = _resolve_local(root, base, m.group(2), path)
            if not ok:
                problems.append(
                    f"{path}:{text[: m.start()].count(chr(10)) + 1}: broken image [{m.group(1)}]({m.group(2)}): {why}"
                )
        defs = {m.group(1).lower(): m.group(2) for m in _REF_PATTERN.finditer(text)}
        for label, target in defs.items():
            ok, why = _resolve_local(root, base, target, path)
            if not ok:
                problems.append(f"{path}: broken reference [{label}]: {target}: {why}")
        for m in _REF_USE_PATTERN.finditer(text):
            label = (m.group(2) or m.group(1)).lower()
            if label not in defs:
                problems.append(
                    f"{path}:{text[: m.start()].count(chr(10)) + 1}: undefined reference [{m.group(1)}][{m.group(2)}]"
                )
        for m in _REF_IMG_USE_PATTERN.finditer(text):
            label = (m.group(2) or m.group(1)).lower()
            if label not in defs:
                problems.append(
                    f"{path}:{text[: m.start()].count(chr(10)) + 1}: undefined image reference [{m.group(1)}][{m.group(2)}]"
                )
        for m in _HTML_A_PATTERN.finditer(text):
            ok, why = _resolve_local(root, base, m.group(1), path)
            if not ok:
                problems.append(f"{path}:{text[: m.start()].count(chr(10)) + 1}: broken <a href>: {m.group(1)}: {why}")
        for m in _HTML_IMG_PATTERN.finditer(text):
            ok, why = _resolve_local(root, base, m.group(1), path)
            if not ok:
                problems.append(f"{path}:{text[: m.start()].count(chr(10)) + 1}: broken <img src>: {m.group(1)}: {why}")
    return problems


# --- routers: 4 роутера содержат ссылку на download.md ---
ROUTER_FILES = ("README.md", "docs/index.md", "docs/en/README.md", "docs/ru/README.md")


def check_routers(root: Path) -> list[str]:
    problems: list[str] = []
    for rel in ROUTER_FILES:
        path = root / rel
        if not path.exists():
            problems.append(f"{path}:MISSING router file does not exist")
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as err:
            problems.append(f"{path}:unreadable: {err}")
            continue
        if "download.md" not in text:
            problems.append(f"{path}:router does not reference download.md")
    return problems


# --- legal: семантическая проверка канона ---
LEGAL_FILES = (
    "docs/en/README.md",
    "docs/ru/README.md",
    "docs/en/download.md",
    "docs/ru/download.md",
)

LEGAL_MARKERS_EN = {
    "own": ("legally own", "legally", "own"),
    "no-commercial": ("does NOT contain or distribute", "commercial ROM files"),
    "no-commercial-short": ("commercial ROM files",),
}
LEGAL_MARKERS_RU = {
    "own": ("законных основаниях", "владеете", "принадлежат"),
    "no-commercial": ("не содержит и не распространяет", "коммерческие файлы ROM"),
    "no-commercial-short": ("коммерческие файлы ROM",),
}


def _term_hit(term: str, low: str) -> bool:
    """Одиночные слова — по границе слова (иначе 'own' матчится в 'download')."""
    t = term.lower()
    if " " in t:
        return t in low
    return re.search(r"\b" + re.escape(t) + r"\b", low) is not None


def _check_legal_semantics(text: str, lang: str) -> list[str]:
    problems: list[str] = []
    markers = LEGAL_MARKERS_EN if lang == "en" else LEGAL_MARKERS_RU
    low = re.sub(r"\s+", " ", text.replace(">", " ")).lower()
    for key, terms in markers.items():
        if not any(_term_hit(term, low) for term in terms):
            problems.append(f"missing legal statement: {key}")
    return problems


def check_legal(root: Path) -> list[str]:
    problems: list[str] = []
    for rel in LEGAL_FILES:
        path = root / rel
        if not path.exists():
            problems.append(f"{path}:MISSING legal file does not exist")
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as err:
            problems.append(f"{path}:unreadable: {err}")
            continue
        lang = "en" if "/en/" in rel else "ru"
        if rel.endswith("download.md"):
            # (3b) non-affiliation — только здесь; семантически: оба токена
            low = re.sub(r"\s+", " ", text.replace(">", " ")).lower()
            if lang == "en" and not ("affiliated" in low and "endorsed" in low):
                problems.append(f"{path}:missing non-affiliation statement")
            if lang == "ru" and not ("аффилирован" in low and "одобрен" in low):
                problems.append(f"{path}:missing non-affiliation statement")
        sub = _check_legal_semantics(text, lang)
        for s in sub:
            problems.append(f"{path}:{s}")
    return problems


def discover_md_files(root: Path) -> list[Path]:
    files = sorted(root.rglob("*.md"))
    skip_parts = {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        "htmlcov",
        "dist",
        "build",
        "test_roms",
        ".agent",
        ".opencode",
        ".claude",
        "docs_roms",
        "scripts_roms",
    }
    return [f for f in files if not any(p in f.parts for p in skip_parts)]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("links", "routers", "legal"), default="links")
    parser.add_argument("--all", action="store_true", help="run all checks")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    root = Path.cwd()
    problems: list[str] = []
    modes = ("links", "routers", "legal") if args.all else (args.mode,)

    for mode in modes:
        if mode == "links":
            problems += check_links(root, discover_md_files(root))
        elif mode == "routers":
            problems += check_routers(root)
        else:  # mode == "legal" (choices ограничены argparse)
            problems += check_legal(root)

    if problems:
        if not args.quiet:
            for p in problems:
                print(p, file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"docs-consistency {','.join(modes)}: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
