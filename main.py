"""
GB Text Extraction Framework
Универсальный фреймворк для извлечения текста из Game Boy ROM с поддержкой плагинов
"""

import argparse
import json
from pathlib import Path
from core.extractor import TextExtractor
from core.plugin_manager import PluginManager


def load_plugins_from_dir(plugin_dir: str) -> list:
    """Загрузка конфигурационных плагинов из каталога"""
    plugins = []
    for file in Path(plugin_dir).glob('*.json'):
        with open(file) as f:
            config = json.load(f)
            plugins.append(config)
    return plugins


def main():
    parser = argparse.ArgumentParser(description='Game Boy Text Extractor')
    parser.add_argument('rom', help='Путь к ROM-файлу')
    parser.add_argument('--output', default='text', choices=['text', 'json', 'csv'],
                        help='Формат вывода')
    parser.add_argument('--plugin-dir', default='plugins',
                        help='Каталог с конфигурационными плагинами')
    parser.add_argument('--gui', action='store_true', help='Запустить графический интерфейс')
    args = parser.parse_args()

    if args.gui:
        # Запуск GUI версии
        try:
            from gui.main_window import run_gui
            run_gui(args.rom, args.plugin_dir)
        except ImportError:
            print("Ошибка: GUI не установлен. Установите зависимости или запустите без --gui")
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
                    print(f"0x{msg['offset']:04X}: {msg['text']}")

        elif args.output == 'json':
            print(json.dumps(results, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Ошибка: {str(e)}")
        print("Подсказка: Попробуйте добавить конфигурацию для этой игры в папку plugins/")


if __name__ == "__main__":
    main()