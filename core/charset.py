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
from pathlib import Path
from typing import Dict

logger = logging.getLogger('gb2text.charset')


def load_charset(name: str) -> Dict[int, str]:
    """Загружает таблицу символов по имени (en, ru, ja)."""
    charset_file = Path(__file__).parent.parent / "locales" / name / "charset.json"
    if not charset_file.exists():
        logger.error(f"Charset file not found: {charset_file}")
        raise FileNotFoundError(f"Charset not found: {charset_file}")
    
    logger.info(f"Loading charset from: {charset_file}")
    with open(charset_file, "r", encoding="utf-8") as f:
        charset = {int(k, 16): v for k, v in json.load(f).items()}
    
    logger.debug(f"Loaded {len(charset)} characters for language: {name}")
    return charset