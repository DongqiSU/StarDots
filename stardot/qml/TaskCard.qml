import QtQuick
import QtQuick.Controls

Rectangle {
    id: card
    required property string taskId
    required property string body
    required property bool completed
    required property string dueLabel
    required property string dueColor
    required property string dueFull
    required property QtObject tasks
    required property int reminderMinutes
    required property bool hasTime
    property bool calendarMode: false
    objectName: "task-" + taskId
    // 日期固定在右下角，正文始终相对整张卡片垂直居中。
    // 两侧对称留白，确保多行正文不会碰到日期。
    implicitHeight: Math.max(72, bodyLabel.implicitHeight + (dueLabel ? 52 : 32))
    radius: 17
    color: hover.hovered ? "#fff1dd" : "#fffcf7"
    border.color: "#eedfcd"
    Behavior on color { ColorAnimation { duration: 100 } }
    HoverHandler { id: hover }
    Item {
        x: 48
        width: parent.width - x - (deleteButton.visible ? 47 : 8)
        height: parent.height
        TapHandler {
            onTapped: {
                Qt.inputMethod.commit()
                card.tasks.editTask(card.taskId)
            }
        }
    }
    IconButton {
        id: deleteButton
        objectName: "delete-" + card.taskId
        visible: card.completed && card.tasks.archiveVisible
        anchors.right: parent.right
        anchors.rightMargin: 10
        y: 16
        symbol: "trash"
        label: "删除归档任务"
        onClicked: card.tasks.deleteTask(card.taskId)
    }
    Button {
        id: completeButton
        objectName: "complete-" + card.taskId
        x: 12
        anchors.verticalCenter: parent.verticalCenter
        width: 34
        height: 34
        enabled: card.calendarMode || !(card.completed && !card.tasks.archiveVisible)
        Accessible.name: card.completed ? "恢复任务" : "完成任务"
        ToolTip.visible: hovered
        ToolTip.text: Accessible.name
        onClicked: {
            if (card.completed) {
                card.tasks.restoreTask(card.taskId)
            } else {
                card.tasks.completeTask(card.taskId)
            }
        }
        background: Rectangle {
            anchors.centerIn: parent
            width: 21
            height: 21
            radius: 8
            border.color: card.completed ? "#c6ad88" : "#d6bc98"
            color: card.completed ? "#e8d9c3" : (completeButton.hovered ? "#ffdf92" : "transparent")
        }
        contentItem: Item {
            Canvas {
                anchors.centerIn: parent
                width: 18
                height: 18
                visible: card.completed
                onPaint: {
                    const ctx = getContext("2d")
                    ctx.reset()
                    ctx.strokeStyle = "#8a7158"
                    ctx.lineWidth = 1.6
                    ctx.lineCap = "round"
                    ctx.lineJoin = "round"
                    ctx.beginPath()
                    ctx.moveTo(4, 9); ctx.lineTo(8, 13); ctx.lineTo(14, 5)
                    ctx.stroke()
                }
            }
        }
    }
    Text {
        id: bodyLabel
        objectName: "body-" + card.taskId
        anchors.left: parent.left
        anchors.leftMargin: 53
        anchors.right: parent.right
        anchors.rightMargin: deleteButton.visible ? 50 : 16
        anchors.verticalCenter: parent.verticalCenter
        text: card.body
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        maximumLineCount: 4
        elide: Text.ElideRight
        font.pixelSize: 14
        lineHeight: 1.25
        font.strikeout: card.completed
        color: card.completed ? "#ae9e8d" : "#634b38"
    }
    Text {
        id: dueText
        objectName: "due-" + card.taskId
        anchors.right: parent.right
        anchors.rightMargin: 14
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 8
        visible: card.dueLabel.length > 0
        text: card.dueLabel
        font.pixelSize: 11
        color: card.completed ? "#ae9e8d" : card.dueColor
        HoverHandler { id: dueHover }
        ToolTip.visible: dueHover.hovered
        ToolTip.delay: 500
        ToolTip.timeout: 2500
        ToolTip.text: card.dueFull
    }
    ReminderButton {
        visible: card.hasTime && !card.completed
        anchors.right: dueText.left
        anchors.rightMargin: 5
        anchors.verticalCenter: dueText.verticalCenter
        width: 22; height: 22
        minutes: card.reminderMinutes
        onChosen: function(value) { card.tasks.setTaskReminder(card.taskId, value) }
    }
}
