"""任务应用层：编辑草稿 → 存储事务 → 更新界面；失败保留草稿。"""

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3

from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer

from stardot.storage import MAX_BODY_LENGTH, Task, TaskStore
from stardot.task_model import TaskListModel
from stardot.text_processing import capture_text, parse_schedule, validate_schedule, shift_schedule


@dataclass(frozen=True)
class UndoAction:
    kind: str
    task: Task


class TaskController(QObject):
    stateChanged = Signal()
    draftChanged = Signal()
    messageChanged = Signal()
    editorRequested = Signal()
    feedback = Signal(str)

    def __init__(self, store: TaskStore, parent=None):
        super().__init__(parent)
        self.store = store
        self._model = TaskListModel(self)
        self._all_tasks = store.list_tasks()
        self._archive = False
        self._draft_visible = False
        self._draft_body = ""
        self._original = ""
        self._editing_id = ""
        self._summary_pending = False
        self._due_date = self._due_time = None
        self._reminder_minutes = 10
        self._date_manually_set = False
        self._parse_note = ""
        self._reference = datetime.now()
        self._parse_timer = QTimer(self)
        self._parse_timer.setSingleShot(True)
        self._parse_timer.setInterval(350)
        self._parse_timer.timeout.connect(self._recognize_date)
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(60000)
        self._clock_timer.timeout.connect(self._model.refresh_clock)
        self._message = ""
        self._error = False
        self._undo: UndoAction | None = None
        self._message_timer = QTimer(self)
        self._message_timer.setSingleShot(True)
        self._message_timer.setInterval(6000)
        self._message_timer.timeout.connect(self.dismissMessage)
        self._refresh_model()

    @Property(QObject, constant=True)
    def taskModel(self):
        return self._model

    @Property(bool, notify=stateChanged)
    def archiveVisible(self):
        return self._archive

    @Property(int, notify=stateChanged)
    def activeCount(self):
        return sum(task.completed_at is None for task in self._all_tasks)

    @Property(int, notify=stateChanged)
    def archivedCount(self):
        return sum(task.completed_at is not None for task in self._all_tasks)

    @Property(bool, notify=draftChanged)
    def draftVisible(self):
        return self._draft_visible

    @Property(str, notify=draftChanged)
    def draftBody(self):
        return self._draft_body

    @Property(str, notify=draftChanged)
    def originalText(self):
        return self._original

    @Property(bool, notify=draftChanged)
    def editing(self):
        return bool(self._editing_id)

    @Property(bool, notify=draftChanged)
    def summaryPending(self):
        return self._summary_pending

    @Property(str, notify=draftChanged)
    def draftDate(self):
        return self._due_date or ""

    @Property(str, notify=draftChanged)
    def draftTime(self):
        return self._due_time or ""

    @Property(int, notify=draftChanged)
    def draftReminder(self):
        return self._reminder_minutes

    @Slot(int)
    def setDraftReminder(self, minutes):
        try:
            self.store.validate_reminder(minutes)
            self._reminder_minutes = minutes
            self.draftChanged.emit()
        except ValueError as error:
            self._failure(error)

    @Slot(str, int)
    def setTaskReminder(self, task_id, minutes):
        try:
            task = self.store.get(task_id)
            self._updated(self.store.edit(task_id, task.body, task.due_date, task.due_time, minutes))
            if self._editing_id == task_id:
                self._reminder_minutes = minutes
                self.draftChanged.emit()
        except (sqlite3.Error, ValueError) as error:
            self._failure(error)

    def reload(self):
        self.cancelDraft()
        self.dismissMessage()
        self._all_tasks = self.store.list_tasks()
        self._refresh_model()

    @Property(str, notify=draftChanged)
    def parseNote(self):
        return self._parse_note

    @Slot(bool)
    def setPanelVisible(self, visible):
        if visible:
            self._model.refresh_clock()
            self._clock_timer.start()
        else:
            self._clock_timer.stop()

    @Property(str, notify=messageChanged)
    def message(self):
        return self._message

    @Property(bool, notify=messageChanged)
    def isError(self):
        return self._error

    @Property(bool, notify=messageChanged)
    def canUndo(self):
        return self._undo is not None

    def _refresh_model(self):
        self._model.replace([task for task in self._all_tasks
                             if (task.completed_at is not None) == self._archive])
        self.stateChanged.emit()

    def _updated(self, task, refresh=True):
        self._all_tasks = [task if old.task_id == task.task_id else old for old in self._all_tasks]
        self._all_tasks.sort(key=lambda item: item.completed_at or item.created_at, reverse=True)
        if refresh:
            self._refresh_model()
        else:
            self.stateChanged.emit()

    def _notify(self, text, error=False, undo=None):
        self._message, self._error, self._undo = text, error, undo
        self.messageChanged.emit()
        # 提示都应自行消失；有撤销操作时留出更长的操作时间。
        self._message_timer.start(6000 if undo else (3500 if error else 1800))

    def _failure(self, error):
        message = str(error) if isinstance(error, ValueError) else "保存失败，内容已保留。请检查磁盘或稍后重试。"
        self._notify(message, error=True, undo=self._undo)

    @Slot()
    def dismissMessage(self):
        self._message_timer.stop()
        self._message, self._undo = "", None
        self._error = False
        self.messageChanged.emit()

    @Slot()
    def toggleArchive(self):
        if not self.finishDraft():
            return
        self._archive = not self._archive
        self._refresh_model()

    @Slot(result=bool)
    def newTask(self):
        if not self.finishDraft():
            return False
        self._reference = datetime.now()
        self._show_draft()
        return True

    def _show_draft(self):
        self._archive = False
        self._refresh_model()
        self._draft_visible = True
        self.draftChanged.emit()
        self.editorRequested.emit()

    @Slot(str)
    def setDraftText(self, text):
        if text != self._draft_body:
            self._draft_body = text
            self._summary_pending = False
            if not self._date_manually_set:
                self._parse_timer.start()
            self.draftChanged.emit()

    @Slot()
    def acceptSummary(self):
        if self._summary_pending:
            self._summary_pending = False
            self.draftChanged.emit()

    def _recognize_date(self):
        if self._draft_visible and not self._date_manually_set:
            self._due_date, self._due_time, self._parse_note = parse_schedule(self._draft_body, self._reference)
            self.draftChanged.emit()

    @Slot(str, str, result=bool)
    def setDraftSchedule(self, day, time):
        try:
            self._due_date, self._due_time = validate_schedule(day or None, time or None)
        except ValueError as error:
            self._failure(error)
            return False
        self._date_manually_set = True
        self._parse_note = ""
        self._parse_timer.stop()
        self.draftChanged.emit()
        return True

    @Slot()
    def clearDraftSchedule(self):
        self.setDraftSchedule("", "")

    @Slot(str, int)
    def adjustSchedule(self, part, step):
        if not self._due_date:
            return
        try:
            day, time = shift_schedule(self._due_date, self._due_time, part, max(-1, min(step, 1)))
            self.setDraftSchedule(day, time or "")
        except (ValueError, OverflowError):
            self._notify("日期超出支持范围。", error=True)

    @Slot()
    def cancelDraft(self):
        self._parse_timer.stop()
        self._draft_visible = False
        self._draft_body = self._original = self._editing_id = ""
        self._summary_pending = self._date_manually_set = False
        self._due_date = self._due_time = None
        self._reminder_minutes = 10
        self._parse_note = ""
        self.draftChanged.emit()

    @Slot(str, result=bool)
    def receiveText(self, text):
        if not text.strip() or len(text) > MAX_BODY_LENGTH:
            self._notify("请选择 1～20000 字的文字再拖入。", error=True)
            return False
        if self._draft_visible and self._draft_body.strip():
            self._notify("请先保存或取消当前编辑，再拖入新内容。", error=True)
            self.editorRequested.emit()
            return False
        self._reference = datetime.now()
        capture = capture_text(text, self._reference)
        self._draft_body, self._original = capture.body, text
        self._due_date, self._due_time, self._parse_note = capture.due_date, capture.due_time, capture.note
        self._summary_pending = True
        self._date_manually_set = False
        self._parse_timer.stop()
        self._editing_id = ""
        self._draft_visible = True
        self._show_draft()
        self.feedback.emit("received")
        return True

    @Slot(str, result=bool)
    def editTask(self, task_id):
        same_task = self._draft_visible and self._editing_id == task_id
        try:
            # 先确认目标存在，再保存当前草稿，防止失效卡片触发意外关闭。
            task = self.store.get(task_id)
        except (sqlite3.Error, ValueError) as error:
            self._failure(error)
            return False
        if not self.finishDraft():
            return False
        if same_task:
            return True
        self._editing_id, self._draft_body, self._original = task.task_id, task.body, task.original_text
        self._due_date, self._due_time = task.due_date, task.due_time
        self._reminder_minutes = task.reminder_minutes
        self._date_manually_set = True
        self._summary_pending = False
        self._parse_note = ""
        self._parse_timer.stop()
        self._draft_visible = True
        self.draftChanged.emit()
        self.editorRequested.emit()
        return True

    @Slot(result=bool)
    def finishDraft(self):
        """离开编辑区的共同出口：空白新建直接关闭，其余必须保存成功。"""
        if not self._draft_visible:
            return True
        if not self._editing_id and not self._draft_body.strip():
            self.cancelDraft()
            return True
        return self.saveDraft()

    @Slot(result=bool)
    def saveDraft(self):
        if not self._draft_visible:
            return False
        # 快速按保存时也使用最新文字；手动改过／取消过日期则不会重新识别。
        if self._parse_timer.isActive():
            self._parse_timer.stop()
            self._recognize_date()
        try:
            if self._editing_id:
                task = self.store.edit(self._editing_id, self._draft_body, self._due_date, self._due_time, self._reminder_minutes)
                self._updated(task)
            else:
                task = self.store.add(self._draft_body, self._original or self._draft_body, self._due_date, self._due_time, self._reminder_minutes)
                self._all_tasks.insert(0, task)
                self._archive = False
                self._refresh_model()
        except (sqlite3.Error, ValueError) as error:
            self._failure(error)
            return False
        self.cancelDraft()
        self._notify("已保存")
        return True

    @Slot(str, result=bool)
    def completeTask(self, task_id):
        return self._change_completion(task_id, True)

    @Slot(str, result=bool)
    def restoreTask(self, task_id):
        return self._change_completion(task_id, False)

    def _change_completion(self, task_id, complete):
        try:
            before = self.store.get(task_id)
            if (before.completed_at is not None) == complete:
                return False
            task = self.store.set_completed(
                task_id, datetime.now(timezone.utc).isoformat() if complete else None
            )
        except (sqlite3.Error, ValueError) as error:
            self._failure(error)
            return False
        # 数据已经提交，先在原卡片上显示划线，再刷新归档分组。
        if complete:
            self._updated(task, refresh=False)
            self._model.update_task(task)
            self.feedback.emit("completed")
            QTimer.singleShot(220, self, self._refresh_model)
        else:
            self._updated(task)
        self._notify("已归档" if complete else "已恢复", undo=UndoAction("completion", before))
        return True

    @Slot(str, result=bool)
    def deleteTask(self, task_id):
        if self._draft_visible and self._editing_id == task_id:
            self._notify("请先保存或取消当前编辑，再删除任务。", error=True)
            return False
        try:
            task = self.store.delete_archived(task_id)
        except (sqlite3.Error, ValueError) as error:
            self._failure(error)
            return False
        self._all_tasks = [item for item in self._all_tasks if item.task_id != task_id]
        self._refresh_model()
        self._notify("已删除", undo=UndoAction("delete", task))
        return True

    @Slot()
    def undo(self):
        if self._undo is None:
            return
        action = self._undo
        try:
            if action.kind == "delete":
                task = self.store.restore_deleted(action.task)
                self._all_tasks.append(task)
            else:
                task = self.store.set_completed(action.task.task_id, action.task.completed_at)
        except (sqlite3.Error, ValueError) as error:
            self._failure(error)
            return
        self._updated(task)
        self._notify("已撤销")
