"""
spec file for building ChettinadTiles.exe (professional folder distribution)
PyInstaller --onedir mode → produces a folder with .exe + all DLLs
Zip that folder → distribute like a real game
"""
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all websockets submodules (important for async WS to work)
websockets_imports = collect_submodules('websockets')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Include assets folder if it exists
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'pygame',
        'pygame.gfxdraw',
        'websockets',
        'websockets.client',
        'websockets.server',
        'websockets.connection',
        'websockets.exceptions',
        'websockets.frames',
        'websockets.http11',
        'websockets.imports',
        'websockets.legacy',
        'websockets.legacy.client',
        'websockets.legacy.server',
        'websockets.asyncio',
        'websockets.asyncio.client',
        'websockets.asyncio.server',
        'asyncio',
    ] + websockets_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'PIL'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # onedir mode
    name='ChettinadTiles',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,          # no console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ChettinadTiles',
)
