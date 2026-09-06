# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/EndY/Desktop/PortableGit/GB2Text/debug_main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/EndY/Desktop/PortableGit/GB2Text/VERSION', '.'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/plugins', 'plugins'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/locales/en/charset.json', 'locales/en'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/locales/en/messages.json', 'locales/en'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/locales/ja/charset.json', 'locales/ja'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/locales/ja/messages.json', 'locales/ja'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/locales/ru/charset.json', 'locales/ru'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/locales/ru/messages.json', 'locales/ru'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/locales/zh/charset.json', 'locales/zh'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/locales/zh/messages.json', 'locales/zh'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/guides', 'guides'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/resources', 'resources'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/gui', 'gui'), ('C:/Users/EndY/Desktop/PortableGit/GB2Text/core', 'core')],
    hiddenimports=['tkinter', 'tkinter.ttk', 'tkinter.scrolledtext', 'tkinter.filedialog', 'tkinter.messagebox', 'json', 'logging', 'pathlib', 'collections', 'core.decoder', 'core.scanner', 'core.extractor', 'core.injector', 'core.compression', 'core.gba_support', 'core.multi_charmap', 'core.plugin_api', 'core.tmx', 'core.ml_classifier', 'core.translation_validator', 'core.translation_filler', 'core.analyzer', 'core.database', 'core.encoding', 'core.charset', 'core.guide', 'core.mbc', 'core.rom_cache', 'core.i18n', 'core.machine_translation'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['posix', 'pwd', 'grp', 'fcntl', 'resource', '_posixsubprocess', 'java', 'org', 'vms_lib', '_winreg', 'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'cv2'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GB2Text-Debug',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:/Users/EndY/Desktop/PortableGit/GB2Text/resources/app_icon.ico'],
)
