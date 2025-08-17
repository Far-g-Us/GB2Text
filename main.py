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
GB Text Extraction Framework
Универсальный фреймворк для извлечения текста из Game Boy ROM с поддержкой плагинов
"""

import argparse, json, logging, sys, os
from pathlib import Path
from core.injector import TextInjector

logger = logging.getLogger('gb2text')
logger.debug("=== НАЧАЛО ИНИЦИАЛИЗАЦИИ ===")
logger.debug(f"sys.frozen: {getattr(sys, 'frozen', False)}")
logger.debug(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")

# Проверяем пути
base_path = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS

logger.debug(f"Базовый путь: {base_path}")
logger.debug(f"Содержимое базового пути: {os.listdir(base_path)}")

# Проверяем наличие папки locales
locales_path = os.path.join(base_path, 'locales')
logger.debug(f"Путь к locales: {locales_path}")
logger.debug(f"Папка locales существует: {os.path.exists(locales_path)}")

if not os.path.exists(locales_path):
    # Попробуем найти в родительской директории
    parent_path = os.path.dirname(base_path)
    locales_path = os.path.join(parent_path, 'locales')
    logger.debug(f"Попробуем путь к locales в родительской директории: {locales_path}")
    logger.debug(f"Папка locales существует: {os.path.exists(locales_path)}")

    if not os.path.exists(locales_path):
        logger.error("Папка locales не найдена! Используем встроенные переводы.")


def load_plugins_from_dir(plugin_dir: str) -> list:
    """Загрузка конфигурационных плагинов из каталога"""
    plugins = []
    for file in Path(plugin_dir).glob('*.json'):
        with open(file) as f:
            config = json.load(f)
            plugins.append(config)
    return plugins


def get_resource_path(relative_path):
    """Получает абсолютный путь к ресурсу, работает как в dev режиме, так и в exe"""
    try:
        # PyInstaller создает временную папку и сохраняет путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_version():
    """Возвращает версию приложения"""
    try:
        version_path = get_resource_path('VERSION')
        with open(version_path, 'r') as f:
            return f.read().strip()
    except:
        return "1.0.0"


def main():
    logging.basicConfig(
        level=logging.DEBUG,  # Изменено с INFO на DEBUG для более детального лога
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='gb2text.log',
        filemode='w'  # 'w' перезаписывает файл при каждом запуске, 'a' дописывает
    )
    # Добавим вывод в консоль для отладки
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

    logger = logging.getLogger('gb2text')
    logger.info("Запуск GB Text Extraction Framework")
    logger.debug("Запуск в режиме отладки")

    parser = argparse.ArgumentParser(description='Game Boy Text Extractor')
    parser.add_argument('rom', nargs='?', help='Путь к ROM-файлу')
    parser.add_argument('--output', default='text', choices=['text', 'json', 'csv'],
                        help='Формат вывода')
    parser.add_argument('--plugin-dir', default='plugins',
                        help='Каталог с конфигурационными плагинами')
    parser.add_argument('--gui', action='store_true', help='Запустить графический интерфейс')
    parser.add_argument('--version', action='store_true', help='Показать версию')
    parser.add_argument('--verbose', action='store_true', help='Подробный вывод')
    parser.add_argument('--inject', action='store_true', help='Внедрить текст обратно в ROM')
    parser.add_argument('--translations', help='Файл с переводами')
    parser.add_argument('--output-rom', help='Выходной файл ROM')
    parser.add_argument('--lang', default='en', choices=['en', 'ru', 'ja'],
                        help='Язык интерфейса')
    args = parser.parse_args()

    if args.version:
        print(f"GB Text Extraction Framework v{get_version()}")
        return

    if not args.rom and not args.inject and not args.version:
        args.gui = True

    if args.gui:
        try:
            from gui.main_window import run_gui
            run_gui(args.rom, get_resource_path(args.plugin_dir), lang=args.lang)
            return
        except ImportError as e:
            print(f"Ошибка: GUI не установлен. Установите зависимости или запустите без --gui: {str(e)}")
        return

    if not args.rom:
        print("Ошибка: Необходимо указать путь к ROM-файлу")
        print("Подсказка: Вы можете создать свою конфигурацию с помощью --auto-config")
        return

    if args.inject:
        if not args.translations or not args.output_rom:
            print("Для внедрения текста необходимы параметры --translations и --output-rom")
            return

        try:
            # Загружаем переводы
            with open(args.translations, 'r', encoding='utf-8') as f:
                translations = json.load(f)

            from core.plugin_manager import get_safe_plugin_manager
            plugin_manager = get_safe_plugin_manager(get_resource_path(args.plugin_dir))

            # Создаем инжектор
            injector = TextInjector(args.rom, plugin_manager)

            # Внедряем переводы
            for segment_name, entries in translations.items():
                texts = [entry['translation'] for entry in entries]
                injector.inject_segment(segment_name, texts, plugin_manager.get_plugin(args.rom))

            # Сохраняем результат
            injector.save(args.output_rom)
            print(f"Текст успешно внедрен. Новый ROM сохранен в {args.output_rom}")

        except Exception as e:
            print(f"Ошибка при внедрении текста: {str(e)}")
            return

    try:
        from core.plugin_manager import get_safe_plugin_manager
        from core.extractor import TextExtractor

        plugin_manager = get_safe_plugin_manager(get_resource_path(args.plugin_dir))
        extractor = TextExtractor(args.rom, plugin_manager)
        results = extractor.extract()

        # Вывод результатов
        if args.output == 'text':
            for seg_name, messages in results.items():
                print(f"\n== {seg_name.upper()} ==")
                for msg in messages:
                    print(f"0x{msg['offset']:04X}: {msg['text']}")

        elif args.output == 'json':
            print(json.dumps(results, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Ошибка: {str(e)}")
        print("Подсказка: Попробуйте добавить конфигурацию для этой игры в папку plugins/")

if __name__ == "__main__":
    main()