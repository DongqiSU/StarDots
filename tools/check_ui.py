"""离屏验证窗口、真实鼠标/键盘事件和截图，不在桌面留下常驻程序。"""

import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QObject, QPoint, QPointF, QRect, QTimer, Qt, QMimeData, qInstallMessageHandler
from PySide6.QtGui import QFontDatabase, QRawFont, QDragEnterEvent, QDropEvent, QInputMethodEvent, QWheelEvent
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest, QAbstractItemModelTester
from PySide6.QtWidgets import QApplication

from stardot.app import create_runtime
from stardot.storage import TaskStore


def main() -> int:
    diagnostics: list[str] = []

    def capture_message(_kind, _context, message):
        diagnostics.append(message)

    qInstallMessageHandler(capture_message)
    app = QApplication(["stardot-ui-check"])
    # 离屏插件需要显式加载字形；正常 Windows 桌面启动使用系统字体。
    if sys.platform == "win32":
        font_dir = Path(os.environ["WINDIR"]) / "Fonts"
        for name in ("msyh.ttc", "msyhbd.ttc"):
            if QFontDatabase.addApplicationFont(str(font_dir / name)) < 0:
                raise RuntimeError(f"无法加载离屏测试字体：{name}")
    test_data = TemporaryDirectory(prefix="stardot-ui-")
    runtime = create_runtime(["stardot-ui-check"], database_path=Path(test_data.name) / "test.sqlite3")
    # 离屏检查模拟“已松手”，避免用户在真实桌面的鼠标操作干扰测试。
    runtime.controller._mouse_is_down = lambda: False
    model_tester = QAbstractItemModelTester(runtime.tasks.taskModel,
        QAbstractItemModelTester.FailureReportingMode.Warning)
    output = Path(__file__).resolve().parents[1] / "artifacts" / "ui"
    output.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    def find_visual(item, name):
        if item.objectName() == name:
            return item
        for child in item.childItems():
            found = find_visual(child, name)
            if found is not None:
                return found
        return None

    def click(name):
        # ListView 的 delegate 属于视觉树，不保证位于 Window 的 QObject 子树。
        item = find_visual(runtime.panel.contentItem(), name)
        assert item is not None, f"找不到控件：{name}"
        point = item.mapToScene(item.boundingRect().center()).toPoint()
        QTest.mouseClick(runtime.panel, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(40)

    def drop_text(text):
        mime = QMimeData()
        mime.setText(text)
        enter = QDragEnterEvent(QPoint(42, 42), Qt.CopyAction | Qt.MoveAction,
                                mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(runtime.star, enter)
        assert enter.isAccepted(), "文字拖入未被接收"
        QTest.qWait(180)
        drop = QDropEvent(QPointF(42, 42), Qt.CopyAction | Qt.MoveAction,
                          mime, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(runtime.star, drop)
        QTest.qWait(220)
        return drop

    def check():
        try:
            font = QRawFont.fromFont(runtime.app.font())
            assert font.isValid() and font.supportsCharacter("星"), "离屏环境未加载中文字体"
            assert runtime.star.isVisible(), "星星应显示"
            assert not runtime.panel.isVisible(), "启动时清单应收起"
            image = runtime.star.grabWindow()
            assert not image.isNull(), "星星截图为空"
            assert image.save(str(output / "star.png")), "无法保存星星截图"

            QTest.mouseClick(runtime.star, Qt.LeftButton, Qt.NoModifier, QPoint(42, 42))
            QTest.qWait(300)
            assert runtime.controller.panelVisible, "点击星星未更新 Python 状态"
            assert runtime.panel.isVisible(), "Python 状态未更新 QML 窗口"
            assert runtime.panel.opacity() > 0.99, "首帧完成后应正常淡入"
            image = runtime.panel.grabWindow()
            assert not image.isNull(), "清单截图为空"
            assert image.save(str(output / "panel.png")), "无法保存清单截图"

            close = runtime.panel.findChild(QQuickItem, "closePanelButton")
            assert close is not None, "收起按钮不存在"
            point = close.mapToScene(close.boundingRect().center()).toPoint()
            QTest.mouseClick(runtime.panel, Qt.LeftButton, Qt.NoModifier, point)
            QTest.qWait(40)
            assert not runtime.controller.panelVisible, "收起按钮未更新 Python 状态"
            assert not runtime.panel.isVisible(), "清单未收起"
            assert runtime.panel.opacity() == 0, "隐藏时应清空原生窗口透明度"

            # 重复打开不会重启动画；快速开关也不能留下可见的旧帧。
            for _ in range(3):
                runtime.controller.showPanel()
                assert runtime.panel.opacity() == 0, "原生窗口必须先透明再显示"
                QTest.qWait(40)
                runtime.controller.hidePanel()
            runtime.controller.showPanel()
            QTest.qWait(250)
            runtime.controller.showPanel()
            assert runtime.panel.opacity() > 0.99, "已打开时聚焦不能再次闪烁"
            runtime.controller.hidePanel()

            runtime.controller.showPanel()
            QTest.qWait(80)
            QTest.keyClick(runtime.panel, Qt.Key_Escape)
            QTest.qWait(40)
            assert not runtime.panel.isVisible(), "Escape 未收起清单"

            area = runtime.star.screen().availableGeometry()
            runtime.star.setPosition(area.left() + 20, area.top() + 20)
            runtime.controller.showPanel()
            assert runtime.panel.x() > runtime.star.x(), "星星靠左时清单应向右展开"
            runtime.star.setPosition(area.right() - runtime.star.width() - 20,
                                     area.bottom() - runtime.star.height() - 20)
            assert runtime.panel.x() < runtime.star.x(), "星星靠右时清单应向左展开"
            assert area.contains(runtime.panel.geometry()), "清单不应越出屏幕"
            runtime.controller.hidePanel()

            for position in (QPoint(area.left() - 40, area.top() - 40),
                             QPoint(area.right() - 20, area.bottom() - 20),
                             QPoint(area.left() - 200, area.bottom() + 200)):
                runtime.star.setPosition(position)
                QTest.qWait(300)
                visible_body = QRect(runtime.star.x() + 11, runtime.star.y() + 12, 62, 61)
                assert area.contains(visible_body), "星星可见部分应自动完整移回屏幕"
            runtime.star.setPosition(area.left() + 10, area.top() + 120)
            QTest.qWait(300)
            assert runtime.star.x() + 11 == area.left() + 2, "吸附后可见星星距左边缘应为 2 像素"
            mascot = runtime.star.findChild(QQuickItem, "desktopMascot")
            mascot.setProperty("highlighted", True)
            QTest.qWait(200)
            assert mascot.property("eyeHeight") == 15, "高亮时眼睛应睁大"
            assert runtime.star.grabWindow().save(str(output / "star-highlight.png"))

            # 真正走 QML DropArea 和 Ctrl+Enter，测试只使用临时数据库。
            dropped_text = "明天下午讨论预算\n带上方案，别忘了附件。"
            drop = drop_text(dropped_text)
            assert drop.isAccepted() and drop.dropAction() == Qt.CopyAction, "拖放只能复制来源文字"
            assert runtime.tasks.draftBody == dropped_text
            assert runtime.tasks.activeCount == 0, "接收文字不能自动保存任务"
            assert runtime.star.grabWindow().save(str(output / "star-received.png"))
            assert runtime.panel.grabWindow().save(str(output / "editor.png"))
            rejected = drop_text("不应覆盖已有草稿")
            assert not rejected.isAccepted()
            assert runtime.tasks.draftBody == dropped_text, "第二次拖入覆盖了编辑内容"
            runtime.tasks.dismissMessage()
            task_input = runtime.star.findChild(QQuickItem, "taskInput")
            task_input.forceActiveFocus()
            QTest.keyClick(runtime.panel, Qt.Key_Return, Qt.ControlModifier)
            QTest.qWait(100)
            assert runtime.tasks.activeCount == 1
            assert not runtime.tasks.draftVisible
            saved = runtime.store.list_tasks()[0]
            assert saved.original_text == dropped_text
            assert runtime.panel.grabWindow().save(str(output / "tasks.png"))
            body_label = find_visual(runtime.panel.contentItem(), "body-" + saved.task_id)
            assert abs(body_label.y() + body_label.height() / 2 - body_label.parentItem().height() / 2) < 1

            # 编辑保留原文；普通 Enter 换行，不保存。
            saved_card = find_visual(runtime.panel.contentItem(), "task-" + saved.task_id)
            point = saved_card.mapToScene(QPointF(140, 30)).toPoint()
            QTest.mouseClick(runtime.panel, Qt.LeftButton, Qt.NoModifier, point)
            QTest.qWait(50)
            assert runtime.tasks.editing, "单击卡片应进入编辑"
            task_input.setProperty("text", "修改后的待办")
            editor = runtime.star.findChild(QQuickItem, "taskEditor")
            original_point = editor.mapToScene(QPointF(120, 75)).toPoint()
            QTest.mouseDClick(runtime.panel, Qt.LeftButton, Qt.NoModifier, original_point)
            QTest.qWait(50)
            assert editor.property("showOriginal"), "双击编辑区应展示原文"
            assert runtime.tasks.draftBody == "修改后的待办", "查看原文不能替换草稿"
            assert runtime.star.findChild(QQuickItem, "originalInput").property("text") == dropped_text
            assert runtime.panel.grabWindow().save(str(output / "original.png"))
            QTest.qWait(QApplication.styleHints().mouseDoubleClickInterval() + 20)
            QTest.mouseDClick(runtime.panel, Qt.LeftButton, Qt.NoModifier, original_point)
            assert not editor.property("showOriginal")
            task_input.forceActiveFocus()
            QTest.keyClick(runtime.panel, Qt.Key_Return)
            assert runtime.tasks.draftVisible and runtime.tasks.activeCount == 1
            assert "\n" in runtime.tasks.draftBody
            assert runtime.store.get(saved.task_id).body == dropped_text
            click("saveTaskButton")
            assert runtime.store.get(saved.task_id).body == "修改后的待办"
            assert runtime.store.get(saved.task_id).original_text == dropped_text

            # 点击完成、微笑、归档、恢复，再测试在过渡期间立即撤销。
            click("complete-" + saved.task_id)
            assert runtime.tasks.archivedCount == 1
            assert mascot.property("expression") == "completed"
            assert runtime.star.grabWindow().save(str(output / "star-completed.png"))
            QTest.qWait(280)
            click("archiveButton")
            assert runtime.tasks.taskModel.rowCount() == 1
            QTest.qWait(230)
            assert runtime.panel.grabWindow().save(str(output / "archive.png"))
            click("delete-" + saved.task_id)
            assert runtime.tasks.archivedCount == 0 and not runtime.tasks.draftVisible
            assert not runtime.store.list_tasks()
            click("undoButton")
            assert runtime.tasks.archivedCount == 1
            assert runtime.store.get(saved.task_id).original_text == dropped_text
            QTest.qWait(220)
            click("complete-" + saved.task_id)
            assert runtime.tasks.activeCount == 1 and runtime.tasks.archivedCount == 0
            runtime.tasks.completeTask(saved.task_id)
            runtime.tasks.undo()
            QTest.qWait(300)
            assert runtime.tasks.activeCount == 1 and runtime.tasks.archivedCount == 0
            assert runtime.store.get(saved.task_id).completed_at is None
            click("archiveButton")
            QTest.qWait(230)
            restored_card = find_visual(runtime.panel.contentItem(), "task-" + saved.task_id)
            assert restored_card is not None and not restored_card.property("completed")
            assert find_visual(restored_card, "complete-" + saved.task_id).isEnabled()

            # 输入法组词时 Ctrl+Enter 不能误保存；提交后再保存一次。
            runtime.tasks.newTask()
            QTest.qWait(50)
            task_input.setProperty("text", "输入法检查")
            task_input.forceActiveFocus()
            QApplication.sendEvent(runtime.panel, QInputMethodEvent("zhong", []))
            assert task_input.property("inputMethodComposing")
            QTest.keyClick(runtime.panel, Qt.Key_Return, Qt.ControlModifier)
            assert runtime.tasks.activeCount == 1 and runtime.tasks.draftVisible
            commit = QInputMethodEvent()
            commit.setCommitString("中")
            QApplication.sendEvent(runtime.panel, commit)
            assert not task_input.property("inputMethodComposing")
            QTest.keyClick(runtime.panel, Qt.Key_Return, Qt.ControlModifier)
            QTest.qWait(50)
            assert runtime.tasks.activeCount == 2

            # 数据库写保护时保留草稿，界面不能伪报成功。
            runtime.tasks.newTask()
            task_input.setProperty("text", "保存失败也不能丢失")
            runtime.store.connection.execute("PRAGMA query_only = ON")
            assert not runtime.tasks.saveDraft()
            assert runtime.tasks.draftBody == "保存失败也不能丢失"
            assert runtime.tasks.activeCount == 2 and runtime.tasks.isError
            runtime.store.connection.execute("PRAGMA query_only = OFF")
            assert runtime.tasks.saveDraft()
            with_store = TaskStore(runtime.store.path)
            assert len(with_store.list_tasks()) == 3, "重开数据库后应能读到任务"
            with_store.close()

            # 多条长任务应在列表内滚动，不挤走编辑器；正文按纯文本呈现。
            for body in ("整理书桌，给今天留一点空白",
                         "把这周的灵感整理进笔记",
                         "<b>这里只是文字，不会变成富文本</b>",
                         "很长的待办内容，卡片最多显示四行。" * 20,
                         "读完搁置的那一章"):
                runtime.tasks.newTask()
                runtime.tasks.setDraftText(body)
                assert runtime.tasks.saveDraft()
            runtime.tasks.dismissMessage()
            QTest.qWait(250)
            task_list = runtime.star.findChild(QQuickItem, "taskList")
            assert task_list.property("contentHeight") > task_list.height()
            assert runtime.panel.grabWindow().save(str(output / "tasks-populated.png"))
            runtime.tasks.newTask()
            runtime.tasks.setDraftText("准备下周的阅读清单")
            QTest.qWait(100)
            assert runtime.panel.grabWindow().save(str(output / "tasks-with-editor.png"))
            runtime.tasks.cancelDraft()

            # 灰色概要只由 Enter 确认；日期自动填入，不等待确认。
            before_count = runtime.tasks.activeCount
            source = "大家好！\n提醒：明天下午三点带预算表开会。\n谢谢大家！"
            assert drop_text(source).isAccepted()
            assert runtime.tasks.summaryPending
            assert runtime.tasks.draftBody == "明天下午三点带预算表开会。"
            assert runtime.tasks.draftTime == "15:00"
            assert runtime.panel.grabWindow().save(str(output / "summary-date.png"))
            task_input.forceActiveFocus()
            QTest.keyClick(runtime.panel, Qt.Key_Return)
            assert not runtime.tasks.summaryPending and runtime.tasks.activeCount == before_count
            assert runtime.tasks.draftTime == "15:00"
            assert runtime.tasks.originalText == source

            # 日历点选日期、选择时刻、滚轮跨闰月，再取消。
            click("dateButton")
            date_popup = runtime.star.findChild(QObject, "datePopup")
            assert date_popup is not None and date_popup.property("visible")
            date_popup.setProperty("displayedYear", 2028)
            date_popup.setProperty("displayedMonth", 0)
            QTest.qWait(40)
            click("calendarDay2028-01-31")
            hour = find_visual(runtime.panel.contentItem(), "hourPicker")
            minute = find_visual(runtime.panel.contentItem(), "minutePicker")
            hour.forceActiveFocus()
            QTest.keyClick(runtime.panel, Qt.Key_End)
            minute.forceActiveFocus()
            QTest.keyClick(runtime.panel, Qt.Key_End)
            assert date_popup.property("selectedHour") == 23
            assert date_popup.property("selectedMinute") == 59
            assert runtime.panel.grabWindow().save(str(output / "date-popup.png"))
            click("applyDateButton")
            assert (runtime.tasks.draftDate, runtime.tasks.draftTime) == ("2028-01-31", "23:59")
            month = find_visual(runtime.panel.contentItem(), "dateMonth")
            local = month.mapToScene(month.boundingRect().center())
            wheel = QWheelEvent(local, QPointF(runtime.panel.mapToGlobal(local.toPoint())),
                                QPoint(), QPoint(0, 120), Qt.NoButton, Qt.NoModifier,
                                Qt.ScrollUpdate, False)
            QApplication.sendEvent(runtime.panel, wheel)
            assert runtime.tasks.draftDate == "2028-02-29", "滚轮按月调整应处理闰年"
            click("clearDateButton")
            assert runtime.tasks.draftDate == "" and runtime.tasks.draftTime == ""
            task_input.setProperty("text", "明天16:00开会，带上附件")
            QTest.qWait(400)
            assert runtime.tasks.draftDate == "", "取消日期后不能被再次识别覆盖"
            click("saveTaskButton")
            assert runtime.tasks.activeCount == before_count + 1
            assert runtime.store.list_tasks()[0].due_date is None

            assert drop_text("提醒：后天09:00提交预算表。谢谢！").isAccepted()
            assert runtime.tasks.summaryPending
            task_input.forceActiveFocus()
            QTest.keyClick(runtime.panel, Qt.Key_Return, Qt.ControlModifier)
            QTest.qWait(220)
            assert runtime.tasks.activeCount == before_count + 2
            assert runtime.store.list_tasks()[0].due_time == "09:00"
            assert runtime.panel.grabWindow().save(str(output / "dated-tasks.png"))

            # 单击当前卡片保存并关闭；单击另一张先保存、再切换。
            newest = runtime.store.list_tasks()[0]
            older = runtime.store.list_tasks()[1]
            def click_card(task_id):
                item = find_visual(runtime.panel.contentItem(), "task-" + task_id)
                assert item is not None
                point = item.mapToScene(QPointF(130, item.height() / 2)).toPoint()
                QTest.mouseClick(runtime.panel, Qt.LeftButton, Qt.NoModifier, point)
                QTest.qWait(80)
            task_list.setProperty("contentY", 0)
            QTest.qWait(80)
            click_card(newest.task_id)
            task_input.setProperty("text", "单击另一张之前的修改")
            click_card(older.task_id)
            assert runtime.store.get(newest.task_id).body == "单击另一张之前的修改"
            assert runtime.tasks.draftBody == older.body
            task_input.setProperty("text", "再次单击当前卡片保存")
            click_card(older.task_id)
            assert not runtime.tasks.draftVisible
            assert runtime.store.get(older.task_id).body == "再次单击当前卡片保存"

            # 关闭清单保存草稿并关闭日期弹窗；再次展开只显示清单。
            runtime.tasks.editTask(newest.task_id)
            task_input.setProperty("text", "收起清单时保存")
            click("dateButton")
            runtime.controller.hidePanel()
            QTest.qWait(80)
            assert not runtime.tasks.draftVisible and not runtime.panel.isVisible()
            assert not date_popup.property("visible")
            assert runtime.store.get(newest.task_id).body == "收起清单时保存"
            runtime.controller.showPanel()
            QTest.qWait(250)
            assert not runtime.tasks.draftVisible
            runtime.tasks.editTask(newest.task_id)
            task_input.setProperty("text", "保存失败时不能收起")
            runtime.store.connection.execute("PRAGMA query_only = ON")
            runtime.controller.hidePanel()
            assert runtime.panel.isVisible() and runtime.tasks.draftVisible
            assert runtime.tasks.draftBody == "保存失败时不能收起"
            runtime.store.connection.execute("PRAGMA query_only = OFF")
            runtime.controller.hidePanel()
            assert not runtime.panel.isVisible() and not runtime.tasks.draftVisible

            # 手动新建的日期默认不附带时刻，日期按钮与保存勾在同一行。
            runtime.tasks.newTask()
            QTest.qWait(250)
            task_input.setProperty("text", "手动选择日期")
            date_button = find_visual(runtime.panel.contentItem(), "dateButton")
            save_button = find_visual(runtime.panel.contentItem(), "saveTaskButton")
            date_center = date_button.mapToScene(date_button.boundingRect().center())
            save_center = save_button.mapToScene(save_button.boundingRect().center())
            assert abs(date_center.y() - save_center.y()) < 1
            click("dateButton")
            assert not date_popup.property("timeEnabled")
            date_popup.setProperty("displayedYear", 2028)
            date_popup.setProperty("displayedMonth", 1)
            click("calendarDay2028-02-29")
            click("applyDateButton")
            assert (runtime.tasks.draftDate, runtime.tasks.draftTime) == ("2028-02-29", "")
            assert runtime.panel.grabWindow().save(str(output / "editor-date-selected.png"))
            click("saveTaskButton")
            manual = runtime.store.list_tasks()[0]
            task_list.setProperty("contentY", 0)
            QTest.qWait(200)
            body_label = find_visual(runtime.panel.contentItem(), "body-" + manual.task_id)
            due_label = find_visual(runtime.panel.contentItem(), "due-" + manual.task_id)
            assert abs(body_label.y() + body_label.height() / 2 - body_label.parentItem().height() / 2) < 1
            assert due_label.y() > body_label.y() + body_label.height()
            assert runtime.panel.grabWindow().save(str(output / "cards-centered.png"))

            qml_errors = [message for message in diagnostics
                          if "file:" in message or "Error" in message or "FAIL!" in message]
            assert not qml_errors, "\n".join(qml_errors)
            print("PASS: UI, star snap/recovery, copy/drop, card save/switch, close/save guard, double-click original, archive/delete/undo, IME, persistence, summary Enter, date picker/wheel/cancel, centered cards, panel entrance")
            print(f"Screenshots: {output}")
        except Exception as error:
            failures.append(str(error))
            print(f"FAIL: {error}", file=sys.stderr)
            for message in diagnostics:
                print(message, file=sys.stderr)
        finally:
            runtime.controller.hidePanel()
            runtime.star.hide()
            runtime.app.quit()

    QTimer.singleShot(400, check)
    runtime.app.exec()
    test_data.cleanup()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
