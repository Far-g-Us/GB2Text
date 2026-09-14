"""
Spell-check Russian docstrings/comments with pymorphy3 and English with pyspellchecker.

Usage:
    python scripts/check_spelling.py [--path ROOT] [--min-word N]

Scans every .py file under ROOT (default repo root, excluding .venv, .git,
build dirs, __pycache__ and htmlcov), extracts comments (via tokenize) and
docstrings (via ast), and reports words pymorphy3 (RU) / pyspellchecker (EN)
do not recognize.

Exit code 0 always; candidate words are printed to stderr. Game/ROM domain
terms are filtered via a built-in allowlist.
"""

import argparse
import ast
import io
import os
import re
import sys
import tokenize

import pymorphy3
from spellchecker import SpellChecker

RU_MORPH = pymorphy3.MorphAnalyzer()
EN_CHECKER = SpellChecker(language="en")

GAME_TERMS = {
    "gb", "gba", "gbc", "sgb", "rom", "roms", "api", "cli", "gui", "ui", "ux",
    "tmx", "xliff", "csv", "json", "xml", "txt", "tbk", "tbl", "charmap",
    "charset", "decode", "decode_", "encode", "encoder", "decoder", "extractor",
    "injector", "inserter", "pointer", "pointers", "offset", "offsets", "bank",
    "banks", "segment", "segments", "plugin", "plugins", "frame", "frames",
    "thread", "threads", "daemon", "pipeline", "hidden", "token", "tokens",
    "tm", "wram", "ram", "vram", "sram", "cpu", "lz77", "huffman", "gba_",
    "moss", "loop", "auto", "lang", "key", "keys", "flag", "flags", "byte",
    "bytes", "bit", "bits", "slot", "slots", "table", "tables", "base", "data",
    "meta", "info", "line", "lines", "file", "files", "path", "paths", "dir",
    "dirs", "log", "logs", "err", "error", "errors", "status", "state", "page",
    "pages", "mode", "modes", "type", "types", "class", "classes", "method",
    "func", "attr", "attrs", "arg", "args", "kwarg", "kwargs", "return",
    "src", "dst", "tmp", "temp", "res", "result", "ok", "true", "false",
    "bool", "int", "str", "float", "none", "self", "main", "init", "start",
    "end", "stop", "exit", "load", "save", "open", "close", "read", "write",
    "get", "set", "add", "remove", "delete", "update", "create", "find",
    "check", "verify", "validate", "apply", "render", "draw", "print", "parse",
    "scan", "search", "fill", "dump", "restore", "reset", "clean", "fetch",
    "merge", "split", "join", "sort", "filter", "build", "compile", "doc",
    "docs", "readme", "license", "todo", "fixme", "hack", "wip", "note",
    "argv", "stdin", "stdout", "stderr", "utf", "ascii", "unicode",
    "array", "dict", "tuple", "list", "vector", "buffer", "packet",
    "chunk", "block", "sector", "zone", "reserved", "padding", "checksum",
    "mc_bgb", "pyboy", "mgba", "deepl", "googletrans", "bing",
    "translator", "translation", "translations", "translate", "translated",
    "multi_charmap", "dbr_array", "dialog", "dialogue", "msg", "msgbox",
    "textbox", "subroutine", "hook", "hooks", "asm", "mnemonic", "opcode",
    "opcodes", "bytecode", "stack", "push", "pop", "call", "ret", "jp", "jr",
    "ld", "vblank", "interrupt", "irq", "dma", "dmg", "cgb", "agb", "mapping",
    "mapper", "interop", "shaper", "tokenizer", "stuff", "etc", "ex",
    "eg", "approx", "config", "configs", "preference", "settings",
    "keybind", "shortcut", "tooltip", "tooltips", "checkbox", "radio",
    "combobox", "scrolled", "notebook", "toplevel", "widget", "widgets",
    "destroing", "destroy", "destroyed", "popup", "modal", "frameless",
    "splash", "overlay", "progressbar", "scrollbar", "messagebox", "filedialog",
    "showerror", "showwarning", "showinfo", "askyesno", "askstring", "askopen",
    "asksave", "tkinter", "ttk", "tcl", "tk", "pytest", "unittest", "coverage",
    "htmlcov", "tox", "nox", "flake8", "black", "isort", "mypy", "ruff",
    "markdown", "md", "rst", "yaml", "yml", "toml", "ini", "cfg", "env",
    "venv", "pip", "conda", "poetry", "pipenv", "pyinstaller", "nuitka",
    "setup", "setup.py", "pyproject", "wheel", "egg", "sdist", "dist",
    "resources", "assets", "sprites", "tiles", "tilemap", "palette", "palettes",
    "rgba", "rgb", "oam", "mbc", "mbc1", "mbc2",
    "mbc3", "mbc5", "cart", "cartridge", "header", "headers", "footer",
    "nintendo", "pokemon", "apispeak", "entry", "entries", "source", "sources",
    "target", "targets", "domain", "domains", "escaped", "escaping", "regex",
    "regexp", "wildcard", "pattern", "patterns", "rule", "rules", "policy",
    "policies", "redact", "redaction", "sanitize", "sanitized", "select",
    "selection", "current", "prev", "next", "idx", "index",
    "indexes", "numeric", "binary", "hex", "decimal", "octal", "roundtrip",
    "roundtrip_", "round_trip", "lossless", "lossy", "manifest", "manifests",
    "schema", "schemas", "deleteatkey", "insertatkey", "literals",
    "languages", "language", "locales", "locale", "i18n", "l10n", "gettext",
    "msgid", "msgstr", "plural", "plurals", "gender", "masculine", "feminine",
    "neuter", "singular", "nominative", "genitive", "dative", "accusative",
    "instrumental", "prepositional", "russian", "english", "japanese",
    "german", "french", "spanish", "italian", "portuguese", "korean", "chinese",
    "metroid", "wario", "zelda", "golden", "ffta", "cvas", "tmc", "mlss",
    "mf", "pokered", "castlevania", "phoenix", "shining", "telefang", "sonic",
    "custom_robo", "golden_sun", "megaman", "mega", "battle_network", "advance",
    "zero", "fusion", "moons", "martial", "saint", "dialogues",
    "encounter", "encounters", "quest", "quests", "item", "items", "party",
    "inventory", "equipment", "armor", "weapon", "weapons", "shop", "shops",
    "npc", "npcs", "enemy", "enemies", "boss", "bosses", "map", "maps",
    "overworld", "dungeon", "dungeons", "village", "town", "castle", "forest",
    "cave", "caves", "tower", "towers", "bridge", "plains", "desert", "ocean",
    "island", "islands", "mountain", "mountains", "river", "lake", "sea",
    "gate", "gates", "door", "doors", "chest", "chests", "lock",
    "locks", "switch", "switches", "lever", "levers", "portal", "portals",
    "warp", "warps", "teleport", "teleports", "respawn", "respawns", "minor",
    "major", "patch", "patches", "patching", "hacks", "romhack",
    "romhacks", "waterfall", "uv", "svg", "png", "jpg", "jpeg",
    "gif", "bmp", "ico", "webp", "apng", "avif", "hdr", "css", "less", "scss",
    "html", "htm", "js", "ts", "tsx", "jsx", "vite", "webpack", "rollup",
    "esbuild", "node", "npm", "yarn", "pnpm", "deno", "bun", "rust", "cargo",
    "crab", "tokio", "serde", "clap", "tui", "host", "guest", "cgroup",
    "namespaces", "overlayfs", "squashfs", "appimage", "snap", "flatpak",
    "deb", "rpm", "pacman", "aur", "brew", "port", "ports", "pkg", "pkgs",
    "github", "git", "workflow", "workflows", "ci", "cd", "lineno",
    "profiler", "cprofile", "coveragerc", "dev", "scikit", "runtime",
    "stdlib", "syntax", "semantic", "semantics", "concise", "flatten",
    "glob", "composition", "marshal", "plist", "msi", "exe", "whl", "tar",
    "gz", "zip", "epoch", "rpc", "grpc", "websocket", "websockets", "tcp",
    "udp", "smtp", "ftp", "multi", "lzss", "seg", "addr", "eval", "metadata",
"app", "url", "uri", "noqa", "tmpl", "tuv", "pct", "trans", "repo",
    "astro", "leafgreen", "firered", "minish", "datacrystal", "https",
    "http", "com", "dbr", "bgb", "ptr", "btn", "hola", "ctx", "via",
    "menu", "mask", "team", "beta", "alpha", "final", "impl", "mod", "ids",
    "usr", "jis", "crn", "usa", "namespace",
    "rle", "gsap", "endian", "lsb", "pret", "cmd", "pre", "cwd", "param",
    "rtc", "wcag", "rec", "bpp", "subprocess", "sklearn", "pyspellchecker",
    "tkinterdnd", "meipass", "backref", "tcrf", "gbatek", "gbt",
    "autohotkey", "pymorphy", "numpy", "pygame",
}

WORD_MIN = 3


def _iter_py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in (".venv", ".git", "__pycache__", "htmlcov", "dist", "build")
        ]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def _words_from(raw_lines):
    seen = set()
    for lineno, line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        clean = stripped.lstrip("#").strip()
        for tok in _tokenize(clean):
            key = (lineno, tok)
            if key in seen:
                continue
            seen.add(key)
            yield lineno, tok


def _tokenize(text):
    cur = []
    for ch in text:
        if ch.isalpha():
            cur.append(ch)
        else:
            if cur:
                yield "".join(cur)
                cur = []
    if cur:
        yield "".join(cur)


def _camel_parts(word):
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+", word)
    return [p for p in parts if len(p) >= WORD_MIN]


def _extract_docstrings(source):
    """Вернуть (lineno, text) строковых литералов в начале тела модуля/класса/функции."""
    doc_nodes = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    strings = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, doc_nodes):
            continue
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            strings.append((first.lineno, first.value.value))
    return strings


def _extract_comments(source):
    """Вернуть (lineno, text) комментариев через tokenize — не ловит '#' внутри строк."""
    comments = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                comments.append((tok.start[0], tok.string))
    except (tokenize.TokenError, IndentationError):
        pass
    return comments


def _is_cyrillic(word):
    return all(0x0400 <= ord(c) <= 0x04FF for c in word)


def _is_hexish(word):
    if len(word) < 2:
        return False
    core = word[1:] if word.startswith("x") else word
    if len(core) < 2:
        return False
    if not all(c in "abcdefABCDEF" for c in core):
        return False
    if word.startswith("x"):
        return True
    if len(core) >= 6:
        return True
    return any(c.isdigit() for c in core)


def check_file(path, min_word) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    try:
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
    except (OSError, UnicodeDecodeError):
        return findings

    raw_lines = []
    try:
        raw_lines.extend(_extract_docstrings(source))
    except SyntaxError:
        pass
    raw_lines.extend(_extract_comments(source))

    for lineno, word in _words_from(raw_lines):
        if len(word) < min_word:
            continue
        lower = word.lower()
        if lower in GAME_TERMS or _is_hexish(word):
            continue
        if word.isascii() and word.isalpha():
            parts = _camel_parts(word)
            if len(parts) > 1 and all(
                p.lower() in GAME_TERMS or EN_CHECKER.known([p.lower()]) for p in parts
            ):
                continue
            if not EN_CHECKER.known([lower]):
                findings.append((lineno, word, "EN"))
        elif _is_cyrillic(word):
            parses = RU_MORPH.parse(word)
            if not any(p.tag.POS is not None for p in parses):
                findings.append((lineno, word, "RU"))
    return findings


def main():
    parser = argparse.ArgumentParser(description="Spell-check comments and docstrings.")
    parser.add_argument("--path", default=".", help="Root directory to scan (default: repo root).")
    parser.add_argument("--min-word", type=int, default=WORD_MIN, help="Minimum word length to check.")
    args = parser.parse_args()

    root = os.path.abspath(args.path)
    total = 0
    for pyfile in sorted(_iter_py_files(root)):
        findings = check_file(pyfile, args.min_word)
        if not findings:
            continue
        print(f"{os.path.relpath(pyfile, root)}:", file=sys.stderr)
        for lineno, word, lang in findings:
            print(f"  {lineno}: [{lang}] {word}", file=sys.stderr)
            total += 1
    print(f"\nTotal candidate words: {total}", file=sys.stderr)


if __name__ == "__main__":
    main()
