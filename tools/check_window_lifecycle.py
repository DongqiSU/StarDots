"""短暂打开原生 Qt 窗口，检查显示前透明度与首帧淡入；只使用临时数据库。"""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest

from stardot.app import create_runtime


def main():
    with TemporaryDirectory(prefix="stardot-window-") as directory:
        runtime = create_runtime(["stardot-window-check"], database_path=Path(directory) / "test.sqlite3")
        failures = []
        shown_opacities = []
        rendered_frames = []
        runtime.panel.visibleChanged.connect(
            lambda visible: shown_opacities.append(runtime.panel.opacity()) if visible else None)
        runtime.panel.frameSwapped.connect(lambda: rendered_frames.append(True))

        def check():
            try:
                for cycle in range(3):
                    runtime.controller.showPanel()
                    assert runtime.panel.opacity() == 0
                    opacity_samples = []
                    for _ in range(25):
                        QTest.qWait(16)
                        opacity_samples.append(runtime.panel.opacity())
                    assert rendered_frames, "原生窗口没有提交首帧"
                    assert opacity_samples[-1] > 0.99, "淡入未完成"
                    assert all(a <= b for a, b in zip(opacity_samples, opacity_samples[1:])), "淡入期间不应重新变暗"
                    runtime.controller.showPanel()
                    assert runtime.panel.opacity() > 0.99, "重复聚焦不应重启淡入"
                    runtime.tasks.newTask()
                    runtime.tasks.setDraftText(f"窗口生命周期检查 {cycle}")
                    runtime.controller.hidePanel()
                    QTest.qWait(40)
                    assert not runtime.panel.isVisible() and not runtime.tasks.draftVisible
                    assert runtime.panel.opacity() == 0
                assert all(value == 0 for value in shown_opacities)
                assert runtime.tasks.activeCount == 3
                print(f"PASS: {runtime.app.platformName()} native window; 3 first-frame fades, repeated focus, close/save")
            except Exception as error:
                failures.append(error)
                print(f"FAIL: {error}", file=sys.stderr)
            finally:
                runtime.tasks.cancelDraft()
                runtime.controller.hidePanel()
                runtime.star.hide()
                runtime.app.quit()

        QTimer.singleShot(350, check)
        runtime.app.exec()
        return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
