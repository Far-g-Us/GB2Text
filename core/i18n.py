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
Модуль для интернационализации приложения
"""

import json, os, sys, logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger('gb2text.i18n')


class I18N:
    """Система интернационализации для приложения"""

    def __init__(self, default_lang: str = "en"):
        self.current_lang = default_lang
        self.translations: Dict[str, Dict[str, str]] = {}
        self._load_translations()

        # # Загружаем переводы
        # self.load_translations(default_lang)

    def _get_resource_path(self, relative_path: str) -> str:
        """Получает правильный путь к ресурсу для exe и обычного режима"""
        try:
            # PyInstaller создает временную папку и сохраняет путь в _MEIPASS
            base_path = sys._MEIPASS
        except AttributeError:
            # Обычный режим - используем текущую директорию
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def _load_translations(self):
        """Загружает файлы переводов из папки locales"""
        try:
            # Использование _get_resource_path для правильного пути к locales в exe
            locales_dir = Path(self._get_resource_path("locales"))
            logger.debug(f"Ищем папку locales по пути: {locales_dir}")
            logger.debug(f"Папка существует: {locales_dir.exists()}")

            if not locales_dir.exists():
                logger.warning("Папка locales не найдена, используются встроенные переводы")
                self._create_default_translations()
                return

            logger.debug(f"Файлы в папке locales: {list(locales_dir.glob('*.json'))}")

            # Загружаем все доступные языки
            for lang_file in locales_dir.glob("*.json"):
                lang_code = lang_file.stem
                try:
                    with open(lang_file, 'r', encoding='utf-8') as f:
                        self.translations[lang_code] = json.load(f)
                    logger.info(f"Загружен перевод: {lang_code}")
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON для языка {lang_code}: {e}")
                except OSError as e:
                    logger.error(f"Ошибка чтения файла перевода {lang_code}: {e}")

            # Если переводы не загрузились, создаем базовые
            if not self.translations:
                logger.warning("Не удалось загрузить переводы, используются встроенные")
                self._create_default_translations()

        except PermissionError as e:
            logger.error(f"Нет доступа к папке locales: {e}")
            self._create_default_translations()
        except OSError as e:
            logger.error(f"Ошибка доступа к файловой системе: {e}")
            self._create_default_translations()
        except RuntimeError as e:
            logger.error(f"Ошибка инициализации i18n: {e}")
            self._create_default_translations()

    def _create_default_translations(self):
        """Создает базовые переводы"""
        self.translations = {
            "en": {
                "app.title": "GB Text Extractor & Translator",
                "tab.extract": "Text Extraction",
                "tab.edit": "Text Editing",
                "tab.settings": "Settings",
                "rom.file": "ROM file:",
                "browse": "Browse",
                "extract.text": "Extract Text",
                "game.info": "Game Information",
                "game.title": "Title",
                "system": "System",
                "cartridge.type": "Cartridge Type",
                "rom.size": "ROM Size",
                "supported.plugin": "Supported Plugin",
                "text.segments": "Text Segments:",
                "segment.content": "Segment Content:",
                "export.json": "Export to JSON",
                "export.txt": "Export to TXT",
                "status.loading": "Loading...",
                "original.text": "Original Text",
                "translated.text": "Translation",
                "prev.entry": "← Previous",
                "next.entry": "Next →",
                "save.translation": "Save Translation",
                "inject.translation": "Inject into ROM",
                "entry": "Entry: {current} of {total}",
                "display.error": "Failed to display entry: {error}",
                "settings.localization": "Localization Settings",
                "target.language": "Target Language:",
                "encoding.type": "Encoding Type:",
                "auto.detect": "Auto-detection",
                "english": "English",
                "japanese": "Japanese",
                "russian": "Russian",
                "save.settings": "Save Settings",
                "legal.warning": "This tool must be used ONLY with ROM files that legally belong to you. Do not use it with illegal copies of games.",
                "create.config": "Create Configuration",
                "apply.encoding": "Apply Encoding",
                "guide.tab": "Guide",
                "load.template": "Load Template",
                "save.guide": "Save Guide",
                "apply.guide": "Apply to Extraction",
                "status.ready": "Ready",
                "warning.title": "Warning",
                "ui.language": "UI Language",
                "tab.about": "About",
                "about.version": "Version: {version}",
                "about.description": "A universal framework for extracting and translating text from Game Boy, Game Boy Color, and Game Boy Advance ROM files with plugin support.",
                "about.legal.title": "Legal Information",
                "about.legal.text": "This tool must be used ONLY with ROM files that legally belong to you. Do not use it with illegal copies of games.\n\nThis project does NOT contain or distribute any ROM files or copyrighted materials.",
                "about.links": "Links:",
                "about.github": "GitHub Repository",
                "diagnostics.tab": "Diagnostics",
                "cancel": "Cancel",
                "confirm.title": "Confirm",
                "confirm.exit": "Are you sure you want to exit?",
                "legal.warning": "This tool must be used ONLY with ROM files that legally belong to you. Do not use it with illegal copies of games.\n\nThis project does NOT contain or distribute any ROM files or copyrighted materials.",
                "file.select.rom": "Please select a ROM file first",
                "rom.loaded": "ROM is loaded",
                "config.created": "Configuration created and saved to:\n{path}\n\nYou can now edit it for better text extraction.",
                "settings.saved": "Settings saved",
                "warning.no.segment": "First load a text segment",
                "success.title": "Success",
                "copy.original": "Copy Original",
                "paste.translation": "Paste Translation",
                "text.copied": "Original text copied to clipboard",
                "original.copied": "Original text copied to clipboard",
                "translation.pasted": "Translation pasted from clipboard",
                "clipboard.empty": "Clipboard is empty",
                "info.title": "Information",
                "segments.found": "Found text segments:",
                "segments.limited": "Limited processing to",
                "processing.segment": "Processing segment",
                "plugin.searching": "Searching for appropriate plugin...",
                "cancel": "Cancel",
                "extraction.canceled": "Extraction canceled",
                "plugin.searching": "Searching for appropriate plugin...",
                "checking.plugin": "Checking plugin",
                "plugin.found": "Found plugin",
                "using.default.gb": "Using GenericGBPlugin by default",
                "using.default.gbc": "Using GenericGBCPlugin by default",
                "using.default.gba": "Using GenericGBAPlugin by default",
                "select.rom": "Please select a ROM file first",
                "text.extracted": "Text extracted",
                "extraction.success": "Text extracted successfully",
                "extraction.error": "Failed to extract text: {error}",
                "status.error": "Error",
                "export.txt.success": "Results successfully saved to TXT",
                "export.json.success": "Results successfully saved to JSON",
                "file.export.json": "",
                "extract.text.first": "Please extract text first",
                "segment.not.found": "Selected segment not found in extracted results",
                "segment.load.error": "Failed to load segment: {error}",
                "segment.loaded": "Segment loaded successfully",
                "page": "Page:",
                "of": "of",
                "go": "Go",
                "entry": "Entry",
                "invalid.page": "Invalid page number. Please enter a number between 1 and {total}.",
                "prev.segment": "← Previous Segment",
                "next.segment": "Next Segment →",
                "segment": "Segment: {current} of {total}",
                "text.extracting": "Extracting text...",
                "diagnostics.running": "Running...",
                "diagnostics.completed": "Completed",
                "diagnostics.start": "Run Diagnostics",
                "save.log": "Save Log"
            },
            "ru": {
                "app.title": "GB Text Extractor & Translator",
                "tab.extract": "Извлечение текста",
                "tab.edit": "Редактирование текста",
                "tab.settings": "Настройки",
                "rom.file": "ROM файл:",
                "browse": "Обзор",
                "extract.text": "Извлечь текст",
                "game.info": "Информация об игре",
                "game.title": "Название",
                "system": "Система",
                "cartridge.type": "Тип картриджа",
                "rom.size": "Размер ROM",
                "supported.plugin": "Поддерживаемый плагин",
                "text.segments": "Текстовые сегменты:",
                "segment.content": "Содержимое сегмента:",
                "export.json": "Экспорт в JSON",
                "export.txt": "Экспорт в TXT",
                "status.loading": "Загрузка...",
                "original.text": "Оригинальный текст",
                "translated.text": "Перевод",
                "prev.entry": "← Предыдущий",
                "next.entry": "Следующий →",
                "save.translation": "Сохранить перевод",
                "inject.translation": "Внедрить в ROM",
                "entry": "Запись: {current} из {total}",
                "display.error": "Не удалось отобразить запись: {error}",
                "settings.localization": "Настройки локализации",
                "target.language": "Целевой язык:",
                "encoding.type": "Тип кодировки:",
                "auto.detect": "Автоопределение",
                "english": "Английский",
                "japanese": "Японский",
                "russian": "Русский",
                "save.settings": "Сохранить настройки",
                "settings.saved": "Настройки сохранены",
                "legal.warning": "Этот инструмент должен использоваться ТОЛЬКО с ROM-файлами, законно принадлежащими вам. Не используйте его для нелегальных копий игр.",
                "create.config": "Создать конфигурацию",
                "apply.encoding": "Применить кодировку",
                "guide.tab": "Руководство",
                "load.template": "Загрузить шаблон",
                "save.guide": "Сохранить руководство",
                "apply.guide": "Применить к извлечению",
                "legal.warning": "Этот инструмент должен использоваться ТОЛЬКО с ROM-файлами, законно принадлежащими вам. Не используйте его для нелегальных копий игр.\n\nЭтот проект НЕ содержит и НЕ распространяет никакие ROM-файлы или защищенные авторским правом материалы.",
                "status.ready": "Готов",
                "warning.extract.first": "Сначала извлеките текст",
                "warning.no.translation": "Перевод не может быть пустым",
                "warning.no.segment": "Сначала загрузите текстовый сегмент",
                "file.browse": "Обзор...",
                "success.title": "Успех",
                "error.title": "Ошибка",
                "warning.title": "Предупреждение",
                "confirm.title": "Подтверждение",
                "confirm.exit": "Вы действительно хотите выйти?",
                "ui.language": "Язык интерфейса",
                "tab.about": "О программе",
                "about.version": "Версия: {version}",
                "about.description": "Универсальный фреймворк для извлечения и перевода текста из ROM-файлов Game Boy, Game Boy Color и Game Boy Advance с поддержкой плагинов.",
                "about.legal.title": "Юридическая информация",
                "about.legal.text": "Этот инструмент должен использоваться ТОЛЬКО с ROM-файлами, законно принадлежащими вам. Не используйте его для нелегальных копий игр.\n\nЭтот проект НЕ содержит и НЕ распространяет никакие ROM-файлы или защищенные авторским правом материалы.",
                "about.links": "Ссылки:",
                "about.github": "Репозиторий GitHub",
                "diagnostics.tab": "Диагностика",
                "cancel": "Отмена",
                "file.select.rom": "Сначала выберите ROM-файл",
                "rom.loaded": "ROM загружен",
                "config.created": "Конфигурация создана и сохранена в:\n{path}\n\nТеперь вы можете отредактировать её для лучшего извлечения текста.",
                "settings.saved": "Настройки сохранены",
                "warning.no.segment": "Сначала загрузите текстовый сегмент",
                "success.title": "Успех",
                "copy.original": "Копировать оригинал",
                "paste.translation": "Вставить перевод",
                "text.copied": "Оригинальный текст скопирован в буфер обмена",
                "original.copied": "Оригинальный текст скопирован в буфер обмена",
                "translation.pasted": "Перевод вставлен из буфера обмена",
                "clipboard.empty": "Буфер обмена пуст",
                "info.title": "Информация",
                "segments.found": "Найдено текстовых сегментов:",
                "segments.limited": "Ограничено обработкой до",
                "processing.segment": "Обработка сегмента",
                "plugin.searching": "Поиск подходящего плагина...",
                "cancel": "Отмена",
                "extraction.canceled": "Извлечение отменено",
                "plugin.searching": "Поиск подходящего плагина...",
                "checking.plugin": "Проверка плагина",
                "plugin.found": "Плагин найден",
                "using.default.gb": "Используется GenericGBPlugin по умолчанию",
                "using.default.gbc": "Используется GenericGBCPlugin по умолчанию",
                "using.default.gba": "Используется GenericGBAPlugin по умолчанию",
                "select.rom": "Сначала выберите ROM-файл",
                "text.extracted": "Текст извлечен",
                "extraction.success": "Текст успешно извлечен",
                "extraction.error": "Не удалось извлечь текст: {error}",
                "status.error": "Ошибка",
                "export.txt.success": "Результаты успешно сохранены в TXT",
                "export.json.success": "Результаты успешно сохранены в JSON",
                "file.export.json": "",
                "extract.text.first": "Сначала извлеките текст",
                "segment.not.found": "Выбранный сегмент не найден в извлеченных результатах",
                "segment.load.error": "Не удалось загрузить сегмент: {error}",
                "segment.loaded": "Сегмент успешно загружен",
                "page": "Страница:",
                "of": "из",
                "go": "Перейти",
                "entry": "Запись",
                "invalid.page": "Неверный номер страницы. Пожалуйста, введите число от 1 до {total}.",
                "prev.segment": "← Предыдущий сегмент",
                "next.segment": "Следующий сегмент →",
                "segment": "Сегмент: {current} из {total}",
                "text.extracting": "Извлечение текста...",
                "diagnostics.running": "Выполняется...",
                "diagnostics.completed": "Завершено",
                "diagnostics.start": "Запустить диагностику",
                "save.log": "Сохранить лог"
            },
            "ja": {
                "app.title": "GB テキスト抽出・翻訳ツール",
                "tab.extract": "テキスト抽出",
                "tab.edit": "テキスト編集",
                "tab.settings": "設定",
                "rom.file": "ROMファイル:",
                "browse": "参照",
                "extract.text": "テキストを抽出",
                "game.info": "ゲーム情報",
                "game.title": "タイトル",
                "system": "システム",
                "cartridge.type": "カートリッジタイプ",
                "rom.size": "ROMサイズ",
                "supported.plugin": "対応プラグイン",
                "text.segments": "テキストセグメント:",
                "segment.content": "セグメント内容:",
                "export.json": "JSONとしてエクスポート",
                "export.txt": "TXTとしてエクスポート",
                "original.text": "原文",
                "translated.text": "翻訳文",
                "prev.entry": "← 前へ",
                "next.entry": "次へ →",
                "save.translation": "翻訳を保存",
                "inject.translation": "ROMに書き込み",
                "entry": "エントリ: {total}中{current}",
                "display.error": "エントリの表示に失敗しました: {error}",
                "settings.localization": "ローカライズ設定",
                "target.language": "対象言語:",
                "encoding.type": "エンコーディング形式:",
                "auto.detect": "自動検出",
                "english": "英語",
                "japanese": "日本語",
                "russian": "ロシア語",
                "save.settings": "設定を保存",
                "legal.warning": "このツールは、法的に所有しているROMファイルでのみ使用してください。違法なゲームコピーには使用しないでください。",
                "create.config": "設定ファイルを作成",
                "apply.encoding": "エンコーディングを適用",
                "guide.tab": "ガイド",
                "load.template": "テンプレートを読み込む",
                "save.guide": "ガイドを保存",
                "apply.guide": "抽出に適用",
                "status.ready": "準備完了",
                "warning.title": "警告",
                "ui.language": "UI言語",
                "tab.about": "について",
                "about.version": "バージョン: {version}",
                "about.description": "Game Boy、Game Boy Color、Game Boy AdvanceのROMファイルからテキストを抽出・翻訳するためのプラグイン対応ユニバーサルフレームワーク。",
                "about.legal.title": "法的情報",
                "about.legal.text": "このツールは、法的に所有しているROMファイルでのみ使用してください。違法なゲームコピーには使用しないでください。\nこのプロジェクトにはROMファイルや著作権で保護された素材は一切含まれていません。",
                "about.links": "リンク:",
                "about.github": "GitHubリポジトリ",
                "diagnostics.tab": "診断",
                "cancel": "キャンセル",
                "confirm.title": "確認",
                "confirm.exit": "本当に終了しますか？",
                "legal.warning": "このツールは、法的に所有しているROMファイルでのみ使用してください。違法なゲームコピーには使用しないでください。\nこのプロジェクトにはROMファイルや著作権で保護された素材は一切含まれていません。",
                "file.select.rom": "最初にROMファイルを選択してください",
                "rom.loaded": "ROMが読み込まれました",
                "config.created": "設定ファイルが作成され、以下の場所に保存されました:\n{path}\nより良いテキスト抽出のために編集できます。",
                "settings.saved": "設定を保存しました",
                "warning.no.segment": "まずテキストセグメントを読み込んでください",
                "success.title": "成功",
                "copy.original": "原文をコピー",
                "paste.translation": "翻訳を貼り付け",
                "text.copied": "原文をクリップボードにコピーしました",
                "original.copied": "原文をクリップボードにコピーしました",
                "translation.pasted": "翻訳をクリップボードから貼り付けました",
                "clipboard.empty": "クリップボードが空です",
                "info.title": "情報",
                "segments.found": "見つかったテキストセグメント:",
                "segments.limited": "処理を制限:",
                "processing.segment": "セグメントを処理中",
                "plugin.searching": "適切なプラグインを検索中...",
                "cancel": "キャンセル",
                "extraction.canceled": "抽出がキャンセルされました",
                "plugin.searching": "適切なプラグインを検索中...",
                "checking.plugin": "プラグインを確認中",
                "plugin.found": "プラグインが見つかりました",
                "using.default.gb": "デフォルトで GenericGBPlugin を使用",
                "using.default.gbc": "デフォルトで GenericGBCPlugin を使用",
                "using.default.gba": "デフォルトで GenericGBAPlugin を使用",
                "select.rom": "最初にROMファイルを選択してください",
                "text.extracted": "テキストを抽出しました",
                "extraction.success": "テキストの抽出に成功しました",
                "extraction.error": "テキストの抽出に失敗しました: {error}",
                "status.error": "エラー",
                "export.txt.success": "結果をTXTファイルに正常に保存しました",
                "export.json.success": "結果が正常にJSONに保存されました",
                "file.export.json": "",
                "extract.text.first": "最初にテキストを抽出してください",
                "segment.not.found": "選択したセグメントは抽出結果にありません",
                "segment.load.error": "セグメントの読み込みに失敗しました: {error}",
                "segment.loaded": "セグメントを正常に読み込みました",
                "page": "ページ:",
                "of": "/",
                "go": "移動",
                "entry": "エントリ",
                "invalid.page": "無効なページ番号です。1 から {total} の間の数字を入力してください。",
                "prev.segment": "← 前のセグメント",
                "next.segment": "次のセグメント →",
                "segment": "セグメント: {total}中{current}",
                "text.extracting": "テキストを抽出中...",
                "diagnostics.running": "実行中...",
                "diagnostics.completed": "完了",
                "diagnostics.start": "診断を実行",
                "save.log": "ログを保存"
            }
        }

    def t(self, key: str, **kwargs) -> str:
        """Получает перевод для ключа"""
        try:
            # Пытаемся получить перевод для текущего языка
            if self.current_lang in self.translations:
                translation = self.translations[self.current_lang].get(key)
                if translation:
                    return translation.format(**kwargs) if kwargs else translation

            # Fallback на английский
            if "en" in self.translations:
                translation = self.translations["en"].get(key)
                if translation:
                    return translation.format(**kwargs) if kwargs else translation

            # Если перевод не найден, возвращаем ключ
            return key

        except Exception as e:
            print(f"Ошибка перевода для ключа '{key}': {e}")
            return key

    def get_available_languages(self) -> Dict[str, str]:
        """Возвращает доступные языки в формате код: название"""
        return {
            "en": "English",
            "ru": "Русский",
            "ja": "日本語"
        }

    def change_language(self, lang: str):
        """Меняет текущий язык"""
        if lang in self.translations:
            self.current_lang = lang
            print(f"Язык изменен на: {lang}")
        else:
            print(f"Язык '{lang}' не найден")