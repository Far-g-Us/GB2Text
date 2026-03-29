"""
Упрощенный скрипт для создания exe файла из проекта GB2Text
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def create_simple_exe():
    """Создает exe файл с минимальными настройками для надежности"""
    
    print("🔨 Создание exe файла для GB2Text (упрощенная версия)...")
    
    # Проверяем наличие PyInstaller
    try:
        import PyInstaller
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
        "--hidden-import=gui.main_window",
        "--hidden-import=gui.text_extraction_tab", 
        "--hidden-import=gui.text_editing_tab",
        "--hidden-import=core.extractor",
        "--hidden-import=core.scanner",
        "--hidden-import=core.analyzer",
        "--hidden-import=plugins.auto_detect",
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk",
        "--hidden-import=tkinter.scrolledtext",
        "--hidden-import=tkinter.filedialog",
        "--hidden-import=tkinter.messagebox",
        "--hidden-import=json",
        "--hidden-import=logging",
        "--hidden-import=pathlib",
        "--hidden-import=collections",
    ]

    version_file = gb2text_dir / "VERSION"
    if version_file.exists():
        cmd.extend([f"--add-data={version_file};."])
        print(f"✅ Добавлен файл VERSION")
    else:
        print(f"⚠️ Файл VERSION не найден в {version_file}")
    
    # Добавляем папки проекта
    required_folders = ['plugins', 'locales', 'guides', 'settings', 'resources', 'gui', 'core']
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
            print(f"❌ Ошибка сборки:")
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
