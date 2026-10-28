"""本地提醒：按当前任务计算，持久化去重，唤醒后合并补提醒。"""

from datetime import datetime, timedelta
import sqlite3

from PySide6.QtCore import QObject, QTimer, Signal


def reminder_schedule(task):
    if task.completed_at or not task.due_date or not task.due_time or task.reminder_minutes < 0:
        return None
    due = datetime.fromisoformat(f"{task.due_date}T{task.due_time}")
    key = f"{task.due_date}T{task.due_time}/{task.reminder_minutes}"
    return due - timedelta(minutes=task.reminder_minutes), key


class ReminderService(QObject):
    failed = Signal(str)

    def __init__(self, store, notify, parent=None, *, now=datetime.now):
        super().__init__(parent)
        self.store, self.notify, self.now = store, notify, now
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.check)
        self._checking = False

    def start(self):
        self.timer.start(1000)

    def check(self):
        if self._checking:
            return
        self._checking = True
        delay = 60000
        try:
            now = self.now()
            pending = []
            for task in self.store.list_tasks():
                schedule = reminder_schedule(task)
                if not schedule:
                    continue
                when, key = schedule
                if self.store.connection.execute(
                    "SELECT 1 FROM reminder_log WHERE task_id = ? AND schedule = ?", (task.task_id, key)
                ).fetchone():
                    continue
                if when <= now:
                    pending.append((task, key))
                else:
                    delay = min(delay, max(100, int((when - now).total_seconds() * 1000)))
            if pending:
                # 先写入去重记录；发送失败则撤回记录。崩溃窗口内优先避免反复弹窗。
                keys = [(task.task_id, key) for task, key in pending]
                with self.store.connection:
                    self.store.connection.executemany("INSERT OR IGNORE INTO reminder_log VALUES (?, ?)", keys)
                try:
                    sent = self.notify([task for task, _ in pending])
                except Exception:
                    sent = False
                if not sent:
                    with self.store.connection:
                        self.store.connection.executemany("DELETE FROM reminder_log WHERE task_id = ? AND schedule = ?", keys)
        except (sqlite3.Error, ValueError, OverflowError) as error:
            self.failed.emit(f"提醒检查失败：{error}")
        finally:
            self._checking = False
            self.timer.start(delay)
