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

import json
import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger('gb2text.charset')


def _get_resource_path(relative_path: str) -> Path:
    """Получает правильный путь к ресурсу для exe и обычного режима"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return Path(base_path) / relative_path


def load_charset(name: str) -> dict[int, str]:
    """Загружает таблицу символов по имени (en, ru, ja)."""
    charset_file = _get_resource_path("locales") / name / "charset.json"
    if not charset_file.exists():
        logger.error(f"Charset file not found: {charset_file}")
        raise FileNotFoundError(f"Charset not found: {charset_file}")

    logger.info(f"Loading charset from: {charset_file}")
    with open(charset_file, encoding="utf-8") as f:
        charset = {int(k, 16): v for k, v in json.load(f).items()}

    logger.debug(f"Loaded {len(charset)} characters for language: {name}")
    return charset


def load_charmap_txt(path: str | Path) -> dict[int | tuple[int, ...], str]:
    """
    Загружает charmap в формате pret/pokeemerald (charmap.txt).

    Поддерживаемые форматы строк:
        'A'         = 0xBB
        'PKMN'      = 0x53 0x54
        PLAYER       = FD 01
        @ комментарии
        #define NAME "BYTE 0x80 0xA6;"

    Возвращает dict[int, str] где ключ — int код символа (single-byte)
    или tuple[int,...] для multi-byte, значение — строковое представление.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Charmap file not found: {path}")  # pragma: no cover

    charmap: dict[int | tuple[int, ...], str] = {}
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()

    # Regex for pret format: 'CHAR' = 0xNN [0xNN ...]  or  'CHAR' = NN [NN ...]
    pret_re = re.compile(
        r"^'([^']*)'\s*=\s*((?:[0-9A-Fa-f]{2}\s*)+)"
    )
    # Regex for #define format: #define NAME "BYTE 0xNN 0xNN;"
    define_re = re.compile(
        r'^#define\s+\w+\s+"((?:BYTE\s+0x[0-9A-Fa-f]{2}\s*)+)"',
        re.IGNORECASE,
    )
    # Regex for hex byte sequences (0xNN or bare NN)
    hex_bytes_re = re.compile(r'(?:0x)?([0-9A-Fa-f]{2})')

    for _lineno, raw_line in enumerate(lines, 1):
        line = raw_line.strip()

        # Skip empty lines and comments
        if not line or line.startswith('@') or line.startswith('//'):
            continue

        # Try pret format: 'A' = 0xBB
        m = pret_re.match(line)
        if m:
            char_str = m.group(1)
            hex_part = m.group(2)
            byte_strs = hex_bytes_re.findall(hex_part)
            byte_vals = [int(b, 16) for b in byte_strs]

            if len(byte_vals) == 1:
                charmap[byte_vals[0]] = char_str
            else:
                # Multi-byte: tuple key per docstring (no callers yet)
                charmap[tuple(byte_vals)] = char_str
            continue

        # Try bare identifier format: PLAYER = FD 01  (plain hex, no 0x prefix)
        m = re.match(r'^([A-Za-z_]\w*)\s*=\s*((?:[0-9A-Fa-f]{2}\s*)+)', line)
        if m and "'" not in line and '"' not in line:
            name = m.group(1)
            hex_part = m.group(2)
            byte_strs = re.findall(r'([0-9A-Fa-f]{2})', hex_part)
            byte_vals = [int(b, 16) for b in byte_strs]
            if len(byte_vals) == 1:
                charmap[byte_vals[0]] = name  # pragma: no cover
            else:
                charmap[tuple(byte_vals)] = f'[{name}]'
            continue

        # Try #define format: #define _A "BYTE 0x80 0xB0;"
        m = define_re.match(line)
        if m:
            hex_part = m.group(1)  # pragma: no cover
            byte_strs = hex_bytes_re.findall(hex_part)  # pragma: no cover
            byte_vals = [int(b, 16) for b in byte_strs]  # pragma: no cover

            if len(byte_vals) == 1:  # pragma: no cover
                charmap[byte_vals[0]] = chr(byte_vals[0]) if 0x20 <= byte_vals[0] <= 0x7E else f'[{byte_vals[0]:02X}]'  # pragma: no cover
            else:
                charmap[tuple(byte_vals)] = f'[{": ".join(f"{b:02X}" for b in byte_vals)}]'  # pragma: no cover
            continue  # pragma: no cover

        # Try simple hex mapping: 0xBB = 'A'  (reverse of pret)
        m = re.match(r'^(0x[0-9A-Fa-f]{2})\s*=\s*\'([^\']*)\'', line)  # pragma: no cover
        if m:  # pragma: no cover
            byte_val = int(m.group(1), 16)  # pragma: no cover
            char_str = m.group(2)  # pragma: no cover
            charmap[byte_val] = char_str  # pragma: no cover
            continue  # pragma: no cover

        # Try TBL format: HEX=CHAR (e.g., 0081=A)
        m = re.match(r'^([0-9A-Fa-f]{4})=(.+)$', line)  # pragma: no cover
        if m:  # pragma: no cover
            byte_val = int(m.group(1), 16)  # pragma: no cover
            char_str = m.group(2).strip()  # pragma: no cover
            if char_str:  # pragma: no cover
                charmap[byte_val] = char_str  # pragma: no cover
            continue  # pragma: no cover

    logger.info(f"Loaded {len(charmap)} characters from {path.name} (pret format)")  # pragma: no cover
    return charmap  # pragma: no cover
