import QtQuick
import QtQuick.Controls

Window {
    id: window
    required property QtObject controller
    required property QtObject tasks
    required property QtObject calendar
    objectName: "calendarWindow"
    title: "星点 · 日历"
    width: 1060; height: 760
    property bool compact: width < 950
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.Window
    onClosing: function(event) { event.accepted = false; controller.closeCalendar() }
    Shortcut { sequence: "Escape"; onActivated: window.controller.closeCalendar() }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 6
        radius: 24
        color: "#fffaf3"
        border.color: "#e7d4b9"
        Rectangle {
            x: 1; y: 1; width: parent.width - 2; height: 95; radius: 23
            gradient: Gradient {
                GradientStop { position: 0; color: "#ffedce" }
                GradientStop { position: 1; color: "#fffaf3" }
            }
        }
        Item {
            x: 18; y: 12; width: parent.width - 130; height: 56
            DragHandler { target: null; onActiveChanged: if (active) window.startSystemMove() }
        }
        Row {
            x: 24; y: 22; spacing: 10
            StarMascot { width: 34; height: 34 }
            Text { text: "日历"; font.pixelSize: 23; font.weight: Font.DemiBold; color: "#67482e"; anchors.verticalCenter: parent.verticalCenter }
        }
        Row {
            anchors.horizontalCenter: grid.horizontalCenter
            y: window.compact ? 70 : 25; spacing: 14
            IconButton { symbol: "previous"; label: "上个月"; onClicked: window.calendar.shiftMonth(-1) }
            Text { text: window.calendar.monthLabel; font.pixelSize: 18; color: "#795a3d"; anchors.verticalCenter: parent.verticalCenter }
            IconButton { symbol: "next"; label: "下个月"; onClicked: window.calendar.shiftMonth(1) }
            Button {
                text: "今天"; width: 48; height: 32
                onClicked: window.calendar.today()
                background: Rectangle { radius: 10; color: "#f6e7ce" }
                contentItem: Text { text: parent.text; color: "#926c3b"; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
            }
        }
        Row {
            anchors.right: parent.right; anchors.rightMargin: 20
            y: 22; spacing: 8
            IconButton { symbol: "list"; label: "切换到清单"; onClicked: window.controller.showPanel() }
            IconButton { label: "关闭日历"; onClicked: window.controller.closeCalendar() }
        }
        Row {
            x: grid.x; y: window.compact ? 117 : 88; width: grid.width
            Repeater {
                model: ["一", "二", "三", "四", "五", "六", "日"]
                Text { required property string modelData; width: grid.width / 7; text: modelData; color: "#ab8b6a"; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter }
            }
        }
        Grid {
            id: grid
            objectName: "calendarGrid"
            x: 20; y: window.compact ? 145 : 116
            width: parent.width - sidebar.width - 54
            height: parent.height - y - 26
            columns: 7
            spacing: 4
            Repeater {
                model: window.calendar.days
                Rectangle {
                    id: cell
                    required property var modelData
                    objectName: "day-" + modelData.day
                    width: (grid.width - 24) / 7
                    height: (grid.height - 20) / 6
                    radius: 12
                    color: modelData.day === window.calendar.selectedDay ? "#fff0d2" : (modelData.inMonth ? "#fffdf9" : "#f6f0e7")
                    border.color: modelData.day === window.calendar.selectedDay ? "#deb273" : "#ede1d0"
                    TapHandler { onTapped: window.calendar.selectDay(cell.modelData.day) }
                    Rectangle {
                        x: 7; y: 6; width: 21; height: 21; radius: 10.5
                        color: cell.modelData.today ? "#f5d189" : "transparent"
                        Text {
                            anchors.centerIn: parent; text: cell.modelData.number
                            font.pixelSize: 11
                            color: cell.modelData.inMonth ? "#97754f" : "#c8b6a1"
                        }
                    }
                    Column {
                        x: 6; y: 31; width: parent.width - 12; spacing: 3
                        Repeater {
                            model: cell.modelData.items
                            Rectangle {
                                id: entry
                                required property var modelData
                                width: parent.width; height: Math.max(20, Math.min(30, (cell.height - 51) / 2))
                                radius: 5; color: entry.modelData.completed ? "#eee8df" : "#f8e8c9"
                                Text {
                                    anchors.fill: parent; anchors.margins: 4
                                    text: entry.modelData.body; textFormat: Text.PlainText
                                    font.pixelSize: 12; font.strikeout: entry.modelData.completed
                                    color: entry.modelData.completed ? "#b09f89" : "#735333"
                                    elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
                                }
                                TapHandler { onTapped: window.calendar.editTask(cell.modelData.day, entry.modelData.taskId) }
                            }
                        }
                    }
                    Text {
                        visible: cell.modelData.count > 2
                        anchors.right: parent.right; anchors.rightMargin: 7
                        anchors.bottom: parent.bottom; anchors.bottomMargin: 4
                        text: "+" + (cell.modelData.count - 2); color: "#a5753b"; font.pixelSize: 10
                    }
                }
            }
        }
        Rectangle {
            id: sidebar
            width: window.compact ? 300 : 330
            anchors.right: parent.right; anchors.rightMargin: 20
            y: window.compact ? 116 : 84; height: parent.height - y - 26
            radius: 18; color: "#f8efdf"
            Text { x: 15; y: 18; text: window.calendar.selectedDay; font.pixelSize: 15; color: "#8c6842" }
            IconButton {
                x: parent.width - 44; y: 10
                symbol: "add"; label: "在这一天新建任务"
                onClicked: window.calendar.newTask()
            }
            Text {
                visible: dayList.count === 0 && !window.tasks.draftVisible
                anchors.centerIn: parent
                text: "这一天，留些空白。"; font.pixelSize: 14; color: "#b39772"
            }
            ListView {
                id: dayList
                objectName: "calendarDayList"
                x: 10; width: parent.width - 20
                anchors.top: parent.top; anchors.topMargin: 54
                anchors.bottom: dayEditor.visible ? dayEditor.top : message.top
                anchors.bottomMargin: 10
                clip: true; spacing: 8
                model: window.calendar.dayModel
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { width: 4 }
                delegate: TaskCard { width: ListView.view.width; tasks: window.tasks; calendarMode: true }
            }
            TaskEditor {
                id: dayEditor
                x: 8; width: parent.width - 16
                anchors.bottom: message.top; anchors.bottomMargin: 8
                tasks: window.tasks
            }
            Item {
                id: message
                x: 12; width: parent.width - 24
                height: window.tasks.message ? Math.max(32, messageText.implicitHeight + 12) : 8
                anchors.bottom: parent.bottom; anchors.bottomMargin: 8
                Text {
                    id: messageText
                    width: parent.width - (undo.visible ? 50 : 0)
                    anchors.verticalCenter: parent.verticalCenter
                    text: window.tasks.message; textFormat: Text.PlainText; wrapMode: Text.Wrap
                    font.pixelSize: 11; color: window.tasks.isError ? "#ad6547" : "#a1805c"
                }
                Button {
                    id: undo
                    visible: window.tasks.canUndo
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    text: "撤销"; width: 44; height: 30
                    onClicked: window.tasks.undo()
                    background: null
                    contentItem: Text { text: parent.text; color: "#946431"; font.pixelSize: 12; verticalAlignment: Text.AlignVCenter }
                }
            }
        }
    }
}
