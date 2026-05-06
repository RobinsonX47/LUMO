# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['desktop\\launcher.py'],
    pathex=[],
    binaries=[('C:/Users/robin/AppData/Local/Programs/Python/Python312/python312.dll', '.')],
    datas=[('templates', 'templates'), ('static', 'static'), ('.env', '.')],
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
    name='LUMO-Desktop',
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
)
