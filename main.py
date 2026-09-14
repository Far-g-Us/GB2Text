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

Режимы запуска:
  1) Legacy (флаги):      python main.py rom.gba [--inject --translations t.json --output-rom out.gba]
  2) Agent (subcommands): python main.py {plugins,detect,extract,inject,serve} [args] [--json]
"""

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path

from core.injector import TextInjector

logger = logging.getLogger('gb2text')

# Команды агентского CLI. Если первый позиционный аргумент совпадает с одной
# из них — работаем в режиме subcommands (делегирование в api.cli), иначе —
# legacy-режим (rom-файл + флаги).
AGENT_COMMANDS = {"plugins", "detect", "extract", "inject", "serve"}

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
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_version():
    """Возвращает версию приложения"""
    try:
        version_path = get_resource_path('VERSION')
        with open(version_path) as f:
            return f.read().strip()
    except OSError:
        return "1.0.0"


def _print_extract_csv(results, out_path=None):
    """CSV-вывод extracted результатов в stdout или файл"""
    writer_holder = None if out_path is None else open(out_path, "w", newline="", encoding="utf-8")
    try:
        writer = csv.writer(sys.stdout if writer_holder is None else writer_holder)
        writer.writerow(["segment", "offset", "text"])
        for seg_name, messages in results.items():
            for msg in messages:
                writer.writerow([seg_name, msg["offset"], msg["text"]])
    finally:
        if writer_holder is not None:
            writer_holder.close()


def main(argv=None):
    args_list = list(sys.argv[1:] if argv is None else argv)

    # Агентский режим: python main.py <command> [args].
    # Логика (форматы, JSON-обёртка, коды выхода) живёт в api.cli —
    # здесь только диспетчеризация, чтобы точка входа для агентов была единой.
    if args_list and args_list[0] in AGENT_COMMANDS:
        from api.cli import main as api_main
        return api_main(args_list)

    logging.basicConfig(
        level=logging.DEBUG,  # Изменено с INFO на DEBUG для более детального лога
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='gb2text.log',
        filemode='a'  # 'w' перезаписывает файл при каждом запуске, 'a' дописывает
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

    parser = argparse.ArgumentParser(
        description='Game Boy Text Extractor',
        epilog='Агентский режим: python main.py {plugins,detect,extract,inject,serve} --json',
    )
    parser.add_argument('rom', nargs='?', help='Путь к ROM-файлу')
    parser.add_argument('--output', default='text', choices=['text', 'json', 'csv'],
                        help='Формат вывода')
    parser.add_argument('--output-file', help='Файл для вывода при --output csv (иначе stdout)')
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
    parser.add_argument('--max-segments', type=int,
                        help='Максимум сегментов при извлечении (для больших ROM)')
    args = parser.parse_args(args_list)

    if args.version:
        print(f"GB Text Extraction Framework v{get_version()}")
        return 0

    if not args.rom and not args.inject and not args.version:
        args.gui = True

    if args.gui:
        try:
            from gui.main_window import run_gui
            run_gui(args.rom, get_resource_path(args.plugin_dir), lang=args.lang)
            return 0
        except ImportError as e:
            print(f"Ошибка: GUI не установлен. Установите зависимости или запустите без --gui: {e!s}")
        return 1

    if not args.rom:
        print("Ошибка: Необходимо указать путь к ROM-файлу")
        print("Подсказка: Вы можете создать свою конфигурацию с помощью --auto-config")
        return 1

    if args.inject:
        if not args.translations or not args.output_rom:
            print("Для внедрения текста необходимы параметры --translations и --output-rom")
            return 1

        try:
            # Загружаем переводы
            with open(args.translations, encoding='utf-8') as f:
                translations = json.load(f)

            from core.plugin_manager import get_safe_plugin_manager
            plugin_manager = get_safe_plugin_manager(get_resource_path(args.plugin_dir))

            # Создаем инжектор (ВАЖНО: без plugin_manager)
            injector = TextInjector(args.rom)

            # Определяем плагин для этого ROM (ВАЖНО: по game_id и system)
            rom_game_id = injector.rom.get_game_id()
            rom_system = injector.rom.system
            plugin = plugin_manager.get_plugin(rom_game_id, rom_system, rom=injector.rom)
            if not plugin:
                raise RuntimeError(f"Не найден плагин для {rom_game_id} ({rom_system})")

            # Внедряем переводы
            for segment_name, entries in translations.items():
                if not isinstance(entries, list):
                    raise RuntimeError(
                        f"Неверный формат перевода для '{segment_name}': ожидается список записей"
                    )
                texts = []
                for i, entry in enumerate(entries):
                    if not isinstance(entry, dict) or 'translation' not in entry:
                        raise RuntimeError(
                            f"Неверный формат записи #{i} в сегменте '{segment_name}': "
                            f"ожидается dict с ключом 'translation'"
                        )
                    translation = entry['translation']
                    if not isinstance(translation, str):
                        raise RuntimeError(
                            f"Неверный тип перевода в записи #{i} сегмента '{segment_name}': "
                            f"ожидается строка, получен {type(translation).__name__}"
                        )
                    texts.append(translation)
                ok = injector.inject_segment(segment_name, texts, plugin)
                if not ok:
                    raise RuntimeError(
                        f"Не удалось внедрить сегмент '{segment_name}' "
                        f"(несовпадение количества записей, decoder=None или длина перевода)"
                    )

            # Сохраняем результат
            injector.save(args.output_rom)
            print(f"Текст успешно внедрен. Новый ROM сохранен в {args.output_rom}")
            return 0

        except Exception as e:
            print(f"Ошибка при внедрении текста: {e!s}")
            return 1

    try:
        from core.extractor import TextExtractor
        from core.plugin_manager import get_safe_plugin_manager

        plugin_manager = get_safe_plugin_manager(get_resource_path(args.plugin_dir))
        extractor = TextExtractor(args.rom, plugin_manager, max_segments=args.max_segments)
        results = extractor.extract()

        # Вывод результатов
        if args.output == 'text':
            for seg_name, messages in results.items():
                print(f"\n== {seg_name.upper()} ==")
                for msg in messages:
                    print(f"0x{msg['offset']:04X}: {msg['text']}")

        elif args.output == 'json':
            print(json.dumps(results, indent=2, ensure_ascii=False))

        elif args.output == 'csv':
            _print_extract_csv(results, args.output_file)

        return 0

    except Exception as e:
        print(f"Ошибка: {e!s}")
        print("Подсказка: Попробуйте добавить конфигурацию для этой игры в папку plugins/")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
