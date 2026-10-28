"""安装到项目临时目录，验证重复安装和卸载；已有正式安装时拒绝测试。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import uuid
import winreg

ROOT = Path(__file__).resolve().parents[1]
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{38AC61BA-D0EE-4E74-A108-8E2F80C5742B}_is1"


def registration():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return winreg.QueryValueEx(key, "InstallLocation")[0]
    except FileNotFoundError:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("installer", type=Path)
    args = parser.parse_args()
    if registration():
        raise SystemExit("检测到现有 Stardot 安装，跳过自动安装测试，避免覆盖。")
    test_root = ROOT / "artifacts" / "packaging" / ("安装测试 " + uuid.uuid4().hex[:8])
    destination = (test_root / "程序目录 Stardot").resolve()
    assert destination.is_relative_to((ROOT / "artifacts" / "packaging").resolve())
    test_root.mkdir(parents=True)
    # 用独立目录的 SQLite 样本验证升级/卸载不会删除应用目录外的数据。
    data = test_root / "用户数据.sqlite3"
    with sqlite3.connect(data) as connection:
        connection.execute("CREATE TABLE tasks (body TEXT)")
        connection.execute("INSERT INTO tasks VALUES (?)", ("升级与卸载后保留",))
    connection.close()  # 验证期间不占用文件，避免文件锁掩盖意外删除。
    data_hash = hashlib.sha256(data.read_bytes()).hexdigest()
    environment = os.environ.copy()
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH"):
        environment.pop(key, None)
    environment["PATH"] = environment["WINDIR"] + os.pathsep + os.path.join(environment["WINDIR"], "System32")
    flags = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/NOICONS", "/TASKS=",
             "/LANG=chinesesimplified", f"/DIR={destination}"]
    report = {"ok": False, "test_directory": str(test_root), "checks": []}
    try:
        for number in (1, 2):
            subprocess.run([str(args.installer.resolve()), *flags, f"/LOG={test_root / f'install-{number}.log'}"],
                           timeout=90, check=True)
            assert Path(registration()).resolve() == destination
            assert (destination / "Stardot.exe").exists()
            output = test_root / f"installed-smoke-{number}.json"
            subprocess.run([str(destination / "Stardot.exe"), "--smoke-test", str(output)],
                           cwd=test_root, env=environment, timeout=45, check=True)
            assert json.loads(output.read_text(encoding="utf-8"))["ok"]
            assert hashlib.sha256(data.read_bytes()).hexdigest() == data_hash
        report["checks"].extend(["unicode_space_install_path", "installed_native_smoke", "repeat_install"])
    finally:
        uninstaller = destination / "unins000.exe"
        if uninstaller.is_file():
            # 仅运行刚安装在本次工作区测试目录中的卸载器。
            assert uninstaller.resolve().is_relative_to(test_root.resolve())
            subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                            f"/LOG={test_root / 'uninstall.log'}"], timeout=60, check=True)
            for _ in range(30):
                if not (destination / "Stardot.exe").exists() and not registration():
                    break
                time.sleep(0.2)
        assert not (destination / "Stardot.exe").exists()
        assert not registration()
        assert hashlib.sha256(data.read_bytes()).hexdigest() == data_hash
    report["checks"].extend(["uninstall_removes_program_and_registration", "external_sqlite_unchanged"])
    report["ok"] = True
    (ROOT / "artifacts" / "packaging" / "installer-check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS: install, native smoke, repeated install, uninstall, external data preservation")


if __name__ == "__main__":
    main()
