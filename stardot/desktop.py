"""Windows 热键及桌面设置；剪贴板只在用户触发快捷键时读取。"""

import ctypes
from ctypes import wintypes
from pathlib import Path
import sqlite3
import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Property, QSettings, Signal, Slot
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox


CAPTURE_KEYS = ("Ctrl+Alt+S", "Ctrl+Shift+S", "Ctrl+Alt+D")
REVEAL_KEYS = ("Ctrl+Alt+Space", "Ctrl+Shift+Space", "Ctrl+Alt+H")


def hotkey_parts(sequence):
    parts = sequence.split("+")
    modifiers = 0x4000
    for part in parts[:-1]:
        modifiers |= {"Ctrl": 2, "Alt": 1, "Shift": 4}[part]
    return modifiers, 0x20 if parts[-1] == "Space" else ord(parts[-1])


class NativeEvents(QAbstractNativeEventFilter):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def nativeEventFilter(self, event_type, message):
        if sys.platform == "win32" and bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x312:
                callback = self.owner.callbacks.get(int(msg.wParam))
                if callback:
                    callback()
                    return True, 0
            elif msg.message == 0x1E or (msg.message == 0x218 and msg.wParam in (7, 0x12)):
                self.owner.resumed.emit()
        return False, 0


class DesktopServices(QObject):
    changed = Signal()
    resumed = Signal()

    def __init__(self, controller, tasks, path: Path, parent=None, *, enabled=True):
        super().__init__(parent)
        self.controller, self.tasks = controller, tasks
        self.settings = QSettings(str(path), QSettings.IniFormat)
        self.enabled = enabled and sys.platform == "win32"
        self.callbacks = {}
        self._ids = {}
        self._next_id = 0x5300
        self._status = ""
        self._capture = self.settings.value("capture", CAPTURE_KEYS[0])
        self._reveal = self.settings.value("reveal", REVEAL_KEYS[0])
        self.filter = NativeEvents(self)
        if self.enabled:
            QApplication.instance().installNativeEventFilter(self.filter)
            self.applyShortcuts(self._capture, self._reveal)

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(str, notify=changed)
    def captureShortcut(self):
        return self._capture

    @Property(str, notify=changed)
    def revealShortcut(self):
        return self._reveal

    def report(self, message):
        self._status = message
        self.changed.emit()

    @Slot(str, str, result=bool)
    def applyShortcuts(self, capture, reveal):
        if capture not in CAPTURE_KEYS or reveal not in REVEAL_KEYS:
            self.report("请选择列表中的快捷键。")
            return False
        requested = {"capture": (capture, self.captureClipboard), "reveal": (reveal, self.controller.revealStar)}
        registrations = {}
        if self.enabled:
            for action, (sequence, callback) in requested.items():
                old = self._ids.get(action)
                if old and old[1] == sequence:
                    continue
                self._next_id += 1
                key_id = self._next_id
                modifiers, key = hotkey_parts(sequence)
                if not ctypes.windll.user32.RegisterHotKey(None, key_id, modifiers, key):
                    for registered, _, _ in registrations.values():
                        ctypes.windll.user32.UnregisterHotKey(None, registered)
                    self.report(f"{sequence} 已被占用，原有快捷键保持不变。请换一组。")
                    return False
                registrations[action] = (key_id, sequence, callback)
            for action, (key_id, sequence, callback) in registrations.items():
                old = self._ids.get(action)
                if old:
                    ctypes.windll.user32.UnregisterHotKey(None, old[0])
                    self.callbacks.pop(old[0], None)
                self._ids[action] = (key_id, sequence)
                self.callbacks[key_id] = callback
        self._capture, self._reveal = capture, reveal
        self.settings.setValue("capture", capture)
        self.settings.setValue("reveal", reveal)
        self.settings.sync()
        self.report("快捷键已保存。" if self.settings.status() == QSettings.NoError else "快捷键已生效，但设置未能写入磁盘。")
        return True

    @Slot()
    def captureClipboard(self):
        self.controller.revealStar()
        text = QApplication.clipboard().text()
        if text.strip():
            self.tasks.receiveText(text)
        else:
            self.controller.showEditor()
            self.tasks._notify("请先复制文字，再按录入快捷键。", error=True)

    def savePosition(self, star, screen):
        area = screen.availableGeometry()
        self.settings.setValue("star/screen", screen.name())
        self.settings.setValue("star/x", (star.x() - area.x()) / max(1, area.width()))
        self.settings.setValue("star/y", (star.y() - area.y()) / max(1, area.height()))
        self.settings.sync()

    def restorePosition(self, star):
        if not self.settings.contains("star/x"):
            return
        screens = QApplication.screens()
        screen = next((s for s in screens if s.name() == self.settings.value("star/screen")), QApplication.primaryScreen())
        if screen:
            area = screen.availableGeometry()
            try:
                x, y = float(self.settings.value("star/x")), float(self.settings.value("star/y"))
                star.setPosition(area.x() + round(x * area.width()), area.y() + round(y * area.height()))
            except (TypeError, ValueError, OverflowError):
                pass

    @Slot()
    def exportBackup(self):
        QApplication.inputMethod().commit()
        if not self.tasks.finishDraft():
            return
        filename, _ = QFileDialog.getSaveFileName(None, "导出星点备份", "Stardot-backup.sqlite3", "星点备份 (*.sqlite3)")
        if filename:
            try:
                self.tasks.store.export_backup(Path(filename))
                self.report(f"已导出：{filename}")
            except (OSError, sqlite3.Error, ValueError) as error:
                self.report(f"导出失败：{error}")

    @Slot()
    def importBackup(self):
        QApplication.inputMethod().commit()
        if not self.tasks.finishDraft():
            return
        filename, _ = QFileDialog.getOpenFileName(None, "恢复星点备份", "", "星点备份 (*.sqlite3)")
        if not filename:
            return
        try:
            items, _ = self.tasks.store.read_backup(Path(filename))
            answer = QMessageBox.question(None, "恢复备份", f"备份包含 {len(items)} 条任务。\n恢复将替换当前任务，现有数据会先自动备份。\n\n继续恢复？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
            safety = self.tasks.store.restore_backup(Path(filename))
            self.tasks.reload()
            self.report(f"已恢复 {len(items)} 条任务。恢复前备份：{safety}")
        except (OSError, sqlite3.Error, ValueError) as error:
            self.report(f"恢复失败，当前数据未替换：{error}")

    def close(self):
        if self.enabled:
            for key_id, _ in self._ids.values():
                ctypes.windll.user32.UnregisterHotKey(None, key_id)
            QApplication.instance().removeNativeEventFilter(self.filter)
        self.settings.sync()
