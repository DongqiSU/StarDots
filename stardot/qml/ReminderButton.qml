import QtQuick
import QtQuick.Controls

IconButton {
    id: control
    property int minutes: 10
    signal chosen(int value)
    symbol: "bell"
    width: 28; height: 28
    selected: minutes >= 0
    opacity: minutes < 0 ? 0.65 : 1
    label: minutes < 0 ? "提醒已关闭" : (minutes === 0 ? "准时提醒" : "提前 " + minutes + " 分钟提醒")
    onClicked: options.open()
    onVisibleChanged: if (!visible) options.close()
    Menu {
        id: options
        objectName: "reminderMenu"
        y: -height - 6
        width: 160
        background: Rectangle { color: "#fffaf1"; radius: 12; border.color: "#e8cfad" }
        Repeater {
            model: [{label: "提前 10 分钟", value: 10}, {label: "提前 30 分钟", value: 30},
                    {label: "准时", value: 0}, {label: "关闭提醒", value: -1}]
            MenuItem {
                required property var modelData
                objectName: "reminderChoice-" + modelData.value
                text: modelData.label
                checkable: true
                checked: control.minutes === modelData.value
                onTriggered: control.chosen(modelData.value)
                indicator: Text { x: 8; anchors.verticalCenter: parent.verticalCenter; text: parent.checked ? "✓" : ""; color: "#a47a3d"; font.pixelSize: 13 }
                background: Rectangle { radius: 8; color: parent.highlighted ? "#f5e3c5" : "transparent" }
                contentItem: Text { text: parent.text; leftPadding: 24; color: "#79583d"; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter }
            }
        }
    }
}
