# PyInstaller spec for the Bridge Agent
# Build: pyinstaller bridge_agent.spec
# Output: dist/bridge_agent.exe (Windows) or dist/bridge_agent (macOS/Linux)

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Include .env template
        ('bridge_agent.env.example', '.'),
    ],
    hiddenimports=[
        'smartcard',
        'smartcard.System',
        'smartcard.CardConnection',
        'smartcard.Exceptions',
        'websockets',
        'websockets.asyncio',
        'websockets.asyncio.server',
        'websockets.legacy',
        'websockets.legacy.server',
        'cryptography',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy'],
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
    name='bridge_agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,    # keep console so HR can see NFC tap logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
