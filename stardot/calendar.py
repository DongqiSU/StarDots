"""日历仅是同一份任务的日期投影，不维护第二套数据。"""

from datetime import date, datetime, timedelta

from PySide6.QtCore import QObject, Property, Signal, Slot

from stardot.task_model import TaskListModel
from stardot.text_processing import due_display


class CalendarController(QObject):
    changed = Signal()

    def __init__(self, tasks, parent=None):
        super().__init__(parent)
        self.tasks = tasks
        self.month = date.today().replace(day=1)
        self.selected = date.today()
        self._day_model = TaskListModel(self)
        tasks.stateChanged.connect(self.refresh)
        tasks._clock_timer.timeout.connect(self.refresh)
        self.refresh()

    @Property(str, notify=changed)
    def monthLabel(self):
        return self.month.strftime("%Y 年 %m 月")

    @Property(str, notify=changed)
    def selectedDay(self):
        return self.selected.isoformat()

    @Property(QObject, constant=True)
    def dayModel(self):
        return self._day_model

    @Property("QVariantList", notify=changed)
    def days(self):
        start = self.month - timedelta(days=self.month.weekday())
        by_day = {}
        for task in self.tasks._all_tasks:
            if task.due_date:
                by_day.setdefault(task.due_date, []).append(task)
        result = []
        for i in range(42):
            day = start + timedelta(days=i)
            entries = sorted(by_day.get(day.isoformat(), []), key=lambda t: (bool(t.completed_at), t.due_time or "99:99", t.created_at))
            result.append({"day": day.isoformat(), "number": day.day,
                           "inMonth": day.month == self.month.month,
                           "today": day == date.today(), "count": len(entries),
                           "items": [{"taskId": t.task_id, "body": t.body,
                                      "completed": bool(t.completed_at), "time": t.due_time or "",
                                      "color": due_display(t.due_date, t.due_time, datetime.now())[1]} for t in entries[:2]]})
        return result

    def refresh(self):
        entries = [t for t in self.tasks._all_tasks if t.due_date == self.selected.isoformat()]
        self._day_model.replace(sorted(entries, key=lambda t: (bool(t.completed_at), t.due_time or "99:99", t.created_at)))
        self._day_model.refresh_clock()
        self.changed.emit()

    @Slot(int)
    def shiftMonth(self, step):
        index = self.month.year * 12 + self.month.month - 1 + max(-1, min(1, step))
        year, month = divmod(index, 12)
        if 1900 <= year <= 9998:
            self.month = date(year, month + 1, 1)
            self.refresh()

    @Slot()
    def today(self):
        self.selected = date.today()
        self.month = self.selected.replace(day=1)
        self.refresh()

    @Slot(str)
    def selectDay(self, day):
        self.selected = date.fromisoformat(day)
        self.refresh()

    @Slot(str, str)
    def editTask(self, day, task_id):
        if self.tasks.editTask(task_id):
            self.selectDay(day)

    @Slot()
    def newTask(self):
        if self.tasks.newTask():
            self.tasks.setDraftSchedule(self.selected.isoformat(), "")
