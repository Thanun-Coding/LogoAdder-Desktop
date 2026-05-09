# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['LogoAdder.py'],
    pathex=[],
    binaries=[],
    datas=[('assets\\applogo.ico', 'assets'), ('assets\\Title Logo.png', 'assets'), ('assets\\KhmerOSmuollight.ttf', 'assets'), ('assets\\KhmerOSsiemreap.ttf', 'assets'), ('assets\\brown cheese.otf', 'assets'), ('assets\\arrows-clockwise.svg', 'assets'), ('assets\\flip-vertical.svg', 'assets'), ('assets\\flip-horizontal.svg', 'assets')],
    hiddenimports=['PySide6', 'pillow_heif'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['qt_material', 'PyQt6', 'PyQt5', 'PySide2', 'tkinter', 'numpy'],
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
    icon=['assets\\applogo.ico'],
)
