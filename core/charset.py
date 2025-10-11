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
from pathlib import Path

def load_charset(name: str):
    """Загружает таблицу символов по имени (en, ru, ja)."""
    charset_file = Path(__file__).parent.parent / "locales" / name / "charset.json"
    if not charset_file.exists():
        raise FileNotFoundError(f"Charset not found: {charset_file}")
    with open(charset_file, "r", encoding="utf-8") as f:
        return {int(k, 16): v for k, v in json.load(f).items()}