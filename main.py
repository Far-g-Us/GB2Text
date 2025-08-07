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

import argparse
import json
from pathlib import Path
from core.injector import TextInjector
from core.plugin_manager import PluginManager


def load_plugins_from_dir(plugin_dir: str) -> list:
    """Загрузка конфигурационных плагинов из каталога"""
    plugins = []
    for file in Path(plugin_dir).glob('*.json'):
        with open(file) as f:
            config = json.load(f)
            plugins.append(config)
    return plugins

def get_version():
    try:
        with open('VERSION', 'r') as f:
            return f.read().strip()
    except:
        return "1.0.0"

def main():
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

    if args.gui:
        try:
            from gui.main_window import run_gui
            run_gui(args.rom, args.plugin_dir, lang="en")
            return
        except ImportError as e:
            print(f"Ошибка: GUI не установлен. Установите зависимости или запустите без --gui: {str(e)}")
        return

    try:
        from core.plugin_manager import get_safe_plugin_manager
        from core.extractor import TextExtractor

        plugin_manager = get_safe_plugin_manager(args.plugin_dir)
        extractor = TextExtractor(args.rom, plugin_manager)
        results = extractor.extract()

        # Вывод результатов
        if args.output == 'text':
            for seg_name, messages in results.items():
                print(f"\n== {seg_name.upper()} ==")
                for msg in messages:
                    print(f"0x{msg['offset']:04X}: {msg['text']}")

        elif args.output == 'json':
            import json
            print(json.dumps(results, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Ошибка: {str(e)}")
        print("Подсказка: Вы можете создать свою конфигурацию с помощью --auto-config")

    if args.version:
        print(f"GB Text Extraction Framework v{get_version()}")
        return

    if args.inject:
        if not args.translations or not args.output_rom:
            print("Для внедрения текста необходимы параметры --translations и --output-rom")
            return

        try:
            # Загружаем переводы
            with open(args.translations, 'r', encoding='utf-8') as f:
                translations = json.load(f)

            # Создаем инжектор
            injector = TextInjector(args.rom)

            # Внедряем переводы
            for segment_name, entries in translations.items():
                texts = [entry['translation'] for entry in entries]
                injector.inject_segment(segment_name, texts, injector.plugin)

            # Сохраняем результат
            injector.save(args.output_rom)
            print(f"Текст успешно внедрен. Новый ROM сохранен в {args.output_rom}")

        except Exception as e:
            print(f"Ошибка при внедрении текста: {str(e)}")
        return

    # Расширение менеджера плагинов конфигурационными плагинами
    plugin_manager = PluginManager(args.plugin_dir)

    try:
        extractor = TextExtractor(args.rom)
        results = extractor.extract()

        # Вывод результатов
        if args.output == 'text':
            for seg_name, messages in results.items():
                print(f"\n== {seg_name.upper()} ==")
                for msg in messages:
                    print(f"Offset: 0x{msg['offset']:04X}")
                    print(f"{msg['text']}\n")

        elif args.output == 'json':
            print(json.dumps(results, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Ошибка: {str(e)}")
        print("Подсказка: Попробуйте добавить конфигурацию для этой игры в папку plugins/")

if __name__ == "__main__":
    main()