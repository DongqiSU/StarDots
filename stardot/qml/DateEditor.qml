import QtQuick
import QtQuick.Controls

Item {
    id: dateEditor
    required property QtObject tasks
    height: 34
    function closePicker() {
        hourPicker.popup.close()
        minutePicker.popup.close()
        editPopup.close()
    }
    onVisibleChanged: { if (!visible) closePicker() }
    Connections {
        target: dateEditor.tasks
        function onDraftChanged() {
            if (!dateEditor.tasks.draftVisible)
                dateEditor.closePicker()
        }
    }
    component DatePart: Rectangle {
        required property string part
        required property string value
        width: numberLabel.implicitWidth + 8
        height: 28
        radius: 6
        color: pointer.containsMouse ? "#f5e4c6" : "transparent"
        Text {
            id: numberLabel
            anchors.centerIn: parent
            text: parent.value
            font.pixelSize: 12
            color: "#947342"
        }
        MouseArea {
            id: pointer
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: editPopup.open()
            onWheel: function(wheel) {
                if (wheel.angleDelta.y !== 0)
                    dateEditor.tasks.adjustSchedule(parent.part, wheel.angleDelta.y > 0 ? 1 : -1)
                wheel.accepted = true
            }
        }
        ToolTip.visible: pointer.containsMouse
        ToolTip.delay: 600
        ToolTip.timeout: 2500
        ToolTip.text: dateEditor.tasks.draftDate + (dateEditor.tasks.draftTime ? " " + dateEditor.tasks.draftTime : "") + " · 滚轮调整"
    }
    IconButton {
        id: dateButton
        objectName: "dateButton"
        anchors.verticalCenter: parent.verticalCenter
        width: 30; height: 30
        symbol: "calendar"
        label: dateEditor.tasks.parseNote || (dateEditor.tasks.draftDate ? "编辑日期" : "添加日期")
        onClicked: editPopup.open()
    }
    Row {
        id: values
        x: 32
        anchors.verticalCenter: parent.verticalCenter
        visible: dateEditor.tasks.draftDate.length > 0
        height: 28
        DatePart { objectName: "dateMonth"; part: "month"; value: dateEditor.tasks.draftDate.slice(5, 7) }
        Text { text: "/"; height: 28; verticalAlignment: Text.AlignVCenter; color: "#aa9169" }
        DatePart { objectName: "dateDay"; part: "day"; value: dateEditor.tasks.draftDate.slice(8, 10) }
        Item { width: 6; height: 1; visible: dateEditor.tasks.draftTime.length > 0 }
        DatePart { objectName: "dateHour"; visible: dateEditor.tasks.draftTime.length > 0; part: "hour"; value: dateEditor.tasks.draftTime.slice(0, 2) }
        Text { visible: dateEditor.tasks.draftTime.length > 0; text: ":"; height: 28; verticalAlignment: Text.AlignVCenter; color: "#aa9169" }
        DatePart { objectName: "dateMinute"; visible: dateEditor.tasks.draftTime.length > 0; part: "minute"; value: dateEditor.tasks.draftTime.slice(3, 5) }
        IconButton {
            objectName: "clearDateButton"
            width: 24; height: 28
            label: "取消日期"
            onClicked: dateEditor.tasks.clearDraftSchedule()
        }
    }
    Popup {
        id: editPopup
        objectName: "datePopup"
        x: 0
        y: -height - 8
        width: 292
        height: 342
        padding: 14
        focus: true
        property string selectedDay: ""
        property int displayedYear: new Date().getFullYear()
        property int displayedMonth: new Date().getMonth()
        property bool timeEnabled: false
        property int selectedHour: 9
        property int selectedMinute: 0
        readonly property int firstWeekday: (new Date(displayedYear, displayedMonth, 1).getDay() + 6) % 7
        function pad(value) { return String(value).padStart(2, "0") }
        function isoDate(day) {
            return day.getFullYear() + "-" + pad(day.getMonth() + 1) + "-" + pad(day.getDate())
        }
        function dayAt(index) {
            return new Date(displayedYear, displayedMonth, index - firstWeekday + 1)
        }
        function shiftMonth(offset) {
            const next = new Date(displayedYear, displayedMonth + offset, 1)
            displayedYear = next.getFullYear()
            displayedMonth = next.getMonth()
        }
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: "#fffaf1"; radius: 15; border.color: "#dfc79e" }
        onClosed: {
            hourPicker.popup.close()
            minutePicker.popup.close()
        }
        onAboutToShow: {
            const saved = dateEditor.tasks.draftDate
            const date = saved ? new Date(Number(saved.slice(0, 4)), Number(saved.slice(5, 7)) - 1, Number(saved.slice(8, 10))) : new Date()
            selectedDay = isoDate(date)
            displayedYear = date.getFullYear()
            displayedMonth = date.getMonth()
            const time = dateEditor.tasks.draftTime
            timeEnabled = time.length > 0
            selectedHour = time ? Number(time.slice(0, 2)) : 9
            selectedMinute = time ? Number(time.slice(3, 5)) : 0
        }
        IconButton {
            objectName: "previousMonthButton"
            width: 30; height: 30
            symbol: "previous"
            label: "上个月"
            onClicked: editPopup.shiftMonth(-1)
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            height: 30
            verticalAlignment: Text.AlignVCenter
            text: editPopup.displayedYear + " 年 " + (editPopup.displayedMonth + 1) + " 月"
            color: "#745235"
            font.pixelSize: 14
        }
        IconButton {
            objectName: "nextMonthButton"
            anchors.right: parent.right
            width: 30; height: 30
            symbol: "next"
            label: "下个月"
            onClicked: editPopup.shiftMonth(1)
        }
        Row {
            y: 40
            width: parent.width
            spacing: 2
            Repeater {
                model: ["一", "二", "三", "四", "五", "六", "日"]
                Text {
                    required property string modelData
                    width: 36; height: 20
                    text: modelData
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 11
                    color: "#ad9272"
                }
            }
        }
        Grid {
            id: dayGrid
            y: 65
            columns: 7
            spacing: 2
            Repeater {
                model: 42
                Button {
                    id: dayCell
                    required property int index
                    readonly property date cellDate: editPopup.dayAt(index)
                    readonly property string dayString: editPopup.isoDate(cellDate)
                    readonly property bool currentMonth: cellDate.getMonth() === editPopup.displayedMonth
                    readonly property bool chosen: dayString === editPopup.selectedDay
                    objectName: "calendarDay" + dayString
                    width: 36; height: 32
                    padding: 0
                    Accessible.name: dayString
                    onClicked: editPopup.selectedDay = dayString
                    background: Rectangle {
                        radius: 9
                        color: dayCell.chosen ? "#f4d69f" : (dayCell.hovered ? "#f7ead6" : "transparent")
                    }
                    contentItem: Text {
                        text: dayCell.cellDate.getDate()
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        color: dayCell.currentMonth ? "#725235" : "#baa58c"
                        font.pixelSize: 13
                        font.weight: dayCell.chosen ? Font.DemiBold : Font.Normal
                    }
                }
            }
        }
        component TimePicker: ComboBox {
            id: picker
            width: 64; height: 32
            padding: 0
            wheelEnabled: true
            indicator: null
            background: Rectangle {
                color: picker.hovered ? "#f7ead6" : "#fffdf9"
                radius: 8
                border.color: "#ead7b9"
            }
            contentItem: Text {
                text: editPopup.pad(picker.currentIndex)
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                color: "#745235"
                font.pixelSize: 13
            }
            delegate: ItemDelegate {
                required property int index
                width: picker.width
                height: 30
                padding: 0
                highlighted: picker.highlightedIndex === index
                background: Rectangle { color: parent.highlighted ? "#f5dfb8" : "transparent"; radius: 6 }
                contentItem: Text {
                    text: editPopup.pad(parent.index)
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    color: "#745235"
                    font.pixelSize: 13
                }
            }
            popup: Popup {
                y: -height - 4
                width: picker.width
                height: 186
                padding: 3
                background: Rectangle { color: "#fffaf1"; radius: 9; border.color: "#dfc79e" }
                contentItem: ListView {
                    clip: true
                    model: picker.popup.visible ? picker.delegateModel : null
                    currentIndex: picker.highlightedIndex
                    ScrollIndicator.vertical: ScrollIndicator {}
                }
            }
        }
        IconButton {
            objectName: "timeEnabledButton"
            y: 280
            symbol: "clock"
            label: editPopup.timeEnabled ? "取消时刻，仅保留日期" : "添加时刻"
            selected: editPopup.timeEnabled
            onClicked: editPopup.timeEnabled = !editPopup.timeEnabled
        }
        Text {
            x: 43; y: 280
            height: 32
            visible: !editPopup.timeEnabled
            verticalAlignment: Text.AlignVCenter
            text: "仅日期"
            color: "#ad9272"
            font.pixelSize: 12
        }
        TimePicker {
            id: hourPicker
            objectName: "hourPicker"
            x: 42; y: 280
            visible: editPopup.timeEnabled
            model: 24
            currentIndex: editPopup.selectedHour
            onActivated: editPopup.selectedHour = currentIndex
            Accessible.name: "小时"
        }
        Text {
            x: 110; y: 280
            width: 12; height: 32
            visible: editPopup.timeEnabled
            text: ":"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: "#a38a6e"
        }
        TimePicker {
            id: minutePicker
            objectName: "minutePicker"
            x: 126; y: 280
            visible: editPopup.timeEnabled
            model: 60
            currentIndex: editPopup.selectedMinute
            onActivated: editPopup.selectedMinute = currentIndex
            Accessible.name: "分钟"
        }
        IconButton {
            objectName: "applyDateButton"
            anchors.right: parent.right
            y: 280
            symbol: "check"
            label: "应用日期"
            selected: true
            onClicked: {
                const time = editPopup.timeEnabled ? editPopup.pad(editPopup.selectedHour) + ":" + editPopup.pad(editPopup.selectedMinute) : ""
                if (dateEditor.tasks.setDraftSchedule(editPopup.selectedDay, time))
                    editPopup.close()
            }
        }
    }
}
