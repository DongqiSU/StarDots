"""两个独立进程验证单实例激活；仅使用临时数据库，子进程自动退出。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def child(directory):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from stardot.app import main
    app = QApplication(["stardot-instance-check"])
    timer = QTimer()
    timer.setInterval(100)
    def check():
        star = next((w for w in app.topLevelWindows() if w.objectName() == "starWindow"), None)
        panel = next((w for w in app.topLevelWindows() if w.objectName() == "taskPanel"), None)
        if star:
            (directory / "ready").write_text("ready")
        if panel and panel.isVisible():
            (directory / "activated").write_text("activated")
            app.quit()
    timer.timeout.connect(check)
    timer.start()
    QTimer.singleShot(12000, app.quit)
    return main(database_path=directory / "test.sqlite3")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", type=Path)
    args = parser.parse_args()
    if args.child:
        return child(args.child)
    with TemporaryDirectory(prefix="stardot-single-instance-") as name:
        directory = Path(name)
        command = [sys.executable, str(Path(__file__).resolve()), "--child", name]
        first = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for _ in range(80):
                if (directory / "ready").exists():
                    break
                assert first.poll() is None
                time.sleep(0.1)
            assert (directory / "ready").exists(), "首个实例没有就绪"
            second = subprocess.run(command, capture_output=True, timeout=8)
            assert second.returncode == 0, second.stderr.decode(errors="replace")
            stdout, stderr = first.communicate(timeout=8)
            assert first.returncode == 0, stderr.decode(errors="replace")
            assert (directory / "activated").exists(), "第二次启动未激活已有清单"
            assert not (directory / "instance.lock").exists(), "退出后实例锁未释放"
        finally:
            if first.poll() is None:
                first.terminate()
                first.wait(timeout=5)
    report = ROOT / "artifacts" / "release" / "single-instance.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"ok": True, "checks": ["second_process_activates_first", "lock_released_on_exit"]}), encoding="utf-8")
    print("PASS: second process activated existing window; lock released on exit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
