from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QTest

from stardot.storage import TaskStore
from stardot.tasks import TaskController


class TaskControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store = TaskStore(Path(self.temp.name) / "tasks.sqlite3")
        self.tasks = TaskController(self.store)

    def tearDown(self):
        self.tasks.cancelDraft()
        self.tasks.deleteLater()
        QCoreApplication.processEvents()
        self.store.close()
        self.temp.cleanup()

    def test_summary_confirmation_does_not_save_or_confirm_date(self):
        text = "大家好！\n任务：明天下午三点带预算表开会。\n谢谢大家！"
        self.assertTrue(self.tasks.receiveText(text))
        self.assertTrue(self.tasks.summaryPending)
        self.assertEqual(self.tasks.draftBody, "明天下午三点带预算表开会。")
        self.assertEqual(self.tasks.draftDate, (date.today() + timedelta(days=1)).isoformat())
        self.assertEqual(self.tasks.draftTime, "15:00")
        self.tasks.acceptSummary()
        self.assertFalse(self.tasks.summaryPending)
        self.assertEqual(self.tasks.activeCount, 0)
        self.assertTrue(self.tasks.saveDraft())
        self.assertEqual(self.store.list_tasks()[0].original_text, text)

    def test_direct_save_and_cancelled_date_not_reintroduced(self):
        self.tasks.receiveText("提醒：后天下午两点带文件。谢谢！")
        self.assertTrue(self.tasks.saveDraft())  # 可以直接保存灰色候选。
        saved = self.store.list_tasks()[0]
        self.assertEqual(saved.due_time, "14:00")
        self.tasks.receiveText("明天15:00开会")
        self.tasks.clearDraftSchedule()
        self.tasks.setDraftText("明天16:00开会，带预算表")
        QTest.qWait(400)
        self.assertEqual(self.tasks.draftDate, "")
        self.assertTrue(self.tasks.saveDraft())
        self.assertIsNone(self.store.list_tasks()[0].due_date)

    def test_manual_date_and_editing_existing_task_are_not_overwritten(self):
        self.tasks.receiveText("明天15:00开会")
        self.tasks.setDraftSchedule("2028-02-29", "23:59")
        self.tasks.adjustSchedule("minute", 1)
        self.assertEqual((self.tasks.draftDate, self.tasks.draftTime), ("2028-03-01", "00:00"))
        self.tasks.setDraftText("后天16:00开会")
        QTest.qWait(400)
        self.assertEqual(self.tasks.draftDate, "2028-03-01")
        self.tasks.saveDraft()
        task = self.store.list_tasks()[0]
        self.tasks.editTask(task.task_id)
        self.tasks.setDraftText("明天14:00开会")
        self.tasks.saveDraft()
        self.assertEqual(self.store.get(task.task_id).due_date, "2028-03-01")

    def test_manual_input_fast_save_flushes_pending_date_parse(self):
        self.tasks.newTask()
        self.tasks.setDraftText("下周一上午九点交稿")
        self.assertTrue(self.tasks.saveDraft())
        self.assertEqual(self.store.list_tasks()[0].due_time, "09:00")

    def test_delete_failure_and_undo_preserve_all_fields(self):
        task = self.store.add("归档任务", "原文", "2028-01-31", "15:00")
        self.store.set_completed(task.task_id, "2026-09-16T10:00:00+00:00")
        self.tasks.deleteLater()
        self.tasks = TaskController(self.store)
        self.store.connection.execute("PRAGMA query_only = ON")
        self.assertFalse(self.tasks.deleteTask(task.task_id))
        self.assertEqual(self.tasks.archivedCount, 1)
        self.store.connection.execute("PRAGMA query_only = OFF")
        self.assertTrue(self.tasks.deleteTask(task.task_id))
        self.assertEqual(self.tasks.archivedCount, 0)
        self.tasks.undo()
        self.assertEqual(self.tasks.archivedCount, 1)
        restored = self.store.get(task.task_id)
        self.assertEqual((restored.original_text, restored.due_date, restored.due_time),
                         ("原文", "2028-01-31", "15:00"))

    def test_click_same_card_saves_and_closes_and_switch_preserves_original(self):
        self.tasks.receiveText("第一张卡片的原文")
        self.tasks.saveDraft()
        first = self.store.list_tasks()[0]
        self.tasks.newTask()
        self.tasks.setDraftText("第二张")
        self.tasks.saveDraft()
        second = self.store.list_tasks()[0]

        self.assertTrue(self.tasks.editTask(first.task_id))
        self.tasks.setDraftText("第一张的修改")
        self.tasks.setDraftSchedule("2028-02-29", "09:30")
        self.assertTrue(self.tasks.editTask(second.task_id))
        saved = self.store.get(first.task_id)
        self.assertEqual((saved.body, saved.original_text, saved.due_date, saved.due_time),
                         ("第一张的修改", "第一张卡片的原文", "2028-02-29", "09:30"))
        self.assertEqual(self.tasks.draftBody, "第二张")
        self.tasks.setDraftText("第二张的修改")
        self.assertTrue(self.tasks.editTask(second.task_id))
        self.assertFalse(self.tasks.draftVisible)
        self.assertEqual(self.store.get(second.task_id).body, "第二张的修改")

    def test_finish_empty_new_draft_but_never_discard_failed_existing_edit(self):
        self.tasks.newTask()
        self.tasks.setDraftText(" \n ")
        self.assertTrue(self.tasks.finishDraft())
        self.assertFalse(self.tasks.draftVisible)
        self.assertEqual(self.tasks.activeCount, 0)
        self.tasks.newTask()
        self.tasks.setDraftText("原内容")
        self.tasks.saveDraft()
        first = self.store.list_tasks()[0]
        self.tasks.newTask()
        self.tasks.setDraftText("另一张")
        self.tasks.saveDraft()
        second = self.store.list_tasks()[0]
        self.tasks.editTask(first.task_id)
        self.tasks.setDraftText("改动不能丢")
        self.store.connection.execute("PRAGMA query_only = ON")
        self.assertFalse(self.tasks.editTask(second.task_id))
        self.assertFalse(self.tasks.finishDraft())
        self.assertTrue(self.tasks.draftVisible)
        self.assertEqual(self.tasks.draftBody, "改动不能丢")
        self.assertEqual(self.store.get(first.task_id).body, "原内容")
        self.store.connection.execute("PRAGMA query_only = OFF")
        self.assertTrue(self.tasks.finishDraft())
        self.assertEqual(self.store.get(first.task_id).body, "改动不能丢")
        self.tasks.editTask(first.task_id)
        self.tasks.setDraftText("")
        self.assertFalse(self.tasks.finishDraft())
        self.assertTrue(self.tasks.draftVisible)

    def test_error_message_expires_without_losing_draft(self):
        self.tasks.newTask()
        self.tasks.setDraftText("保留这段输入")
        self.assertFalse(self.tasks.setDraftSchedule("2026-02-30", ""))
        self.assertTrue(self.tasks.message and self.tasks.isError)
        QTest.qWait(3750)
        self.assertEqual(self.tasks.message, "")
        self.assertFalse(self.tasks.isError)
        self.assertTrue(self.tasks.draftVisible)
        self.assertEqual(self.tasks.draftBody, "保留这段输入")

    def test_new_task_saves_existing_edit_then_starts_blank(self):
        self.tasks.receiveText("原始任务")
        self.tasks.saveDraft()
        original = self.store.list_tasks()[0]
        self.tasks.editTask(original.task_id)
        self.tasks.setDraftText("旧任务的修改")
        self.store.connection.execute("PRAGMA query_only = ON")
        self.assertFalse(self.tasks.newTask())
        self.assertTrue(self.tasks.editing)
        self.assertEqual(self.tasks.draftBody, "旧任务的修改")
        self.store.connection.execute("PRAGMA query_only = OFF")
        self.assertTrue(self.tasks.newTask())
        self.assertFalse(self.tasks.editing)
        self.assertEqual(self.tasks.draftBody, "")
        self.tasks.setDraftText("新任务")
        self.tasks.saveDraft()
        self.assertEqual(self.tasks.activeCount, 2)
        self.assertEqual(self.store.get(original.task_id).body, "旧任务的修改")
