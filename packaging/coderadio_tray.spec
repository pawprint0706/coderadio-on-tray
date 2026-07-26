# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Code Radio Tray (onedir, windowed, slim Qt)."""

import sys
from pathlib import Path

SPECDIR = Path(SPECPATH).resolve()
ROOT = SPECDIR.parent
SRC = ROOT / "src"

# Do NOT collect_all(PySide6) — that pulls WebEngine/3D/Charts (~700MB+).
# Hooks for QtCore/Gui/Widgets/Network follow from imports in the app.

a = Analysis(
    [str(SRC / "coderadio_tray" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "coderadio_tray",
        "coderadio_tray.app",
        "coderadio_tray.config",
        "coderadio_tray.paths",
        "coderadio_tray.single_instance",
        "coderadio_tray.platform_win",
        "coderadio_tray.metadata",
        "coderadio_tray.metadata.client",
        "coderadio_tray.player",
        "coderadio_tray.player.mpv_player",
        "coderadio_tray.player.worker",
        "coderadio_tray.ui",
        "coderadio_tray.ui.tray",
        "coderadio_tray.ui.popup",
        "coderadio_tray.ui.icons",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtBluetooth",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtDesigner",
        "PySide6.QtGraphs",
        "PySide6.QtGraphsWidgets",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtQml",
        "PySide6.QtRemoteObjects",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtTextToSpeech",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "PySide6.QtWebView",
        "tkinter",
        "unittest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CodeRadioTray",
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
    name="CodeRadioTray",
)

# On macOS wrap onedir into a .app (menu-bar accessory; LSUIElement hides Dock).
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="CodeRadioTray.app",
        icon=None,
        bundle_identifier="org.coderadio-on-tray.app",
        info_plist={
            "CFBundleName": "Code Radio Tray",
            "CFBundleDisplayName": "Code Radio Tray",
            "CFBundleShortVersionString": "0.3.0",
            "NSHighResolutionCapable": True,
            "LSUIElement": True,
        },
    )
