"""SQLite 存储：参数化 SQL，事务成功后才返回任务。"""

from dataclasses import dataclass
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from stardot.text_processing import validate_schedule


MAX_BODY_LENGTH = 20000


@dataclass(frozen=True)
class Task:
    task_id: str
    body: str
    original_text: str
    created_at: str
    completed_at: str | None = None
    due_date: str | None = None
    due_time: str | None = None
    reminder_minutes: int = 10


class TaskStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=1)
        self.connection.row_factory = sqlite3.Row
        try:
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3):
                raise ValueError("数据版本较新，请使用更新版本的 Stardot。")
            if version < 2:
                existing = self.connection.execute(
                    "SELECT name FROM sqlite_master WHERE name = 'tasks'"
                ).fetchone()
                if existing:
                    # 升级前用 SQLite 自身的备份接口保留一致的旧库，不覆盖已有备份。
                    backup = path.with_name(f"{path.stem}.before-v2-{uuid4().hex[:8]}.sqlite3")
                    with closing(sqlite3.connect(backup)) as destination:
                        self.connection.backup(destination)
                self.connection.execute("BEGIN IMMEDIATE")
                self.connection.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        body TEXT NOT NULL,
                        original_text TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        completed_at TEXT,
                        due_date TEXT,
                        due_time TEXT
                    )
                """)
                columns = {row[1] for row in self.connection.execute("PRAGMA table_info(tasks)")}
                for column in ("due_date", "due_time"):
                    if column not in columns:
                        self.connection.execute(f"ALTER TABLE tasks ADD COLUMN {column} TEXT")
                self.connection.execute("PRAGMA user_version = 2")
                self.connection.commit()
            # 对已经标记为 v2 的数据库也检查结构；不自动清空异常数据。
            self.connection.execute("SELECT task_id, body, original_text, created_at, completed_at, due_date, due_time FROM tasks LIMIT 0")
            if version < 3:
                if version == 2:
                    with closing(sqlite3.connect(path.with_name(f"{path.stem}.before-v3-{uuid4().hex[:8]}.sqlite3"))) as destination:
                        self.connection.backup(destination)
                with self.connection:
                    self.connection.execute("BEGIN IMMEDIATE")
                    self.connection.execute("ALTER TABLE tasks ADD COLUMN reminder_minutes INTEGER NOT NULL DEFAULT 10")
                    self.connection.execute("CREATE TABLE reminder_log (task_id TEXT NOT NULL, schedule TEXT NOT NULL, PRIMARY KEY(task_id, schedule))")
                    # 旧任务不自动开启提醒，避免升级时突然补发历史任务。
                    if version in (1, 2):
                        self.connection.execute("UPDATE tasks SET reminder_minutes = -1")
                    self.connection.execute("PRAGMA user_version = 3")
            self.connection.execute("SELECT reminder_minutes FROM tasks LIMIT 0")
            self.connection.execute("SELECT task_id, schedule FROM reminder_log LIMIT 0")
        except Exception:
            self.connection.rollback()
            self.connection.close()
            raise

    @staticmethod
    def validate_body(body: str) -> str:
        body = body.strip()
        if not body:
            raise ValueError("写下一件小事，再保存吧。")
        if len(body) > MAX_BODY_LENGTH:
            raise ValueError(f"任务文字不能超过 {MAX_BODY_LENGTH} 字，请精简后再保存。")
        return body

    def list_tasks(self) -> list[Task]:
        rows = self.connection.execute(
            "SELECT * FROM tasks ORDER BY COALESCE(completed_at, created_at) DESC, task_id"
        ).fetchall()
        return [Task(**dict(row)) for row in rows]

    def get(self, task_id: str) -> Task:
        row = self.connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise ValueError("这条任务已不存在。")
        return Task(**dict(row))

    def add(self, body: str, original_text: str, due_date=None, due_time=None, reminder_minutes=10) -> Task:
        self.validate_reminder(reminder_minutes)
        due_date, due_time = validate_schedule(due_date, due_time)
        task = Task(uuid4().hex, self.validate_body(body), original_text,
                    datetime.now(timezone.utc).isoformat(), None, due_date, due_time, reminder_minutes)
        with self.connection:
            self.connection.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(vars(task).values()),
            )
        return task

    def edit(self, task_id: str, body: str, due_date=None, due_time=None, reminder_minutes=None) -> Task:
        if reminder_minutes is None:
            reminder_minutes = self.get(task_id).reminder_minutes
        self.validate_reminder(reminder_minutes)
        body = self.validate_body(body)
        due_date, due_time = validate_schedule(due_date, due_time)
        with self.connection:
            if self.connection.execute(
                "UPDATE tasks SET body = ?, due_date = ?, due_time = ?, reminder_minutes = ? WHERE task_id = ?",
                (body, due_date, due_time, reminder_minutes, task_id)
            ).rowcount != 1:
                raise ValueError("这条任务已不存在。")
        return self.get(task_id)

    def set_completed(self, task_id: str, completed_at: str | None) -> Task:
        with self.connection:
            if self.connection.execute(
                "UPDATE tasks SET completed_at = ? WHERE task_id = ?", (completed_at, task_id)
            ).rowcount != 1:
                raise ValueError("这条任务已不存在。")
        return self.get(task_id)

    def close(self) -> None:
        self.connection.close()

    def delete_archived(self, task_id: str) -> Task:
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            task = self.get(task_id)
            if task.completed_at is None:
                raise ValueError("仅已归档的任务可以删除。")
            self.connection.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        return task

    def restore_deleted(self, task: Task) -> Task:
        with self.connection:
            self.connection.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(vars(task).values()),
            )
        return task

    @staticmethod
    def validate_reminder(minutes):
        if type(minutes) is not int or minutes not in (-1, 0, 10, 30):
            raise ValueError("提醒可选关闭、准时、提前 10 分钟或 30 分钟。")

    def export_backup(self, destination: Path):
        if destination.resolve() == self.path.resolve():
            raise ValueError("请选择其他文件，不能覆盖正在使用的数据库。")
        temporary = destination.with_name(destination.name + f".{uuid4().hex}.tmp")
        try:
            with closing(sqlite3.connect(temporary)) as output:
                self.connection.backup(output)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def read_backup(cls, source: Path):
        """只读取已知字段，绝不在工作数据库中执行导入文件里的 SQL。"""
        if not source.is_file() or source.stat().st_size > 100 * 1024 * 1024:
            raise ValueError("请选择小于 100 MB 的 Stardot 数据备份。")
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("备份文件损坏。")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (1, 2, 3):
                raise ValueError("不支持此备份版本。")
            if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('view', 'trigger')").fetchone():
                raise ValueError("备份包含不支持的数据结构。")
            records = db.execute("SELECT * FROM tasks LIMIT 100001").fetchall()
            if len(records) > 100000:
                raise ValueError("备份任务数量超出上限。")
            tasks = []
            ids = set()
            for record in records:
                data = dict(record)
                data.setdefault("due_date", None)
                data.setdefault("due_time", None)
                data.setdefault("reminder_minutes", -1)
                try:
                    task = Task(**data)
                    if not isinstance(task.task_id, str) or not task.task_id or task.task_id in ids:
                        raise ValueError("任务标识无效。")
                    if not isinstance(task.body, str) or not isinstance(task.original_text, str) or len(task.original_text) > MAX_BODY_LENGTH:
                        raise ValueError("任务文字无效。")
                    cls.validate_body(task.body)
                    validate_schedule(task.due_date, task.due_time)
                    cls.validate_reminder(task.reminder_minutes)
                    datetime.fromisoformat(task.created_at)
                    if task.completed_at is not None:
                        datetime.fromisoformat(task.completed_at)
                except (TypeError, ValueError) as error:
                    raise ValueError("备份中的任务数据无效。") from error
                ids.add(task.task_id)
                tasks.append(task)
            log = []
            if version == 3:
                log = [(r[0], r[1]) for r in db.execute("SELECT task_id, schedule FROM reminder_log LIMIT 1000000")
                       if r[0] in ids and isinstance(r[1], str)]
            return tasks, log

    def restore_backup(self, source: Path):
        tasks, log = self.read_backup(source)
        safety = self.path.with_name(f"{self.path.stem}.before-restore-{uuid4().hex[:8]}.sqlite3")
        self.export_backup(safety)
        with self.connection:
            self.connection.execute("DELETE FROM tasks")
            self.connection.execute("DELETE FROM reminder_log")
            self.connection.executemany("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                        [tuple(vars(task).values()) for task in tasks])
            self.connection.executemany("INSERT OR IGNORE INTO reminder_log VALUES (?, ?)", log)
        return safety
