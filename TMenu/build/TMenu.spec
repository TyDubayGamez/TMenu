# -*- mode: python ; coding: utf-8 -*-
#
# Disposable: build.bat deletes and regenerates this file from its own
# PyInstaller CLI flags every run (mirroring what's below) - only kept
# here for reference / for running pyinstaller directly on the .spec
# instead of via build.bat. Run from build\ (this file's own folder) -
# app.py is one level up at the repo root, hence '../app.py' below.


a = Analysis(
    ['../app.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.ico', 'build')],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='TMenu',
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
    version='version_info.txt',
    icon=['icon.ico'],
)
