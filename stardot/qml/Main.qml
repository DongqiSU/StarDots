import QtQuick
import QtQuick.Controls

Window {
    id: starWindow
    required property QtObject controller
    required property QtObject tasks
    objectName: "starWindow"
    title: "Stardot · 星点"
    width: 84
    height: 84
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool

    StarMascot {
        id: desktopMascot
        objectName: "desktopMascot"
        anchors.fill: parent
        anchors.margins: 7
        highlighted: starHover.hovered || textDrop.containsDrag
    }

    Connections {
        target: starWindow.tasks
        function onFeedback(expression) {
            desktopMascot.expression = expression
            expressionTimer.restart()
        }
    }
    Timer {
        id: expressionTimer
        interval: 900
        onTriggered: desktopMascot.expression = ""
    }
    DropArea {
        id: textDrop
        objectName: "starDropArea"
        anchors.fill: parent
        onEntered: function(drag) {
            drag.accepted = drag.hasText && Boolean(drag.supportedActions & Qt.CopyAction)
        }
        onDropped: function(drop) {
            if (drop.hasText && (drop.supportedActions & Qt.CopyAction)
                    && starWindow.tasks.receiveText(drop.text)) {
                drop.accept(Qt.CopyAction)
            } else {
                drop.accepted = false
                starWindow.controller.showPanel()
            }
        }
    }

    HoverHandler {
        id: starHover
        cursorShape: Qt.PointingHandCursor
    }

    TapHandler {
        acceptedButtons: Qt.LeftButton
        onTapped: starWindow.controller.togglePanel()
    }

    DragHandler {
        target: null
        acceptedButtons: Qt.LeftButton
        onActiveChanged: {
            if (active)
                starWindow.startSystemMove()
            else
                starWindow.controller.queueStarSettlement()
        }
    }

    Shortcut {
        sequence: "Ctrl+Q"
        context: Qt.ApplicationShortcut
        onActivated: starWindow.controller.quitApp()
    }

    Window {
        id: panelWindow
        objectName: "taskPanel"
        title: "星点 · 清单"
        width: 376
        height: 600
        color: "transparent"
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        visible: false
        opacity: 0
        property bool awaitingEntrance: false

        Connections {
            target: starWindow.controller
            function onPanelVisibleChanged() {
                entrance.stop()
                if (starWindow.controller.panelVisible) {
                    // 原生窗口显示前就设为透明，防止旧帧先亮一下。
                    panelWindow.opacity = 0
                    card.scale = 0.985
                    panelWindow.awaitingEntrance = true
                    panelWindow.visible = true
                    panelWindow.update()
                } else {
                    panelWindow.opacity = 0
                    panelWindow.visible = false
                    panelWindow.awaitingEntrance = false
                }
            }
        }

        // 第一帧已经绘制好，才开始窗口整体淡入。
        onFrameSwapped: {
            if (awaitingEntrance && visible) {
                awaitingEntrance = false
                entrance.start()
            }
        }

        onClosing: function(close) {
            close.accepted = false
            starWindow.controller.hidePanel()
        }

        Shortcut {
            sequence: "Escape"
            enabled: panelWindow.visible
            onActivated: starWindow.controller.hidePanel()
        }

        Item {
            id: card
            objectName: "panelSurface"
            anchors.fill: parent
            anchors.margins: 10
            transformOrigin: panelWindow.x < starWindow.x ? Item.Right : Item.Left

            Rectangle {
                anchors.fill: parent
                anchors.topMargin: 5
                anchors.bottomMargin: -5
                radius: 27
                color: "#0b704422"
            }

            Rectangle {
                anchors.fill: parent
                radius: 25
                color: "#fffaf3"
                border.color: "#e9d9c8"
                border.width: 1

                Rectangle {
                    x: 1
                    y: 1
                    width: parent.width - 2
                    height: 128
                    radius: 24
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#fff0da" }
                        GradientStop { position: 1; color: "#fffaf3" }
                    }
                }

                Row {
                    x: 24
                    y: 26
                    spacing: 10

                    StarMascot { width: 32; height: 32; expression: desktopMascot.expression }

                    Text {
                        text: "星点"
                        color: "#60432f"
                        font.pixelSize: 23
                        font.weight: Font.DemiBold
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                IconButton {
                    objectName: "archiveButton"
                    anchors.right: parent.right
                    anchors.rightMargin: 100
                    y: 26
                    symbol: "folder"
                    label: starWindow.tasks.archiveVisible ? "返回待办" : "已完成"
                    selected: starWindow.tasks.archiveVisible
                    onClicked: starWindow.tasks.toggleArchive()
                }
                IconButton {
                    objectName: "newTaskButton"
                    anchors.right: parent.right
                    anchors.rightMargin: 60
                    y: 26
                    symbol: "add"
                    label: "记一件小事"
                    onClicked: {
                        Qt.inputMethod.commit()
                        starWindow.tasks.newTask()
                    }
                }
                IconButton {
                    objectName: "closePanelButton"
                    anchors.right: parent.right
                    anchors.rightMargin: 20
                    y: 26
                    width: 32
                    height: 32
                    label: "收起清单"
                    onClicked: starWindow.controller.hidePanel()
                }

                Text {
                    x: 26
                    y: 77
                    text: starWindow.tasks.archiveVisible
                        ? "已完成 · " + starWindow.tasks.archivedCount
                        : "待办 · " + starWindow.tasks.activeCount
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    color: "#aa8468"
                }

                Rectangle {
                    x: 24
                    y: 105
                    width: parent.width - 48
                    height: 1
                    color: "#eedfce"
                }
                Row {
                    anchors.right: parent.right
                    anchors.rightMargin: 20
                    y: 71
                    spacing: 8
                    IconButton {
                        objectName: "calendarButton"
                        width: 28; height: 28
                        symbol: "calendar"; label: "日历"
                        onClicked: starWindow.controller.showCalendar()
                    }
                    IconButton {
                        objectName: "settingsButton"
                        width: 28; height: 28
                        symbol: "settings"; label: "设置与备份"
                        onClicked: starWindow.controller.showSettings()
                    }
                }

                Column {
                    visible: taskList.count === 0 && !starWindow.tasks.draftVisible
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: 175
                    spacing: 14

                    StarMascot {
                        width: 84
                        height: 84
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Text {
                        text: starWindow.tasks.archiveVisible ? "完成的小事，会留在这里" : "还没有待办"
                        font.pixelSize: 19
                        font.weight: Font.Medium
                        color: "#795841"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }

                    Text {
                        text: starWindow.tasks.archiveVisible ? "每一步，都算数。" : "点击 +，或把文字拖到星星上。"
                        font.pixelSize: 13
                        color: "#a38b76"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }

                ListView {
                    id: taskList
                    objectName: "taskList"
                    x: 20
                    anchors.top: parent.top
                    anchors.topMargin: 122
                    width: parent.width - 40
                    anchors.bottom: editor.visible ? editor.top : messageBar.top
                    anchors.bottomMargin: 12
                    clip: true
                    spacing: 10
                    model: starWindow.tasks.taskModel
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { width: 4 }
                    delegate: TaskCard {
                        width: ListView.view.width
                        tasks: starWindow.tasks
                    }
                    add: Transition {
                        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 160 }
                    }
                }
                TaskEditor {
                    id: editor
                    x: 20
                    width: parent.width - 40
                    anchors.bottom: messageBar.top
                    anchors.bottomMargin: 12
                    tasks: starWindow.tasks
                }
                Rectangle {
                    id: messageBar
                    x: 20
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 18
                    width: parent.width - 40
                    height: starWindow.tasks.message ? Math.max(34, messageText.implicitHeight + 18) : 20
                    radius: 10
                    color: starWindow.tasks.message ? (starWindow.tasks.isError ? "#f9e3d7" : "#f2e8d8") : "transparent"
                    Text {
                        id: messageText
                        x: 10
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - (undoButton.visible ? 75 : 20)
                        text: starWindow.tasks.message
                        textFormat: Text.PlainText
                        color: starWindow.tasks.isError ? "#9b5540" : "#937756"
                        font.pixelSize: 11
                        wrapMode: Text.Wrap
                    }
                    Button {
                        id: undoButton
                        objectName: "undoButton"
                        anchors.right: parent.right
                        anchors.rightMargin: 5
                        anchors.verticalCenter: parent.verticalCenter
                        visible: starWindow.tasks.canUndo
                        text: "撤销"
                        onClicked: starWindow.tasks.undo()
                        background: null
                        contentItem: Text { text: parent.text; color: "#946431"; font.pixelSize: 12 }
                    }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 23
                    text: "S T A R D O T"
                    visible: !starWindow.tasks.message
                    font.pixelSize: 10
                    color: "#c2a78c"
                }
            }
        }

        ParallelAnimation {
            id: entrance
            NumberAnimation {
                target: panelWindow
                property: "opacity"
                from: 0
                to: 1
                duration: 160
            }
            NumberAnimation {
                target: card
                property: "scale"
                from: 0.985
                to: 1
                duration: 180
                easing.type: Easing.OutCubic
            }
        }
    }
}
