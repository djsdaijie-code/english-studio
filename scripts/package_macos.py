from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from english_typing_trainer import __version__


def run(*args, env=None):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env, check=True)


def audit_bundle(bundle: Path) -> dict:
    forbidden_dirs = {".git", ".venv", "tests", "runtime_data", "workspace_data", "logs", "recordings"}
    forbidden_suffixes = {".db", ".sqlite", ".sqlite3", ".log", ".wav", ".mp3", ".env"}
    files = [path for path in bundle.rglob("*") if path.is_file()]
    bad = [str(path.relative_to(bundle)) for path in files
           if any(part in forbidden_dirs for part in path.relative_to(bundle).parts)
           or path.suffix.lower() in forbidden_suffixes
           or path.name.lower() in {"credentials.json", "config.json", ".env", "settings.json"}]
    if bad:
        raise RuntimeError(f"Unexpected personal/runtime files in bundle: {bad}")
    names = {path.name for path in files}
    for required in ("light.qss", "dark.qss", "shiju.svg", "shiju.icns", "catalog.json", "libqcocoa.dylib"):
        if required not in names:
            raise RuntimeError(f"Missing resource: {required}")
    if not any("QtMultimedia" in str(path) for path in files):
        raise RuntimeError("QtMultimedia is missing")
    return {"file_count": len(files), "bytes": sum(path.stat().st_size for path in files), "forbidden_files": []}


def smoke(bundle: Path, destination: Path) -> None:
    exe = bundle / "Contents" / "MacOS" / "Shiju"
    for action in ("seed", "verify"):
        env = os.environ.copy()
        env.update(
            ENGLISH_TYPING_TRAINER_DATA_DIR=str(destination / "data"),
            ENGLISH_TYPING_TRAINER_APP_TAG="acceptance-macos",
            ENGLISH_STUDIO_ACCEPTANCE_REPORT=str(destination / f"{action}.json"),
            ENGLISH_STUDIO_ACCEPTANCE_ACTION=action,
            QT_QPA_PLATFORM="offscreen",
        )
        subprocess.run([str(exe)], cwd=destination, env=env, check=True, timeout=90)
        report = json.loads((destination / f"{action}.json").read_text(encoding="utf-8"))
        if not report.get("passed"):
            raise RuntimeError(f"Packaged smoke failed: {action}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an Apple Silicon macOS test distribution.")
    parser.add_argument("--skip-tests", action="store_true")
    options = parser.parse_args()
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise SystemExit("Build this package on native Apple Silicon macOS.")
    if sys.version_info[:2] != (3, 14):
        raise SystemExit("Python 3.14 is required.")
    output = ROOT / "artifacts" / "macos-build"
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["ENGLISH_TYPING_TRAINER_DATA_DIR"] = str(output / "test-data")
    env["QT_QPA_PLATFORM"] = "offscreen"
    if not options.skip_tests:
        run(sys.executable, "-m", "pytest", "-q", "--basetemp", str(output / "pytest"), "-p", "no:cacheprovider", env=env)
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", "dist-macos", "--workpath", "build-macos", "Shiju-macOS.spec")
    bundle = ROOT / "dist-macos" / "拾句.app"
    executable = bundle / "Contents" / "MacOS" / "Shiju"
    run("/usr/bin/lipo", "-verify_arch", "arm64", executable)
    run("/usr/bin/codesign", "--verify", "--deep", "--strict", bundle)
    report = audit_bundle(bundle)
    report.update(version=__version__, architecture="arm64", signing="ad-hoc", notarized=False)
    smoke(bundle, output)
    report["packaged_smoke_passed"] = True
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    stem = f"Shiju-{__version__}-macOS-arm64"
    zip_path = release / f"{stem}.zip"
    dmg_path = release / f"{stem}.dmg"
    run("/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", bundle, zip_path)
    with tempfile.TemporaryDirectory(prefix="shiju-dmg-") as temporary:
        staging = Path(temporary)
        run("/usr/bin/ditto", bundle, staging / bundle.name)
        (staging / "Applications").symlink_to("/Applications", target_is_directory=True)
        (staging / "安装说明.txt").write_text(
            "拾句 · 拾句习语，读懂英文。\n\n拖动“拾句.app”到 Applications 即可安装。\n"
            "这是未完成 Apple 开发者签名与公证的测试版。若系统阻止打开，请在系统设置的隐私与安全性中确认。\n"
            "首次使用无需 API Key；翻译与朗读需在设置中配置自己的 Key。\n"
            "数据保存在 ~/Library/Application Support/EnglishStudio/，删除应用不会删除学习数据。\n"
            "Key 仅保存在 macOS 钥匙串。Mac 实机音频、输入法及 macOS 27.2 仍需用户验收。\n",
            encoding="utf-8",
        )
        run("/usr/bin/hdiutil", "create", "-volname", "拾句", "-srcfolder", staging, "-format", "UDZO", "-ov", dmg_path)
    sums = []
    report["artifacts"] = []
    for path in (zip_path, dmg_path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        sums.append(f"{digest}  {path.name}")
        report["artifacts"].append({"name": path.name, "bytes": path.stat().st_size, "sha256": digest})
    (release / "SHA256SUMS-macOS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
