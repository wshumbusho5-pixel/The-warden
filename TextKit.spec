# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for TextKit. Cross-platform: produces TextKit.app on macOS,
# dist/TextKit/TextKit.exe on Windows. PyInstaller can't cross-build, so the
# Mac bundle has to be built on a Mac and the Windows exe on a Windows box
# (or in a GitHub Actions windows-latest runner).
import os
import sys

PROJECT_ROOT = os.path.abspath(os.getcwd())

IS_MAC = sys.platform == 'darwin'
IS_WIN = sys.platform.startswith('win')

# .env is intentionally NOT bundled — the invite-code first-run dialog lets
# friends configure their own credentials per machine, so the binary stays
# shareable without leaking the host's tokens.
datas = [
    (os.path.join(PROJECT_ROOT, 'server'), 'server'),
    (os.path.join(PROJECT_ROOT, 'client', 'config.yaml'), 'client'),
]

# Whisper model for local voice transcription. Downloaded in CI before this
# spec runs (see .github/workflows/build.yml) and shipped inside the bundle.
# Absence is not fatal — voice_input.py degrades gracefully — but the intent
# is for every release to include the model.
_WHISPER_DIR = os.path.join(PROJECT_ROOT, 'whisper_models')
if os.path.isdir(_WHISPER_DIR):
    datas.append((_WHISPER_DIR, 'whisper_models'))

# faster-whisper ships a Silero VAD ONNX model in its assets/ directory
# that vad_filter=True loads at runtime. PyInstaller misses package data
# files unless we ask for them explicitly, so grab them here.
from PyInstaller.utils.hooks import collect_data_files
datas += collect_data_files('faster_whisper')

# Common hidden imports the static analyzer can miss
hiddenimports = ['PIL', 'PIL._tkinter_finder']

if IS_MAC:
    hiddenimports += [
        'pynput.keyboard._darwin',
        'pynput.mouse._darwin',
        'Cocoa', 'Quartz', 'AppKit', 'objc',
    ]
elif IS_WIN:
    hiddenimports += [
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        # Windows.Media.Ocr via Microsoft's pywinrt projection
        'winrt.windows.foundation',
        'winrt.windows.foundation.collections',
        'winrt.windows.media.ocr',
        'winrt.windows.graphics.imaging',
        'winrt.windows.storage.streams',
        'winrt.windows.security.cryptography',
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
    console=False,  # GUI app — no terminal window on either platform
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

# Mac-only: wrap the collected output in an .app bundle so it behaves like
# a real macOS application. Windows just uses the COLLECT folder directly —
# dist/TextKit/TextKit.exe is what gets distributed (zip it for sharing).
if IS_MAC:
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
            'NSMicrophoneUsageDescription': 'Warden transcribes your voice locally on this device with Whisper. Audio is never sent to any server.',
        },
    )
