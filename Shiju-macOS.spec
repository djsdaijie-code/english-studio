# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH)
sys.path.insert(0, str(root / "src"))
from english_typing_trainer import __version__

hidden_imports = []
for module in ("PySide6.QtCharts", "PySide6.QtSvg", "PySide6.QtMultimedia", "keyring.backends.macOS"):
    hidden_imports += collect_submodules(module)

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[
        (str(root / "resources" / "styles"), "resources/styles"),
        (str(root / "resources" / "icons"), "resources/icons"),
        (str(root / "resources" / "sample_article.txt"), "resources"),
        (str(root / "courses"), "courses"),
        (str(root / "LICENSE"), "documents"),
        (str(root / "THIRD_PARTY_NOTICES.md"), "documents"),
        (str(root / "PRIVACY.md"), "documents"),
    ],
    hiddenimports=hidden_imports,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="Shiju", console=False,
    debug=False, strip=False, upx=False, argv_emulation=False,
    target_arch="arm64", codesign_identity=None, entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Shiju")
app = BUNDLE(
    coll, name="拾句.app", icon=str(root / "resources" / "icons" / "shiju.icns"),
    bundle_identifier="io.github.djsdaijie-code.english-studio",
    version=__version__,
    info_plist={
        "CFBundleDisplayName": "拾句",
        "CFBundleName": "拾句",
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.education",
    },
)
