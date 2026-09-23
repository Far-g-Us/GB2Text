# -*- mode: python ; coding: utf-8 -*-
# Портативный spec (только относительные пути, CWD — корень проекта).
# Сборки пишут свои spec в build/specs (--specpath) и этот файл не трогают.


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('VERSION', '.'), ('plugins', 'plugins'), ('locales/en/charset.json', 'locales/en'), ('locales/en/messages.json', 'locales/en'), ('locales/ja/charset.json', 'locales/ja'), ('locales/ja/messages.json', 'locales/ja'), ('locales/ru/charset.json', 'locales/ru'), ('locales/ru/messages.json', 'locales/ru'), ('locales/zh/charset.json', 'locales/zh'), ('locales/zh/messages.json', 'locales/zh'), ('settings', 'settings'), ('resources', 'resources'), ('gui', 'gui'), ('core', 'core')],
    hiddenimports=['tkinter', 'tkinter.ttk', 'tkinter.scrolledtext', 'tkinter.filedialog', 'tkinter.messagebox', 'json', 'logging', 'pathlib', 'collections', 'PIL', 'PIL.Image', 'PIL.ImageTk', 'spellchecker', 'tkinterdnd2', 'core.extractor', 'core.scanner', 'core.analyzer', 'core.decoder', 'core.compression', 'core.gba_support', 'core.multi_charmap', 'core.plugin_api', 'core.tmx', 'core.ml_classifier', 'core.translation_validator', 'core.translation_filler', 'core.encoding', 'core.charset', 'core.guide', 'core.mbc', 'core.rom_cache', 'core.i18n', 'core.machine_translation', 'core.injector', 'core.database', 'core.font_tiles', 'core.font_ui', 'core.playtest', 'core.dte', 'core.pointer_table', 'core.textbox', 'core.plugin_manager', 'core.rom', 'gui.main_window', 'gui.font_tab', 'gui.glyph_editor', 'plugins.auto_detect'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GB2Text-Debug',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources/app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GB2Text-Debug',
)
