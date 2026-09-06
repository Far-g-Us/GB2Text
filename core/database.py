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

"""
База данных с безопасной информацией о типичных структурах ROM
"""

import logging

from core.constants import GBA_ROM_BASE_ADDRESS, POINTER_SIZES, SYSTEM_GB, SYSTEM_GBA, SYSTEM_GBC

logger = logging.getLogger('gb2text.database')

# Безопасная база данных с общими паттернами
ROM_DATABASE = {
    SYSTEM_GB: {
        'text_segment_patterns': [
            {'start_min': 0x4000, 'start_max': 0x5000, 'end_min': 0x6000, 'end_max': 0x7FFF},
            {'start_min': 0x8000, 'start_max': 0x9000, 'end_min': 0xA000, 'end_max': 0xBFFF}
        ],
        'pointer_size': POINTER_SIZES[SYSTEM_GB]  # 16-битные указатели для GB
    },
    SYSTEM_GBC: {
        'text_segment_patterns': [
            {'start_min': 0x4000, 'start_max': 0x5000, 'end_min': 0x6000, 'end_max': 0x7FFF},
            {'start_min': 0x8000, 'start_max': 0x9000, 'end_min': 0xA000, 'end_max': 0xBFFF}
        ],
        'pointer_size': POINTER_SIZES[SYSTEM_GBC]  # 16-битные указатели для GBC
    },
    SYSTEM_GBA: {
        'text_segment_patterns': [
            {'start_min': GBA_ROM_BASE_ADDRESS + 0x0D0000, 'start_max': GBA_ROM_BASE_ADDRESS + 0x0E0000,
             'end_min': GBA_ROM_BASE_ADDRESS + 0x100000, 'end_max': GBA_ROM_BASE_ADDRESS + 0x120000}
        ],
        'pointer_size': POINTER_SIZES[SYSTEM_GBA]  # 32-битные указатели для GBA
    }
}

def get_segment_patterns(system: str) -> list[dict]:
    """Получает типичные паттерны текстовых сегментов для системы"""
    return ROM_DATABASE.get(system, {}).get('text_segment_patterns', [])

def get_pointer_size(system: str) -> int:
    """Получает размер указателя для системы"""
    size = ROM_DATABASE.get(system, {}).get('pointer_size', 2)
    if size is None:
        logger.warning(f"Неизвестный размер указателя для системы {system}, используем 2 по умолчанию")
        return 2
    return size


class TranslationDatabase:
    """Класс для хранения и извлечения переводов с поддержкой SQLite"""

    def __init__(self, db_path: str | None = None):
        """Инициализация базы данных переводов"""
        self.db_path = db_path
        self._cache: dict[str, str | int | list] = {}
        self._cache_enabled = False
        self._conn = None

        if db_path and db_path != ":memory:":
            import sqlite3
            self._conn = sqlite3.connect(db_path)
            self._create_tables()
        elif db_path == ":memory:":
            import sqlite3
            self._conn = sqlite3.connect(":memory:")
            self._create_tables()

    def _create_tables(self):
        """Создает таблицы SQLite"""
        if self._conn:
            cursor = self._conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_lang, target_lang, source)
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_translations_lookup
                ON translations(source_lang, target_lang, source)
            ''')
            self._conn.commit()

    def store_translation(self, source_lang: str, target_lang: str, source: str, target: str) -> bool:
        """Сохраняет перевод в базу данных"""
        key = (source_lang, target_lang, source)
        self._cache[key] = target

        if self._conn:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    'INSERT OR REPLACE INTO translations (source_lang, target_lang, source, target) VALUES (?, ?, ?, ?)',
                    (source_lang, target_lang, source, target)
                )
                self._conn.commit()
            except Exception:
                return False
        return True

    def get_translation(self, source_lang: str, target_lang: str, source: str) -> str | None:
        """Получает перевод из базы данных"""
        key = (source_lang, target_lang, source)

        if key in self._cache:
            return self._cache[key]

        if self._conn:
            cursor = self._conn.cursor()
            cursor.execute(
                'SELECT target FROM translations WHERE source_lang = ? AND target_lang = ? AND source = ?',
                (source_lang, target_lang, source)
            )
            row = cursor.fetchone()
            if row:
                self._cache[key] = row[0]
                return row[0]
        return None

    def get_translations_for_source(self, source_lang: str, target_lang: str, source: str) -> list:
        """Получает все переводы для исходного текста"""
        if self._conn:
            cursor = self._conn.cursor()
            cursor.execute(
                'SELECT target FROM translations WHERE source_lang = ? AND target_lang = ? AND source = ?',
                (source_lang, target_lang, source)
            )
            return [row[0] for row in cursor.fetchall()]

        translations = []
        for (sl, tl, s), t in self._cache.items():
            if sl == source_lang and tl == target_lang and s == source:
                translations.append(t)
        return translations

    def enable_cache(self):
        """Включает кэширование"""
        self._cache_enabled = True

    def disable_cache(self):
        """Выключает кэширование"""
        self._cache_enabled = False
        self._cache.clear()

    def store_batch(self, translations: list) -> int:
        """
        Массовая вставка переводов.
        translations: список кортежей (source_lang, target_lang, source, target)
        Возвращает количество сохранённых записей.
        """
        if not self._conn or not translations:
            return 0
        try:
            cursor = self._conn.cursor()
            cursor.executemany(
                'INSERT OR REPLACE INTO translations (source_lang, target_lang, source, target) VALUES (?, ?, ?, ?)',
                translations
            )
            self._conn.commit()
            for sl, tl, s, t in translations:
                self._cache[(sl, tl, s)] = t
            return len(translations)
        except Exception:
            return 0

    def search(self, source_lang: str, target_lang: str, query: str, limit: int = 50) -> list:
        """
        Поиск переводов по подстроке (LIKE %query%).
        Возвращает список словарей {source, target}.
        """
        if not self._conn:
            return []
        cursor = self._conn.cursor()
        cursor.execute(
            'SELECT source, target FROM translations WHERE source_lang = ? AND target_lang = ? AND source LIKE ? LIMIT ?',
            (source_lang, target_lang, f'%{query}%', limit)
        )
        return [{'source': row[0], 'target': row[1]} for row in cursor.fetchall()]

    def count(self, source_lang: str | None = None, target_lang: str | None = None) -> int:
        """Подсчёт записей с опциональной фильтрацией по языкам"""
        if not self._conn:
            return len(self._cache)
        conditions = []
        params = []
        if source_lang:
            conditions.append('source_lang = ?')
            params.append(source_lang)
        if target_lang:
            conditions.append('target_lang = ?')
            params.append(target_lang)
        where = f' WHERE {" AND ".join(conditions)}' if conditions else ''
        cursor = self._conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM translations{where}', params)
        return cursor.fetchone()[0]

    def close(self):
        """Закрывает соединение с базой данных"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __del__(self):
        self.close()
