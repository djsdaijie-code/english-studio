# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH)
src_root = project_root / "src"
debug_console = os.environ.get("ETT_DEBUG_CONSOLE", "0") == "1"

hidden_imports = collect_submodules("PySide6.QtCharts")
hidden_imports += collect_submodules("PySide6.QtSvg")

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(src_root)],
    binaries=[],
    datas=[
        (str(project_root / "resources" / "styles"), "resources/styles"),
    ],
    hiddenimports=hidden_imports,
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
    name="EnglishTypingTrainer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=debug_console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(project_root / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="EnglishTypingTrainer",
)