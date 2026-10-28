import QtQuick
import QtQuick.Controls

Rectangle {
    id: editor
    required property QtObject tasks
    objectName: "taskEditor"
    property bool showOriginal: false
    visible: tasks.draftVisible
    height: visible ? 210 : 0
    radius: 18
    color: "#fff6e6"
    border.color: "#e4cda5"

    function submit() {
        if (!input.inputMethodComposing)
            tasks.saveDraft()
    }
    function toggleOriginal() {
        if (tasks.originalText.length > 0) {
            showOriginal = !showOriginal
            if (!showOriginal)
                input.forceActiveFocus()
        }
    }
    Connections {
        target: editor.tasks
        function onEditorRequested() {
            editor.showOriginal = false
            Qt.callLater(function() { if (editor.visible && editor.Window.window.visible) input.forceActiveFocus() })
        }
        function onDraftChanged() {
            if (!editor.tasks.draftVisible)
                editor.showOriginal = false
        }
    }
    Text {
        x: 15; y: 12
        text: editor.showOriginal ? "原文 · 双击返回" : (editor.tasks.editing ? "编辑小事" : "记下一件小事")
        font.pixelSize: 12
        color: "#9a7856"
    }
    IconButton {
        anchors.right: parent.right
        anchors.rightMargin: 9
        y: 5
        width: 28; height: 28
        label: "取消编辑"
        onClicked: editor.tasks.cancelDraft()
    }
    ScrollView {
        id: inputScroll
        x: 10; y: 37
        width: parent.width - 20
        height: 94
        visible: !editor.showOriginal
        clip: true
        TextArea {
            id: input
            TapHandler { onDoubleTapped: editor.toggleOriginal() }
            objectName: "taskInput"
            text: editor.tasks.draftBody
            textFormat: TextEdit.PlainText
            placeholderText: "有什么想做的？"
            placeholderTextColor: "#b8a189"
            wrapMode: TextEdit.Wrap
            color: editor.tasks.summaryPending ? "#a9957e" : "#60432f"
            font.pixelSize: 14
            selectByMouse: true
            background: null
            onTextChanged: editor.tasks.setDraftText(text)
            Keys.priority: Keys.BeforeItem
            Keys.onPressed: function(event) {
                if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && !inputMethodComposing) {
                    if (event.modifiers & Qt.ControlModifier) {
                        event.accepted = true
                        if (!event.isAutoRepeat)
                            editor.submit()
                    } else if (event.modifiers === Qt.NoModifier && editor.tasks.summaryPending) {
                        event.accepted = true
                        editor.tasks.acceptSummary()
                    }
                }
            }
        }
    }
    Text {
        anchors.right: parent.right
        anchors.rightMargin: 16
        y: 145
        text: "Ctrl + Enter"
        font.pixelSize: 10
        color: "#b09777"
    }
    IconButton {
        id: saveButton
        objectName: "saveTaskButton"
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        width: 34; height: 34
        symbol: "check"
        label: "保存任务"
        selected: true
        enabled: editor.tasks.draftBody.trim().length > 0
        onClicked: editor.submit()
    }
    ScrollView {
        x: 10; y: 37
        width: parent.width - 20
        height: 94
        visible: editor.showOriginal
        clip: true
        TextArea {
            objectName: "originalInput"
            TapHandler { onDoubleTapped: editor.toggleOriginal() }
            text: editor.tasks.originalText
            textFormat: TextEdit.PlainText
            readOnly: true
            selectByMouse: true
            wrapMode: TextEdit.Wrap
            font.pixelSize: 12
            color: "#9b846d"
            background: null
            Keys.onPressed: function(event) {
                if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && (event.modifiers & Qt.ControlModifier)) {
                    event.accepted = true
                    if (!event.isAutoRepeat)
                        editor.submit()
                }
            }
        }
    }
    DateEditor {
        x: 12
        anchors.verticalCenter: saveButton.verticalCenter
        width: (reminder.visible ? reminder.x : saveButton.x) - x - 8
        tasks: editor.tasks
    }
    Text {
        x: 16; y: 145
        visible: editor.tasks.summaryPending && !editor.showOriginal
        text: "Enter 确认正文"
        font.pixelSize: 10
        color: "#b09777"
    }
    ReminderButton {
        id: reminder
        objectName: "draftReminder"
        visible: editor.visible && editor.tasks.draftTime.length > 0
        anchors.right: saveButton.left
        anchors.rightMargin: 6
        anchors.verticalCenter: saveButton.verticalCenter
        minutes: editor.tasks.draftReminder
        onChosen: function(value) { editor.tasks.setDraftReminder(value) }
    }
}
