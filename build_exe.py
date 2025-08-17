"""
Скрипт для создания exe файла из проекта GB2Text
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def create_exe():
    """Создает exe файл используя PyInstaller"""
    
    print("🔨 Создание exe файла для GB2Text...")
    
    # Проверяем наличие PyInstaller
    try:
        import PyInstaller
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
    dist_dir = gb2text_dir / "dist"
    build_dir = gb2text_dir / "build"
    
    required_folders = ['plugins', 'locales', 'settings', 'resources', 'gui', 'core']
    existing_folders = []
    
    for folder in required_folders:
        folder_path = gb2text_dir / folder
        if folder_path.exists():
            existing_folders.append(folder)
            print(f"✅ Найдена папка: {folder}")
        else:
            print(f"⚠️ Папка не найдена: {folder}")
    
    # Очищаем предыдущие сборки
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    
    versions = [
        {
            'name': 'GB2Text-Debug',
            'console': True,
            'description': 'версия с консолью для отладки'
        },
        {
            'name': 'GB2Text',
            'console': False,
            'description': 'финальная версия без консоли'
        }
    ]

    debug_wrapper_content = '''
import sys
import traceback
import logging
from pathlib import Path

# Настройка логирования в файл
log_file = Path(__file__).parent / "gb2text_debug.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

try:
    logging.info("Запуск GB2Text Debug версии...")

    # Импортируем и запускаем основную программу
    import main

except Exception as e:
    logging.error(f"Критическая ошибка: {e}")
    logging.error(f"Трассировка: {traceback.format_exc()}")
    print(f"\\n❌ ОШИБКА: {e}")
    print(f"📝 Подробности сохранены в: {log_file}")
    print("\\n" + "="*50)
    print("ПОЛНАЯ ТРАССИРОВКА ОШИБКИ:")
    print("="*50)
    traceback.print_exc()
    print("="*50)

finally:
    print("\\n🔍 Для закрытия нажмите Enter...")
    try:
        input()
    except:
        import time
        time.sleep(10)  # Ждем 10 секунд если input не работает
'''

    debug_wrapper_path = gb2text_dir / "debug_main.py"
    with open(debug_wrapper_path, 'w', encoding='utf-8') as f:
        f.write(debug_wrapper_content)

    for version in versions:
        print(f"\n🔨 Создание {version['description']}...")
        entry_script = debug_wrapper_path if version['console'] else main_script
        
        cmd = [
            sys.executable, "-m", "PyInstaller",  # Используем Python модуль вместо прямого вызова
            "--onefile",                    # Один exe файл (портативный)
            "--clean",                      # Очистка кэша
            f"--name={version['name']}",    # Имя exe файла
            "--hidden-import=tkinter",
            "--hidden-import=tkinter.ttk",
            "--hidden-import=tkinter.scrolledtext",
            "--hidden-import=tkinter.filedialog",
            "--hidden-import=tkinter.messagebox",
            "--hidden-import=json",
            "--hidden-import=logging",
            "--hidden-import=pathlib",
            "--hidden-import=collections",
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
            "--exclude-module=PIL",
            "--exclude-module=cv2",
        ]
        
        if not version['console']:
            cmd.append("--windowed")

        version_file = gb2text_dir / "VERSION"
        if version_file.exists():
            cmd.extend([f"--add-data={version_file};."])
            print(f"✅ Добавлен файл VERSION")
        else:
            print(f"⚠️ Файл VERSION не найден в {version_file}")
        
        for folder in existing_folders:
            folder_path = gb2text_dir / folder
            if folder == 'locales':
                # Добавляем каждый JSON файл отдельно
                locales_files = list(folder_path.glob('*.json'))
                for locale_file in locales_files:
                    cmd.extend([f"--add-data={locale_file};locales/"])
                print(f"✅ Добавлены файлы локализации: {len(locales_files)} файлов")
            else:
                cmd.extend([f"--add-data={folder_path};{folder}"])
        
        icon_path = gb2text_dir / "resources" / "app_icon.ico"
        if icon_path.exists():
            cmd.append(f"--icon={icon_path}")
            print("✅ Найдена иконка")
        else:
            print("⚠️ Иконка не найдена, используется стандартная")
        
        cmd.append(str(entry_script))
        
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

    if debug_wrapper_path.exists():
        debug_wrapper_path.unlink()

    create_portable_package(gb2text_dir, dist_dir)
    
    return True

def create_portable_package(gb2text_dir, dist_dir):
    """Создает портативный пакет с exe файлом"""
    
    print("\n📦 Создание портативного пакета...")
    
    portable_dir = gb2text_dir.parent / "GB2Text-Portable"
    if portable_dir.exists():
        shutil.rmtree(portable_dir)
    portable_dir.mkdir()
    
    # Копируем exe файлы
    for exe_name in ["GB2Text.exe", "GB2Text-Debug.exe"]:
        exe_path = dist_dir / exe_name
        if exe_path.exists():
            shutil.copy2(exe_path, portable_dir / exe_name)
            print(f"✅ Скопирован {exe_name}")
    
    # Создаем README для пользователя
    readme_content = """GB2Text - Портативная версия

ФАЙЛЫ:
- GB2Text.exe - основная программа (без консоли)
- GB2Text-Debug.exe - версия с консолью для отладки ошибок

ИСПОЛЬЗОВАНИЕ:
1. Запустите GB2Text.exe для обычной работы
2. Если программа не запускается или работает неправильно, 
   запустите GB2Text-Debug.exe чтобы увидеть ошибки в консоли

ОТЛАДКА ОШИБОК:
- Debug версия создает файл gb2text_debug.log с подробными ошибками
- Консоль не закрывается автоматически - нажмите Enter для выхода
- Все ошибки сохраняются в лог файл для анализа

ТРЕБОВАНИЯ:
- Windows 7/8/10/11
- Не требует установки Python или других программ
- Все необходимые файлы включены в exe

ПОДДЕРЖКА:
- Если возникают проблемы, запустите Debug версию
- Скопируйте текст ошибок из консоли или gb2text_debug.log для диагностики
"""
    
    with open(portable_dir / "README.txt", 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"✅ Портативный пакет создан: {portable_dir}")
    print("📋 Включает обе версии exe и инструкции")

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
    
    folders_to_include = []
    for folder in ['plugins', 'locales', 'settings', 'resources', 'gui', 'core']:
        folder_path = gb2text_dir / folder
        if folder_path.exists():
            folders_to_include.append(f"        ('{folder}', '{folder}'),")
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
{chr(10).join(folders_to_include)}
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.scrolledtext',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'json',
        'logging',
        'pathlib',
        'collections',
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
        'PIL',
        'cv2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GB2Text',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    cofile=None,
    icon='resources/app_icon.ico' if (Path('resources/app_icon.ico').exists()) else None,
)
'''

    spec_path = gb2text_dir / 'GB2Text.spec'
    with open(spec_path, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
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
