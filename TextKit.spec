# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for TextKit.app — bundles client + server into one launchable .app
import os

PROJECT_ROOT = os.path.abspath(os.getcwd())

# Bundle the server source + configs as data so the client can spawn it
datas = [
    (os.path.join(PROJECT_ROOT, 'server'), 'server'),
    (os.path.join(PROJECT_ROOT, 'client', 'config.yaml'), 'client'),
    (os.path.join(PROJECT_ROOT, '.env'), '.'),
]

hiddenimports = [
    'pynput.keyboard._darwin',
    'pynput.mouse._darwin',
    'Cocoa',
    'Quartz',
    'AppKit',
    'objc',
    'PIL',
    'PIL._tkinter_finder',
]

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'client', 'main.py')],
    pathex=[
        os.path.join(PROJECT_ROOT, 'client'),
        os.path.join(PROJECT_ROOT, 'server'),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TextKit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TextKit',
)

app = BUNDLE(
    coll,
    name='TextKit.app',
    icon=None,
    bundle_identifier='com.textkit.assistant',
    info_plist={
        'CFBundleName': 'TextKit',
        'CFBundleDisplayName': 'TextKit',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0',
        'LSUIElement': True,  # accessory app — no Dock icon
        'NSHighResolutionCapable': True,
        'NSAppleEventsUsageDescription': 'TextKit needs accessibility access for the global hotkey.',
    },
)
