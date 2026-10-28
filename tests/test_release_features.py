from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtCore import QCoreApplication

from stardot.storage import TaskStore
from stardot.tasks import TaskController
from stardot.calendar import CalendarController
from stardot.reminders import ReminderService


class ReleaseFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.path = Path(self.directory.name)
        self.store = TaskStore(self.path / "test.sqlite3")
        self.clock = datetime(2026, 9, 20, 14, 49)
        self.notifications = []
        self.reminders = ReminderService(self.store, self.notify, now=lambda: self.clock)

    def notify(self, tasks):
        self.notifications.append([t.task_id for t in tasks])
        return True

    def tearDown(self):
        self.reminders.timer.stop()
        self.store.close()
        self.directory.cleanup()

    def test_reminders_due_catchup_restart_and_no_time(self):
        task = self.store.add("提交", "原文", "2026-09-20", "15:00")
        self.store.add("仅日期", "", "2026-09-20")
        self.store.add("无时间", "")
        self.store.add("关闭", "", "2026-09-20", "15:00", -1)
        self.reminders.check()
        self.assertEqual(self.notifications, [])
        self.clock = datetime(2026, 9, 20, 14, 50)
        self.reminders.check()
        self.assertEqual(self.notifications, [[task.task_id]])
        second = self.store.add("第二件", "", "2026-09-20", "16:00", 30)
        third = self.store.add("第三件", "", "2026-09-20", "17:00", 0)
        self.clock = datetime(2026, 9, 21, 9)
        self.reminders.check()
        self.assertEqual(set(self.notifications[1]), {second.task_id, third.task_id})
        reopened = TaskStore(self.store.path)
        try:
            service = ReminderService(reopened, self.notify, now=lambda: self.clock)
            service.check()
            service.timer.stop()
            self.assertEqual(len(self.notifications), 2)
        finally:
            reopened.close()

    def test_reminder_edit_complete_delete_and_failed_delivery(self):
        task = self.store.add("调整", "", "2026-09-20", "15:00")
        self.store.edit(task.task_id, "调整", "2026-09-21", "15:00")
        self.clock = datetime(2026, 9, 20, 15)
        self.reminders.check()
        self.assertEqual(self.notifications, [])
        self.store.set_completed(task.task_id, self.clock.isoformat())
        self.clock = datetime(2026, 9, 21, 15)
        self.reminders.check()
        self.assertEqual(self.notifications, [])
        snapshot = self.store.delete_archived(task.task_id)
        self.reminders.check()
        self.assertEqual(self.notifications, [])
        self.store.restore_deleted(snapshot)
        self.store.set_completed(task.task_id, None)
        self.reminders.notify = lambda _: False
        self.reminders.check()
        self.assertEqual(self.store.connection.execute("SELECT COUNT(*) FROM reminder_log").fetchone()[0], 0)
        self.reminders.notify = self.notify
        self.reminders.check()
        self.reminders.check()
        self.assertEqual(self.notifications, [[task.task_id]])
        self.store.edit(task.task_id, "调整", "2026-09-21", "16:00", 30)
        self.clock = datetime(2026, 9, 21, 15, 30)
        self.reminders.check()
        self.assertEqual(len(self.notifications), 2)

    def test_backup_round_trip_with_reminder_log_and_safety_copy(self):
        task = self.store.add("有时间", "原文", "2026-09-20", "14:00", 30)
        self.reminders.check()
        backup = self.path / "备份.sqlite3"
        self.store.export_backup(backup)
        later = self.store.add("备份之后新增", "")
        safety = self.store.restore_backup(backup)
        self.assertEqual(self.store.list_tasks(), [task])
        self.assertIn(later.task_id, [t.task_id for t in TaskStore.read_backup(safety)[0]])
        self.reminders.check()
        self.assertEqual(self.notifications, [[task.task_id]])
        with self.assertRaises(ValueError):
            self.store.export_backup(self.store.path)

    def test_invalid_backup_and_failed_restore_do_not_replace_data(self):
        task = self.store.add("保留", "")
        bad = self.path / "bad.sqlite3"
        bad.write_text("not a database")
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.restore_backup(bad)
        self.assertEqual(self.store.list_tasks(), [task])
        good = self.path / "good.sqlite3"
        self.store.export_backup(good)
        with closing(sqlite3.connect(good)) as db:
            db.execute("UPDATE tasks SET due_date = 'invalid'")
            db.commit()
        with self.assertRaises(ValueError):
            self.store.restore_backup(good)
        self.assertEqual(self.store.list_tasks(), [task])
        self.store.export_backup(good)
        with closing(sqlite3.connect(self.store.path)) as locker:
            locker.execute("BEGIN IMMEDIATE")
            self.store.connection.execute("PRAGMA busy_timeout = 10")
            with self.assertRaises(sqlite3.OperationalError):
                self.store.restore_backup(good)
        self.assertEqual(self.store.list_tasks(), [task])

    def test_v2_upgrade_keeps_tasks_and_disables_historical_reminders(self):
        old = self.path / "old.sqlite3"
        with closing(sqlite3.connect(old)) as db:
            db.execute("CREATE TABLE tasks(task_id TEXT PRIMARY KEY, body TEXT, original_text TEXT, created_at TEXT, completed_at TEXT, due_date TEXT, due_time TEXT)")
            db.execute("INSERT INTO tasks VALUES ('old', '旧任务', '原文', '2026-09-19', NULL, '2026-09-20', '15:00')")
            db.execute("PRAGMA user_version = 2")
            db.commit()
        upgraded = TaskStore(old)
        try:
            self.assertEqual(upgraded.get("old").reminder_minutes, -1)
            self.assertEqual(upgraded.connection.execute("PRAGMA user_version").fetchone()[0], 3)
            self.assertEqual(len(list(self.path.glob("old.before-v3-*.sqlite3"))), 1)
        finally:
            upgraded.close()

    def test_calendar_days_overflow_shared_edits_and_new_date(self):
        for i in range(4):
            self.store.add(f"闰日任务{i}", "", "2028-02-29", "15:00")
        self.store.add("无日期", "")
        tasks = TaskController(self.store)
        calendar = CalendarController(tasks)
        calendar.month = datetime(2028, 2, 1).date()
        calendar.selectDay("2028-02-29")
        days = calendar.days
        self.assertEqual(len(days), 42)
        self.assertEqual(datetime.fromisoformat(days[0]["day"]).weekday(), 0)
        cell = next(d for d in days if d["day"] == "2028-02-29")
        self.assertEqual(cell["count"], 4)
        self.assertEqual(len(cell["items"]), 2)
        self.assertEqual(calendar.dayModel.rowCount(), 4)
        first = calendar.dayModel.tasks[0]
        calendar.editTask("2028-02-29", first.task_id)
        tasks.setDraftText("日历改动")
        tasks.setDraftReminder(30)
        tasks.saveDraft()
        self.assertEqual(self.store.get(first.task_id).body, "日历改动")
        self.assertEqual(self.store.get(first.task_id).reminder_minutes, 30)
        calendar.newTask()
        self.assertEqual(tasks.draftDate, "2028-02-29")
        self.assertEqual(tasks.draftTime, "")
        tasks.cancelDraft()
        tasks.dismissMessage()
