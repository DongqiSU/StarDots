"""首版联动验证；--native 验证 Windows 热键并测量进程占用，数据均为临时数据。"""

import argparse
import ctypes
from ctypes import wintypes
from datetime import date, timedelta
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument("--native", action="store_true")
parser.add_argument("--cycles", type=int, default=60)
args = parser.parse_args()
if not args.native:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_QUICK_BACKEND"] = "software"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QObject, QPoint, Qt, QEvent, qInstallMessageHandler
from PySide6.QtGui import QFontDatabase
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from stardot.app import create_runtime
from stardot.desktop import DesktopServices, hotkey_parts


def find(item, name):
    if item.objectName() == name:
        return item
    for child in item.childItems():
        found = find(child, name)
        if found is not None:
            return found


def click(window, name):
    item = find(window.contentItem(), name)
    assert item is not None, name
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, item.mapToScene(item.boundingRect().center()).toPoint())
    QTest.qWait(80)


def memory_mb():
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    assert ctypes.windll.psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
    return {"working_set_mib": round(counters.WorkingSetSize / 1048576, 1), "private_mib": round(counters.PrivateUsage / 1048576, 1)}


def main():
    messages = []
    qInstallMessageHandler(lambda _kind, _context, message: messages.append(message))
    app = QApplication(["stardot-release-check"])
    if not args.native:
        for name in ("msyh.ttc", "msyhbd.ttc"):
            QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / name))
    output = Path(__file__).resolve().parents[1] / "artifacts" / "release"
    output.mkdir(parents=True, exist_ok=True)
    report = {"native": args.native, "ok": False, "checks": []}
    with TemporaryDirectory(prefix="stardot-release-") as temporary:
        runtime = create_runtime(["check"], database_path=Path(temporary) / "test.sqlite3")
        tasks, controller = runtime.tasks, runtime.controller
        controller._mouse_is_down = lambda: False
        native = None
        try:
            QTest.qWait(250)
            today = date.today().isoformat()
            for body, day, clock in [("整理项目灵感与本周计划", today, "09:30"), ("提交设计方案", today, "15:00"),
                                     ("给窗台上的植物浇水", today, None), ("读完这一章", today, None),
                                     ("和朋友吃午饭", (date.today() + timedelta(days=1)).isoformat(), "12:00"),
                                     ("完成首版体验反馈", (date.today() + timedelta(days=3)).isoformat(), "16:30")]:
                runtime.store.add(body, body, day, clock)
            tasks.reload()
            if args.native:
                report["star_idle"] = memory_mb()
            controller.showPanel()
            QTest.qWait(250)
            click(runtime.panel, "calendarButton")
            calendar_window = controller._calendar_window
            assert calendar_window and calendar_window.isVisible()
            assert not runtime.panel.isVisible()
            assert runtime.calendar.dayModel.rowCount() == 4
            QTest.qWait(220)
            assert calendar_window.grabWindow().save(str(output / "calendar.png"))
            if args.native:
                report["calendar_open"] = memory_mb()
            first = runtime.calendar.dayModel.tasks[0]
            click(calendar_window, "task-" + first.task_id)
            # 卡片中心可能落在勾选区域之外，确认确实打开正文编辑。
            assert tasks.editing
            tasks.setDraftText("从日历编辑并保存")
            controller.closeCalendar()
            QTest.qWait(80)
            assert controller._calendar_window is None
            assert not runtime.panel.isVisible()
            assert runtime.store.get(first.task_id).body == "从日历编辑并保存"
            controller.showPanel()
            QTest.qWait(250)
            assert tasks.editTask(first.task_id)
            QTest.qWait(80)
            assert runtime.panel.grabWindow().save(str(output / "reminder-editor.png"))
            click(runtime.panel, "draftReminder")
            reminder = find(runtime.panel.contentItem(), "draftReminder")
            menu = reminder.findChild(QObject, "reminderMenu")
            assert menu.property("count") == 4
            option = find(menu.property("contentItem"), "reminderChoice-30")
            assert option is not None and option.isVisible()
            QTest.mouseClick(runtime.panel, Qt.LeftButton, Qt.NoModifier, option.mapToScene(option.boundingRect().center()).toPoint())
            QTest.qWait(80)
            assert tasks.draftReminder == 30
            controller.showCalendar()
            QTest.qWait(150)
            assert runtime.store.get(first.task_id).reminder_minutes == 30
            assert not tasks.draftVisible
            runtime.calendar.newTask()
            tasks.setDraftText("日历中的新任务")
            controller.showPanel()
            QTest.qWait(180)
            assert controller._calendar_window is None
            assert any(t.body == "日历中的新任务" and t.due_date == today for t in runtime.store.list_tasks())
            report["checks"].append("calendar_cells_overflow_shared_edits_close_and_switch_save")

            controller.showSettings()
            QTest.qWait(180)
            assert controller._settings_window
            assert controller._settings_window.grabWindow().save(str(output / "settings.png"))
            settings_window = controller._settings_window
            click(settings_window, "captureShortcutCombo")
            click(settings_window, "shortcutChoice-Ctrl+Alt+D")
            click(settings_window, "saveShortcuts")
            assert runtime.desktop.captureShortcut == "Ctrl+Alt+D"
            backup = Path(temporary) / "ui-backup.sqlite3"
            with patch("stardot.desktop.QFileDialog.getSaveFileName", return_value=(str(backup), "")):
                runtime.desktop.exportBackup()
            count = len(runtime.store.list_tasks())
            extra = runtime.store.add("恢复前的安全副本", "")
            with patch("stardot.desktop.QFileDialog.getOpenFileName", return_value=(str(backup), "")), patch("stardot.desktop.QMessageBox.question", return_value=QMessageBox.No):
                runtime.desktop.importBackup()
            assert runtime.store.get(extra.task_id)
            with patch("stardot.desktop.QFileDialog.getOpenFileName", return_value=(str(backup), "")), patch("stardot.desktop.QMessageBox.question", return_value=QMessageBox.Yes):
                runtime.desktop.importBackup()
            assert len(runtime.store.list_tasks()) == count
            assert list(Path(temporary).glob("test.before-restore-*.sqlite3"))
            report["checks"].append("backup_ui_export_cancel_restore_and_safety_copy")
            controller.closeSettings()
            controller.hidePanel()
            position = QPoint(runtime.star.x() - 110, runtime.star.y() + 30)
            runtime.star.setPosition(position)
            controller.settleStar()
            saved = runtime.star.position()
            runtime.star.setPosition(300, 300)
            runtime.desktop.restorePosition(runtime.star)
            assert runtime.star.position() == saved
            controller.hideStar()
            assert not runtime.star.isVisible()
            controller.revealStar()
            assert runtime.star.isVisible()
            report["checks"].append("settings_load_position_persistence_hide_reveal")

            class Clipboard:
                def text(self):
                    return "明天下午三点提交首版反馈"
            with patch("stardot.desktop.QApplication.clipboard", return_value=Clipboard()):
                runtime.desktop.captureClipboard()
            assert tasks.draftTime == "15:00"
            assert tasks.saveDraft()
            report["checks"].append("explicit_clipboard_capture")

            if args.native:
                native = DesktopServices(controller, tasks, Path(temporary) / "hotkeys.ini", app, enabled=True)
                assert len(native._ids) == 2, native.status
                old_ids = dict(native._ids)
                modifiers, key = hotkey_parts("Ctrl+Shift+S")
                blocker = 0x6010
                assert ctypes.windll.user32.RegisterHotKey(None, blocker, modifiers, key)
                try:
                    assert not native.applyShortcuts("Ctrl+Shift+S", "Ctrl+Alt+H")
                    assert native._ids == old_ids
                finally:
                    ctypes.windll.user32.UnregisterHotKey(None, blocker)
                calls = []
                key_id = native._ids["capture"][0]
                native.callbacks[key_id] = lambda: calls.append("capture")
                assert ctypes.windll.user32.PostThreadMessageW(ctypes.windll.kernel32.GetCurrentThreadId(), 0x312, key_id, 0)
                QTest.qWait(80)
                assert calls == ["capture"]
                class KeyboardInput(ctypes.Structure):
                    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
                class MouseInput(ctypes.Structure):
                    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
                class InputUnion(ctypes.Union):
                    _fields_ = [("ki", KeyboardInput), ("mi", MouseInput)]
                class Input(ctypes.Structure):
                    _fields_ = [("type", wintypes.DWORD), ("union", InputUnion)]
                events = (Input * 6)()
                for event, (key, flags) in zip(events, [(0x11, 0), (0x12, 0), (ord("S"), 0), (ord("S"), 2), (0x12, 2), (0x11, 2)]):
                    event.type = 1
                    event.union.ki = KeyboardInput(key, 0, flags, 0, 0)
                assert ctypes.windll.user32.SendInput(6, events, ctypes.sizeof(Input)) == 6
                QTest.qWait(120)
                assert calls == ["capture", "capture"], calls
                resumed = []
                native.resumed.connect(lambda: resumed.append(True))
                message = wintypes.MSG()
                message.message, message.wParam = 0x218, 0x12
                native.filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(message))
                assert resumed == [True]
                report["checks"].append("windows_registerhotkey_conflict_rollback_native_dispatch_resume")
                controller.hidePanel()
                report["calendar_cycle_samples"] = []
                report["before_cycles"] = memory_mb()
                for index in range(args.cycles):
                    controller.showCalendar()
                    QTest.qWait(45)
                    controller.closeCalendar()
                    app.sendPostedEvents(None, QEvent.DeferredDelete)
                    QTest.qWait(45)
                    if index in (14, 29, 59, 149, 299):
                        report["calendar_cycle_samples"].append({"cycles": index + 1, **memory_mb()})
                QTest.qWait(500)
                assert not [w for w in app.topLevelWindows() if w.objectName() == "calendarWindow"]
                report["after_calendar_cycles"] = memory_mb()
                runtime.engine.collectGarbage()
                app.sendPostedEvents(None, QEvent.DeferredDelete)
                QTest.qWait(100)
                report["after_qml_gc"] = memory_mb()
                start_cpu, start_wall = time.process_time(), time.perf_counter()
                QTest.qWait(10000)
                report["idle_cpu_one_core_percent"] = round(100 * (time.process_time() - start_cpu) / (time.perf_counter() - start_wall), 2)

            errors = [m for m in messages if "file:" in m or "Error" in m or "failed to load" in m.lower()]
            assert not errors, "\n".join(errors)
            report["ok"] = True
        finally:
            if native:
                native.close()
            tasks.cancelDraft()
            controller.closeCalendar()
            controller.closeSettings()
            controller.hidePanel()
            runtime.star.hide()
            runtime.tray.hide()
            runtime.desktop.close()
            runtime.reminders.timer.stop()
            runtime.store.close()
            # 此脚本不进入 app.exec；手动清理后避免 aboutToQuit 再次关闭存储。
            report["qt_messages"] = messages
            (output / ("native-check.json" if args.native else "ui-check.json")).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
