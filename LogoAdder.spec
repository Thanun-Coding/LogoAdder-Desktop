# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['LogoAdder.py'],
    pathex=[],
    binaries=[],
    datas=[('myicon.ico', '.'), ('Title Logo.png', '.')],
    hiddenimports=['PySide6', 'qt_material', 'PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'PyQt5', 'PySide2'],
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
    name='LogoAdder',
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
    codesign_identity=None,
    entitlements_file=None,
    icon=['myicon.ico'],
)
