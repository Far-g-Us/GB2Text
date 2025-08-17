# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Monty\\Desktop\\PortableGit\\GB2Text\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\Monty\\Desktop\\PortableGit\\GB2Text\\VERSION', '.'), ('C:\\Users\\Monty\\Desktop\\PortableGit\\GB2Text\\plugins', 'plugins'), ('C:\\Users\\Monty\\Desktop\\PortableGit\\GB2Text\\settings', 'settings'), ('C:\\Users\\Monty\\Desktop\\PortableGit\\GB2Text\\resources', 'resources'), ('C:\\Users\\Monty\\Desktop\\PortableGit\\GB2Text\\gui', 'gui'), ('C:\\Users\\Monty\\Desktop\\PortableGit\\GB2Text\\core', 'core')],
    hiddenimports=['gui.main_window', 'gui.text_extraction_tab', 'gui.text_editing_tab', 'core.extractor', 'core.scanner', 'core.analyzer', 'plugins.auto_detect', 'tkinter', 'tkinter.ttk', 'tkinter.scrolledtext', 'tkinter.filedialog', 'tkinter.messagebox', 'json', 'logging', 'pathlib', 'collections'],
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
    icon=['C:\\Users\\Monty\\Desktop\\PortableGit\\GB2Text\\resources\\app_icon.ico'],
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
