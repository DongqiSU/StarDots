from pathlib import Path
from contextlib import closing
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from stardot.storage import TaskStore


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "tasks.sqlite3"
        self.store = TaskStore(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_restart_preserves_body_original_and_archive(self):
        original = "明天下午讨论预算\n原始消息含 '引号' 和 😀"
        task = self.store.add(original, original)
        self.store.edit(task.task_id, "讨论预算")
        self.store.set_completed(task.task_id, "2026-09-16T10:00:00+00:00")
        self.store.close()
        self.store = TaskStore(self.path)
        saved = self.store.get(task.task_id)
        self.assertEqual(saved.body, "讨论预算")
        self.assertEqual(saved.original_text, original)
        self.assertIsNotNone(saved.completed_at)
        self.store.set_completed(task.task_id, None)
        self.assertIsNone(self.store.get(task.task_id).completed_at)
        self.assertEqual(len(self.store.list_tasks()), 1)

    def test_invalid_input_and_missing_edit_do_not_create_tasks(self):
        for body in ("", " \n\t", "字" * 20001):
            with self.assertRaises(ValueError):
                self.store.add(body, body)
        with self.assertRaises(ValueError):
            self.store.edit("missing", "保留")
        self.assertEqual(self.store.list_tasks(), [])

    def test_parameterized_sql_and_failed_write(self):
        text = "'); DROP TABLE tasks; --"
        task = self.store.add(text, text)
        self.assertEqual(self.store.get(task.task_id).body, text)
        with closing(sqlite3.connect(self.path)) as locker:
            locker.execute("BEGIN EXCLUSIVE")
            self.store.connection.execute("PRAGMA busy_timeout = 10")
            with self.assertRaises(sqlite3.OperationalError):
                self.store.add("不会假装成功", "")
        self.assertEqual(len(self.store.list_tasks()), 1)

    def test_newer_database_is_not_modified(self):
        newer = Path(self.temp.name) / "newer.sqlite3"
        with closing(sqlite3.connect(newer)) as connection:
            connection.execute("PRAGMA user_version = 99")
        with self.assertRaises(ValueError):
            TaskStore(newer)
        with closing(sqlite3.connect(newer)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 99)
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master").fetchall(), [])

    def test_delete_only_archived_and_undo_preserves_identity(self):
        task = self.store.add("归档后可删除", "原始文字")
        with self.assertRaises(ValueError):
            self.store.delete_archived(task.task_id)
        self.store.set_completed(task.task_id, "2026-09-16T10:00:00+00:00")
        snapshot = self.store.delete_archived(task.task_id)
        self.assertEqual(self.store.list_tasks(), [])
        self.store.restore_deleted(snapshot)
        self.assertEqual(self.store.get(task.task_id), snapshot)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.restore_deleted(snapshot)
        self.assertEqual(len(self.store.list_tasks()), 1)

    def test_v1_migration_keeps_records_and_creates_readable_backup(self):
        old = Path(self.temp.name) / "old.sqlite3"
        with closing(sqlite3.connect(old)) as connection:
            connection.execute("CREATE TABLE tasks (task_id TEXT PRIMARY KEY, body TEXT NOT NULL, original_text TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT)")
            connection.execute("INSERT INTO tasks VALUES ('existing', '旧任务', '原文', '2026-09-16', '2026-09-17')")
            connection.execute("PRAGMA user_version = 1")
            connection.commit()
        upgraded = TaskStore(old)
        self.assertEqual(upgraded.get("existing").original_text, "原文")
        self.assertIsNone(upgraded.get("existing").due_date)
        upgraded.edit("existing", "旧任务已编辑", "2028-02-29", "09:00")
        upgraded.close()
        reopened = TaskStore(old)
        self.assertEqual(reopened.get("existing").due_time, "09:00")
        reopened.close()
        backups = list(Path(self.temp.name).glob("old.before-v2-*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT body FROM tasks").fetchone()[0], "旧任务")


if __name__ == "__main__":
    unittest.main()
