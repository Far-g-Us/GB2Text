"""
Скрипт для создания exe файла из проекта GB2Text
"""

import os
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

# Единый канонический список hidden imports (CLI-команды + spec-шаблон
# + build_exe_debug.py обязаны совпадать; расхождение = риск silent death).
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
    "core.decoder",
    "core.scanner",
    "core.extractor",
    "core.injector",
    "core.compression",
    "core.gba_support",
    "core.multi_charmap",
    "core.plugin_api",
    "core.tmx",
    "core.ml_classifier",
    "core.translation_validator",
    "core.translation_filler",
    "core.analyzer",
    "core.database",
    "core.encoding",
    "core.charset",
    "core.guide",
    "core.mbc",
    "core.rom_cache",
    "core.i18n",
    "core.machine_translation",
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


def create_exe():
    """Создает exe файл используя PyInstaller"""

    print("🔨 Создание exe файла для GB2Text...")

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

    current_dir = Path(__file__).parent.parent
    gb2text_dir = None

    # Ищем папку GB2Text в текущей директории и родительских
    for path in [current_dir, current_dir.parent, current_dir.parent.parent]:
        potential_gb2text = path / "GB2Text"
        if potential_gb2text.exists() and (potential_gb2text / "main.py").exists():
            gb2text_dir = potential_gb2text
            break

    if not gb2text_dir:
        print("❌ Папка GB2Text с main.py не найдена!")
        print("🔍 Поиск проводился в:")
        for path in [current_dir, current_dir.parent, current_dir.parent.parent]:
            print(f"   - {path / 'GB2Text'}")
        return False

    print(f"✅ Найдена папка GB2Text: {gb2text_dir}")

    main_script = gb2text_dir / "main.py"
    # Каждый скрипт сборки живёт в своей папке: build_exe.py -> dist/gui,
    # build_exe_debug.py -> dist/debug. Иначе они затирали бы друг друга,
    # потому что оба чистили общий dist/ перед сборкой.
    dist_dir = gb2text_dir / "dist" / "gui"
    build_dir = gb2text_dir / "build" / "gui"

    required_folders = ['plugins', 'locales', 'settings', 'resources', 'gui', 'core']
    existing_folders = []

    for folder in required_folders:
        folder_path = gb2text_dir / folder
        if folder_path.exists():
            existing_folders.append(folder)
            print(f"✅ Найдена папка: {folder}")
        else:
            print(f"⚠️ Папка не найдена: {folder}")

    # Очищаем только свою папку: сборка другой версии не должна пропадать
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    # Здесь собирается ТОЛЬКО обычная GUI-версия, одним файлом.
    # Debug-сборку (console + numpy/scikit-learn, onedir) собирает
    # build_exe_debug.py. Держать обе версии в этом скрипте нельзя:
    # у них разный формат и разный набор зависимостей, а имя у обеих
    # `GB2Text-Debug`, поэтому один скрипт затирал бы вывод другого.
    # Разделение ответственности между двумя скриптами сборки:
    #   build_exe.py        -> GUI, onefile, БЕЗ numpy/sklearn/scipy
    #   build_exe_debug.py -> Debug, onedir, С numpy + scikit-learn
    # Исключения ниже намеренные: production-код не импортирует numpy
    # ни sklearn (`core/ml_classifier.py` импортирует их лениво, а
    # `auto_detect_segments_ml` вызывает только тесты), поэтому в GUI
    # сборке они были бы мёртвым грузом. В debug-сборке они нужны,
    # чтобы диагностировать проблему с реальным ML-окружением.
    versions = [
        {
            'name': 'GB2Text',
            'console': False,
            'description': 'финальная версия без консоли'
        }
    ]



    for version in versions:
        print(f"\n🔨 Создание {version['description']}...")

        cmd = [
            sys.executable, "-m", "PyInstaller",  # Используем Python модуль вместо прямого вызова
            "--onefile",                    # Один exe файл (портативный)
            "--clean",                      # Очистка кэша
            f"--name={version['name']}",    # Имя exe файла
        ]
        cmd.extend(f"--hidden-import={name}" for name in HIDDEN_IMPORTS)
        spec_dir = gb2text_dir / "build" / "specs"
        spec_dir.mkdir(parents=True, exist_ok=True)
        cmd.append(f"--specpath={spec_dir}")
        cmd.append(f"--distpath={dist_dir}")
        cmd.append(f"--workpath={build_dir}")
        cmd.extend([
            "--exclude-module=posix",
            "--exclude-module=pwd",
            "--exclude-module=grp",
            "--exclude-module=fcntl",
            "--exclude-module=resource",
            "--exclude-module=_posixsubprocess",
            "--exclude-module=java",
            "--exclude-module=org",
            "--exclude-module=vms_lib",
            "--exclude-module=_winreg",
            "--exclude-module=matplotlib",
            "--exclude-module=numpy",
            "--exclude-module=pandas",
            "--exclude-module=scipy",
            "--exclude-module=cv2",
        ])

        cmd.append("--windowed")

        version_file = gb2text_dir / "VERSION"
        if version_file.exists():
            cmd.extend([f"--add-data={version_file};."])
            print("✅ Добавлен файл VERSION")
        else:
            print(f"⚠️ Файл VERSION не найден в {version_file}")

        # Офлайн-каталог плагинов. core/community_registry.py ищет его в
        # _MEIPASS, и без него окно «Плагины» падает при недоступной сети.
        # Раньше файл добавлялся только в create_spec_file(), которого
        # сборка не касается, поэтому в поставку он не попадал.
        registry_file = gb2text_dir / "registry.json"
        if registry_file.exists():
            cmd.extend([f"--add-data={registry_file};."])
            print("✅ Добавлен файл registry.json")
        else:
            print(f"⚠️ Файл registry.json не найден в {registry_file}")

        for folder in existing_folders:
            folder_path = gb2text_dir / folder
            if folder == 'locales':
                locales_files = list(folder_path.rglob('*.json'))
                for locale_file in locales_files:
                    rel_path = locale_file.relative_to(gb2text_dir)
                    cmd.extend([f"--add-data={locale_file};{rel_path.parent}"])
                print(f"✅ Добавлены файлы локализации: {len(locales_files)} файлов")
            else:
                cmd.extend([f"--add-data={folder_path};{folder}"])

        spellchecker_dir = Path(site.getsitepackages()[0]) / "spellchecker"
        if spellchecker_dir.exists():
            cmd.append(f"--add-data={spellchecker_dir / 'resources'};spellchecker/resources")
            print("✅ Добавлены словари spellchecker")

        icon_path = gb2text_dir / "resources" / "app_icon.ico"
        if icon_path.exists():
            cmd.append(f"--icon={icon_path}")
            print("✅ Найдена иконка")
        else:
            print("⚠️ Иконка не найдена, используется стандартная")

        cmd.append(str(main_script))

        print(f"🚀 Запуск команды: {' '.join(str(x) for x in cmd)}")

        try:
            print(f"🔧 Рабочая директория: {gb2text_dir}")
            print(f"🔧 Команда: {' '.join(str(x) for x in cmd)}")

            result = subprocess.run(cmd, cwd=gb2text_dir, capture_output=True, text=True)

            if result.returncode == 0:
                exe_path = dist_dir / f"{version['name']}.exe"
                if exe_path.exists():
                    print(f"✅ {version['description']} создана: {exe_path}")
                    print(f"📁 Размер файла: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
                else:
                    print(f"❌ {version['description']} не найдена после сборки")
                    print(f"🔍 Содержимое папки dist: {list(dist_dir.glob('*')) if dist_dir.exists() else 'папка не существует'}")
            else:
                print(f"❌ Ошибка при создании {version['description']}:")
                print(f"Return code: {result.returncode}")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")

        except Exception as e:
            print(f"❌ Исключение при создании {version['description']}: {e}")
            print(f"🔧 Тип ошибки: {type(e).__name__}")

    return True


def create_spec_file():
    """Создает .spec файл для более тонкой настройки"""

    current_dir = Path(__file__).parent.parent
    gb2text_dir = None

    for path in [current_dir, current_dir.parent, current_dir.parent.parent]:
        potential_gb2text = path / "GB2Text"
        if potential_gb2text.exists() and (potential_gb2text / "main.py").exists():
            gb2text_dir = potential_gb2text
            break

    if not gb2text_dir:
        print("❌ Папка GB2Text не найдена для создания spec файла!")
        return

    # Проверяем наличие папки locales
    locales_path = gb2text_dir / "locales"
    if not locales_path.exists():
        print(f"❌ Папка locales не найдена по пути: {locales_path}")
        print("🔧 Создаем папку locales и базовые файлы локализации...")
        locales_path.mkdir(exist_ok=True)

        # Создаем базовые файлы локализации, если их нет
        en_path = locales_path / "en"
        ru_path = locales_path / "ru"
        ja_path = locales_path / "ja"
        en_path.mkdir(exist_ok=True)
        ru_path.mkdir(exist_ok=True)
        ja_path.mkdir(exist_ok=True)

        # Пример базового файла messages.json
        en_messages = en_path / "messages.json"
        ru_messages = ru_path / "messages.json"
        ja_messages = ja_path / "messages.json"

        if not en_messages.exists():
            with open(en_messages, 'w', encoding='utf-8') as f:
                f.write('''{
    "app.title": "GB Text Extraction Framework",
    "select.rom": "Please select a ROM file",
    "text.extracting": "Extracting text...",
    "text.extracted": "Text extracted"
    }''')

        if not ru_messages.exists():
            with open(ru_messages, 'w', encoding='utf-8') as f:
                f.write('''{
    "app.title": "GB Text Extraction Framework",
    "select.rom": "Пожалуйста, выберите ROM файл",
    "text.extracting": "Извлечение текста...",
    "text.extracted": "Текст извлечен"
    }''')

        if not ja_messages.exists():
            with open(ja_messages, 'w', encoding='utf-8') as f:
                f.write('''{
    "app.title": "GB テキスト抽出・翻訳ツール",
    "select.rom": "最初にROMファイルを選択してください",
    "text.extracting": "テキストを抽出中...",
    "text.extracted": "テキストを抽出しました"
    }''')

    # Проверяем, что папка locales действительно создана
    if not locales_path.exists():
        print(f"❌ Не удалось создать папку locales по пути: {locales_path}")
        return

    folders_to_include = []
    if (gb2text_dir / "VERSION").exists():
        folders_to_include.append("    ('VERSION', '.'),")
    # registry.json — офлайн-запасной каталог плагинов: без него в собранном
    # exe окно «Плагины» падало с ошибкой загрузки, когда сеть недоступна.
    if (gb2text_dir / "registry.json").exists():
        folders_to_include.append("    ('registry.json', '.'),")
    required_folders = ['plugins', 'locales', 'settings', 'resources', 'gui', 'core']

    for folder in required_folders:
        folder_path = gb2text_dir / folder
        if folder_path.exists():
            if folder == 'locales':
                for root, _, files in os.walk(folder_path):
                    for fname in sorted(files):
                        rel_path = os.path.relpath(Path(root) / fname, gb2text_dir)
                        rel_posix = rel_path.replace(os.sep, "/")
                        parent_posix = os.path.dirname(rel_posix) or "."
                        # Относительные POSIX-пути: spec переносим между машинами и ОС
                        folders_to_include.append(f"    ('{rel_posix}', '{parent_posix}'),")
            else:
                folders_to_include.append(f"    ('{folder}', '{folder}'),")
            print(f"✅ Найдена папка для включения: {folder}")
        else:
            print(f"⚠️ Папка не найдена: {folder}")

        # Добавляем явное включение файлов локализации
    datas_entries = "\n".join(folders_to_include)
    if not datas_entries:
        datas_entries = "    # No additional data files"

    # Единый список и для spec-шаблона (см. HIDDEN_IMPORTS выше)
    hiddenimports_spec = ",\n        ".join(f"'{name}'" for name in HIDDEN_IMPORTS)

    def render_spec(name: str, console: bool, onefile: bool) -> str:
        if onefile:
            exe_body = """    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],"""
            tail = ""
        else:
            exe_body = """    pyz,
    a.scripts,
    [],
    exclude_binaries=True,"""
            tail = f"""
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='{name}',
)
"""
        return f'''# -*- mode: python ; coding: utf-8 -*-
# Портативный spec: только относительные пути, CWD — корень проекта.
# Сгенерировано build_exe.create_spec_file; ручные правки затрутся.
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
{datas_entries}
    ],
    hiddenimports=[
        {hiddenimports_spec}
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'posix',
        'pwd',
        'grp',
        'fcntl',
        'resource',
        '_posixsubprocess',
        'java',
        'org',
        'vms_lib',
        '_winreg',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'cv2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
{exe_body}
    name='{name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console={console},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    cofile=None,
    icon='resources/app_icon.ico' if (Path('resources/app_icon.ico').exists()) else None,
    codesign_identity=None,
    entitlements_file=None,
)
{tail}'''

    # Спека описывает ровно ту сборку, которую делает этот скрипт, —
    # одну GUI-версию одним файлом. Спеки для debug здесь нет: debug
    # собирает build_exe_debug.py, у него другой формат (onedir) и
    # другой набор зависимостей.
    spec_path = gb2text_dir / 'GB2Text.spec'
    with open(spec_path, 'w', encoding='utf-8') as spec_file:
        spec_file.write(render_spec('GB2Text', False, True))

    print("✅ Создан файл GB2Text.spec для настройки сборки")

if __name__ == "__main__":
    print("GB2Text - Создание exe файла")
    print("=" * 40)

    # Создаем spec файл
    create_spec_file()

    # Создаем exe
    success = create_exe()

    if success:
        print("\n🎉 Exe файл успешно создан!")
        print("📁 Найти его можно в папке dist/")
        print("\n💡 Советы:")
        print("- Протестируйте exe на другом компьютере")
        print("- Убедитесь, что все плагины работают")
        print("- Проверьте работу с разными ROM файлами")
    else:
        print("\n❌ Не удалось создать exe файл")
        print("🔧 Попробуйте:")
        print("- Установить все зависимости: pip install -r requirements.txt")
        print("- Обновить PyInstaller: pip install --upgrade pyinstaller")
        print("- Запустить из командной строки для подробных ошибок")
