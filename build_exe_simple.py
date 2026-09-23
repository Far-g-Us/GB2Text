"""
Упрощенный скрипт для создания exe файла из проекта GB2Text
"""

import shutil
import site
import subprocess
import sys
from pathlib import Path


def _fix_console_encoding() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_fix_console_encoding()

# Канонический список — обязан совпадать с HIDDEN_IMPORTS в build_exe.py.
HIDDEN_IMPORTS = [
    "tkinter",
    "tkinter.ttk",
    "tkinter.scrolledtext",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "json",
    "logging",
    "pathlib",
    "collections",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "spellchecker",
    "tkinterdnd2",
    "core.extractor",
    "core.scanner",
    "core.analyzer",
    "core.decoder",
    "core.compression",
    "core.gba_support",
    "core.multi_charmap",
    "core.plugin_api",
    "core.tmx",
    "core.ml_classifier",
    "core.translation_validator",
    "core.translation_filler",
    "core.encoding",
    "core.charset",
    "core.guide",
    "core.mbc",
    "core.rom_cache",
    "core.i18n",
    "core.machine_translation",
    "core.injector",
    "core.database",
    "core.font_tiles",
    "core.font_ui",
    "core.playtest",
    "core.dte",
    "core.pointer_table",
    "core.textbox",
    "core.plugin_manager",
    "core.rom",
    "gui.main_window",
    "gui.font_tab",
    "gui.glyph_editor",
    "plugins.auto_detect",
]


def create_simple_exe():
    """Создает exe файл с минимальными настройками для надежности"""

    print("🔨 Создание exe файла для GB2Text (упрощенная версия)...")

    # Проверяем наличие PyInstaller
    try:
        import importlib.util

        if importlib.util.find_spec("PyInstaller") is None:
            raise ImportError
        print("✅ PyInstaller найден")
    except ImportError:
        print("❌ PyInstaller не найден. Устанавливаем...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller установлен")

    # Ищем папку GB2Text
    current_dir = Path(__file__).parent.parent
    gb2text_dir = None

    for path in [current_dir, current_dir.parent, current_dir.parent.parent]:
        potential_gb2text = path / "GB2Text"
        if potential_gb2text.exists() and (potential_gb2text / "main.py").exists():
            gb2text_dir = potential_gb2text
            break

    if not gb2text_dir:
        print("❌ Папка GB2Text с main.py не найдена!")
        return False

    print(f"✅ Найдена папка GB2Text: {gb2text_dir}")

    main_script = gb2text_dir / "main.py"
    dist_dir = gb2text_dir / "dist"
    build_dir = gb2text_dir / "build"

    # Очищаем предыдущие сборки
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    print("\n🔨 Создание debug версии с консолью...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",  # Используем --onedir вместо --onefile для надежности
        "--console",  # Всегда с консолью для отладки
        "--clean",
        "--name=GB2Text-Debug",
    ]
    cmd.extend(f"--hidden-import={name}" for name in HIDDEN_IMPORTS)
    spec_dir = gb2text_dir / "build" / "specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    cmd.append(f"--specpath={spec_dir}")

    version_file = gb2text_dir / "VERSION"
    if version_file.exists():
        cmd.extend([f"--add-data={version_file};."])
        print("✅ Добавлен файл VERSION")
    else:
        print(f"⚠️ Файл VERSION не найден в {version_file}")

    # Добавляем папки проекта
    required_folders = ['plugins', 'locales', 'settings', 'resources', 'gui', 'core']
    for folder in required_folders:
        folder_path = gb2text_dir / folder
        if folder_path.exists():
            if folder == 'locales':
                # Для locales используем rglob для рекурсивного поиска
                locales_files = list(folder_path.rglob('*.json'))
                for locale_file in locales_files:
                    # Сохраняем относительную структуру папок
                    rel_path = locale_file.relative_to(folder_path)
                    cmd.extend([f"--add-data={locale_file};locales/{rel_path.parent}"])
                print(f"✅ Добавлена папка: {folder} ({len(locales_files)} файлов)")
            else:
                cmd.extend([f"--add-data={folder_path};{folder}"])
            print(f"✅ Добавлена папка: {folder}")
        else:
            print(f"⚠️ Папка {folder} не найдена")

    # Добавляем иконку если есть
    icon_path = gb2text_dir / "resources" / "app_icon.ico"
    if icon_path.exists():
        cmd.append(f"--icon={icon_path}")

    # Словари pyspellchecker (ресурсы пакета)
    spellchecker_dir = Path(site.getsitepackages()[0]) / "spellchecker"
    if spellchecker_dir.exists():
        cmd.append(f"--add-data={spellchecker_dir / 'resources'};spellchecker/resources")
        print("✅ Добавлены словари spellchecker")

    cmd.append(str(main_script))

    print(f"🚀 Команда: {' '.join(str(x) for x in cmd)}")

    try:
        result = subprocess.run(cmd, cwd=gb2text_dir, capture_output=True, text=True)

        if result.returncode == 0:
            exe_path = dist_dir / "GB2Text-Debug" / "GB2Text-Debug.exe"
            if exe_path.exists():
                print(f"✅ Debug версия создана: {exe_path}")
                print(f"📁 Размер: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")

                bat_content = f'''@echo off
echo Запуск GB2Text Debug версии...
echo Если возникнут ошибки, они будут показаны в этом окне
echo.
"{exe_path}"
echo.
echo Программа завершена. Нажмите любую клавишу для закрытия...
pause > nul
'''
                bat_path = dist_dir / "Запуск GB2Text.bat"
                with open(bat_path, 'w', encoding='cp1251') as f:
                    f.write(bat_content)
                print(f"✅ Создан bat файл для запуска: {bat_path}")

                return True
            else:
                print("❌ Exe файл не найден после сборки")
                return False
        else:
            print("❌ Ошибка сборки:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Исключение: {e}")
        return False

if __name__ == "__main__":
    print("GB2Text - Упрощенная сборка exe")
    print("=" * 40)

    success = create_simple_exe()

    if success:
        print("\n🎉 Debug exe создан успешно!")
        print("📁 Найти можно в папке dist/GB2Text-Debug/")
        print("🚀 Запустите через bat файл или напрямую exe")
        print("\n💡 Если exe не работает:")
        print("- Запустите через bat файл - он покажет ошибки")
        print("- Консоль не закроется автоматически")
        print("- Все ошибки будут видны в окне")
    else:
        print("\n❌ Не удалось создать exe")
