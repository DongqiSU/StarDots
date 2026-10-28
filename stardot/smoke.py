"""随体验版提供的打包自检入口；永远使用临时数据库，不接触用户任务。"""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from PySide6.QtCore import QTimer, QEventLoop, qInstallMessageHandler, qVersion
from PySide6.QtGui import QIcon

from stardot import __version__
from stardot.app import create_runtime, PACKAGE_DIR
from stardot.storage import TaskStore


def run_smoke_test(report_path):
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {"version": __version__, "frozen": bool(getattr(sys, "frozen", False)),
              "executable": sys.executable, "qt": qVersion(), "checks": [], "ok": False}
    messages = []
    previous_handler = qInstallMessageHandler(lambda _kind, _context, message: messages.append(message))
    try:
        with TemporaryDirectory(prefix="stardot-preview-smoke-") as directory:
            database = Path(directory) / "test.sqlite3"
            runtime = create_runtime(["stardot-smoke-test"], database_path=database)

            def finish(error=None):
                if error:
                    report["error"] = str(error)
                runtime.tasks.cancelDraft()
                runtime.controller.hidePanel()
                runtime.star.hide()
                runtime.app.quit()

            def verify():
                try:
                    assert runtime.panel.isVisible() and runtime.panel.opacity() > 0.99
                    assert not runtime.panel.grabWindow().isNull()
                    assert not QIcon(str(PACKAGE_DIR / "assets" / "star.svg")).pixmap(64, 64).isNull()
                    report["checks"].append("native_window_qml_svg_first_frame")
                    assert runtime.tasks.receiveText("提醒：明天下午三点提交体验版反馈。谢谢！")
                    assert runtime.tasks.draftTime == "15:00"
                    assert runtime.tasks.saveDraft()
                    task = runtime.store.list_tasks()[0]
                    assert runtime.tasks.editTask(task.task_id)
                    runtime.tasks.setDraftText("打包后保存、编辑与归档检查")
                    runtime.controller.hidePanel()
                    assert not runtime.tasks.draftVisible
                    assert runtime.store.get(task.task_id).body == "打包后保存、编辑与归档检查"
                    assert runtime.tasks.completeTask(task.task_id)
                    assert runtime.tasks.deleteTask(task.task_id)
                    runtime.tasks.undo()
                    assert runtime.store.get(task.task_id).completed_at is not None
                    assert runtime.tasks.restoreTask(task.task_id)
                    with_store = TaskStore(database)
                    try:
                        restored = with_store.get(task.task_id)
                        assert restored.body == "打包后保存、编辑与归档检查"
                        assert restored.due_time == "15:00" and restored.completed_at is None
                    finally:
                        with_store.close()
                    report["checks"].append("summary_date_sqlite_edit_close_archive_delete_undo_reopen")
                    runtime.controller.showCalendar()
                    loop = QEventLoop()
                    QTimer.singleShot(180, loop.quit)
                    loop.exec()
                    assert runtime.controller._calendar_window is not None
                    assert not runtime.controller._calendar_window.grabWindow().isNull()
                    assert not runtime.panel.isVisible()
                    runtime.controller.closeCalendar()
                    assert not runtime.panel.isVisible()
                    runtime.controller.showSettings()
                    QTimer.singleShot(180, loop.quit)
                    loop.exec()
                    assert runtime.controller._settings_window is not None
                    assert not runtime.controller._settings_window.grabWindow().isNull()
                    runtime.controller.closeSettings()
                    runtime.controller.hideStar()
                    assert not runtime.star.isVisible()
                    runtime.controller.revealStar()
                    assert runtime.star.isVisible()
                    backup = Path(directory) / "backup.sqlite3"
                    runtime.store.export_backup(backup)
                    runtime.store.add("测试恢复", "")
                    runtime.store.restore_backup(backup)
                    runtime.tasks.reload()
                    assert len(runtime.store.list_tasks()) == 1
                    from datetime import datetime, timedelta
                    runtime.reminders.now = lambda: datetime.fromisoformat(f"{task.due_date}T{task.due_time}") + timedelta(minutes=1)
                    delivered = []
                    runtime.reminders.notify = lambda items: delivered.append(items) or True
                    runtime.reminders.check()
                    runtime.reminders.check()
                    runtime.reminders.timer.stop()
                    assert len(delivered) == 1
                    report["checks"].append("calendar_settings_backup_restore_reminder_dedup_hide_reveal")
                    errors = [m for m in messages if "Error" in m or "file:" in m or "failed to load" in m.lower()]
                    assert not errors, "\n".join(errors)
                    report["ok"] = True
                    finish()
                except Exception as error:
                    finish(error)

            def open_panel():
                runtime.controller.showPanel()
                QTimer.singleShot(600, verify)

            QTimer.singleShot(300, open_panel)
            QTimer.singleShot(15000, runtime.app.quit)
            runtime.app.exec()
            if not report["ok"] and "error" not in report:
                report["error"] = "自检超时"
    except Exception as error:
        report["error"] = str(error)
    finally:
        qInstallMessageHandler(previous_handler)
        report["qt_messages"] = messages
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1
