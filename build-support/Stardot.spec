# Run with: uv run --group build python tools/build_preview.py
from pathlib import Path
import os
import sys

root = Path(SPECPATH).parent
generated = root / "build" / "preview-assets"
a = Analysis(
    [str(root / "main.py")], pathex=[str(root)],
    binaries=[],
    datas=[(str(root / "stardot" / "qml"), "stardot/qml"),
           (str(root / "stardot" / "assets"), "stardot/assets"),
           (str(generated / "licenses"), "licenses")],
    hiddenimports=["PySide6.QtSvg"],
    hookspath=[str(root / "build-support" / "hooks")],
    excludes=["PySide6.QtTest", "unittest", "tkinter", "pytest"],
    noarchive=False,
)
# 拒绝收集项目环境之外的第三方库，避免构建机其他软件影响发布包。
allowed_roots = [root / ".venv", Path(sys.base_prefix), Path(os.environ["WINDIR"])]
for destination, source, kind in a.binaries:
    path = Path(source).resolve()
    if not any(path.is_relative_to(parent.resolve()) for parent in allowed_roots):
        raise RuntimeError(f"Unexpected external binary: {path}")
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="Stardot", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False,
    console=bool(os.environ.get("STARDOT_DEBUG_CONSOLE")),
    icon=str(generated / "Stardot.ico"), version=str(generated / "version.txt"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Stardot")
