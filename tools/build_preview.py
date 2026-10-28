"""uv run --group build python tools/build_preview.py [--iscc path/to/ISCC.exe]"""

import argparse
import hashlib
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stardot import __version__


def clean_environment():
    environment = os.environ.copy()
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH"):
        environment.pop(key, None)
    # 构建也要隔离 PATH：其他软件的同名 ICU/UCRT 库可能被错误收集。
    environment["PATH"] = os.pathsep.join((os.path.join(environment["WINDIR"], "System32"),
                                            environment["WINDIR"], sys.base_prefix))
    return environment


def generate_assets():
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct)

    output = ROOT / "build" / "preview-assets"
    output.mkdir(parents=True, exist_ok=True)
    renderer = QSvgRenderer(str(ROOT / "stardot" / "assets" / "star.svg"))
    sizes = (16, 24, 32, 48, 64, 128, 256)
    images = []
    for size in sizes:
        image = QImage(size, size, QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        assert image.save(buffer, "PNG")
        images.append(bytes(data))
    offset = 6 + 16 * len(sizes)
    entries = []
    for size, data in zip(sizes, images):
        entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    (output / "Stardot.ico").write_bytes(struct.pack("<HHH", 0, 1, len(sizes)) + b"".join(entries + images))
    version = VSVersionInfo(
        ffi=FixedFileInfo(filevers=(1, 0, 0, 0), prodvers=(1, 0, 0, 0), mask=0x3f,
                          flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
        kids=[StringFileInfo([StringTable("040904B0", [
            StringStruct("FileDescription", "Stardot 星点"),
            StringStruct("FileVersion", __version__), StringStruct("ProductVersion", __version__),
            StringStruct("ProductName", "Stardot"), StringStruct("OriginalFilename", "Stardot.exe")])]),
            VarFileInfo([VarStruct("Translation", [1033, 1200])])])
    (output / "version.txt").write_text(str(version), encoding="utf-8")
    licenses = output / "licenses"
    licenses.mkdir(exist_ok=True)
    for path in (ROOT / "build-support" / "licenses").iterdir():
        if path.is_file():
            shutil.copy2(path, licenses / path.name)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
    pyinstaller = distribution("pyinstaller")
    installer_license = next(pyinstaller.locate_file(path) for path in pyinstaller.files
                             if path.name == "COPYING.txt")
    shutil.copy2(installer_license, licenses / "PyInstaller-COPYING.txt")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iscc", type=Path, help="Inno Setup compiler; omit to build the portable zip only")
    parser.add_argument("--skip-build", action="store_true", help="Reuse an existing dist/Stardot build")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("此构建脚本需要 Windows x64。")
    os.chdir(ROOT)
    generate_assets()
    if not args.skip_build:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                        "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / "pyinstaller"),
                        str(ROOT / "build-support" / "Stardot.spec")], env=clean_environment(), check=True)
    distribution = ROOT / "dist" / "Stardot"
    executable = distribution / "Stardot.exe"
    if not executable.exists():
        raise SystemExit("找不到 dist/Stardot/Stardot.exe，请先完成构建。")
    shutil.copy2(ROOT / "build-support" / "preview-notes.txt", distribution / "使用说明.txt")
    # 使用程序目录作为工作目录，并移除开发相关路径；不会依赖项目源码启动。
    environment = clean_environment()
    environment["PATH"] = os.path.join(environment["WINDIR"], "System32") + os.pathsep + environment["WINDIR"]
    report_path = ROOT / "artifacts" / "packaging" / "frozen-smoke.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(executable), "--smoke-test", str(report_path)], cwd=distribution,
                   env=environment, timeout=45, check=True)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not report.get("ok") or not report.get("frozen"):
        raise SystemExit(f"打包自检未通过：{report}")
    archive = shutil.make_archive(str(ROOT / "dist" / f"Stardot-{__version__}-windows-x64-portable"),
                                  "zip", ROOT / "dist", "Stardot")
    outputs = [Path(archive)]
    if args.iscc:
        subprocess.run([str(args.iscc.resolve()), f"/DAppVersion={__version__}",
                        str(ROOT / "build-support" / "Stardot.iss")], check=True)
        outputs.append(ROOT / "dist" / f"Stardot-{__version__}-windows-x64-setup.exe")
    checksums = []
    for path in outputs:
        with path.open("rb") as stream:
            checksums.append(f"{hashlib.file_digest(stream, 'sha256').hexdigest()}  {path.name}")
        print(f"READY: {path} ({path.stat().st_size / 1024 / 1024:.1f} MiB)")
    (ROOT / "dist" / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
