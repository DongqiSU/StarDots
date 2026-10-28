"""把 Python 任务序列转换为 QML ListView 可读取的模型。"""

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt
from datetime import datetime

from stardot.storage import Task
from stardot.text_processing import due_display


class TaskListModel(QAbstractListModel):
    ROLES = {
        Qt.UserRole + 1: b"taskId",
        Qt.UserRole + 2: b"body",
        Qt.UserRole + 3: b"completed",
        Qt.UserRole + 4: b"dueLabel",
        Qt.UserRole + 5: b"dueColor",
        Qt.UserRole + 6: b"dueFull",
        Qt.UserRole + 7: b"reminderMinutes",
        Qt.UserRole + 8: b"hasTime",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks: list[Task] = []
        self._now = datetime.now()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.tasks)

    def roleNames(self):
        return self.ROLES

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.tasks):
            return None
        task = self.tasks[index.row()]
        label, color, full = due_display(task.due_date, task.due_time, self._now)
        return {Qt.UserRole + 1: task.task_id, Qt.UserRole + 2: task.body,
                Qt.UserRole + 3: task.completed_at is not None,
                Qt.UserRole + 4: label, Qt.UserRole + 5: color, Qt.UserRole + 6: full,
                Qt.UserRole + 7: task.reminder_minutes, Qt.UserRole + 8: bool(task.due_time)}.get(role)

    def refresh_clock(self):
        self._now = datetime.now()
        if self.tasks:
            self.dataChanged.emit(self.index(0), self.index(len(self.tasks) - 1),
                                  [Qt.UserRole + 4, Qt.UserRole + 5, Qt.UserRole + 6])

    def replace(self, tasks: list[Task]) -> None:
        # 只通知改变的行，避免每次保存都重建整张清单、丢失滚动位置。
        target_ids = {task.task_id for task in tasks}
        for row in range(len(self.tasks) - 1, -1, -1):
            if self.tasks[row].task_id not in target_ids:
                self.beginRemoveRows(QModelIndex(), row, row)
                self.tasks.pop(row)
                self.endRemoveRows()
        for row, task in enumerate(tasks):
            current = next((i for i in range(row, len(self.tasks))
                            if self.tasks[i].task_id == task.task_id), None)
            if current is None:
                self.beginInsertRows(QModelIndex(), row, row)
                self.tasks.insert(row, task)
                self.endInsertRows()
            else:
                if current != row:
                    self.beginMoveRows(QModelIndex(), current, current, QModelIndex(), row)
                    self.tasks.insert(row, self.tasks.pop(current))
                    self.endMoveRows()
                if self.tasks[row] != task:
                    self.tasks[row] = task
                    self.dataChanged.emit(self.index(row), self.index(row), list(self.ROLES))

    def update_task(self, task: Task) -> None:
        """完成后先更新当前行，留出划线过渡时间，再移出待办列表。"""
        for row, current in enumerate(self.tasks):
            if current.task_id == task.task_id:
                self.tasks[row] = task
                self.dataChanged.emit(self.index(row), self.index(row), list(self.ROLES))
                break
