import QtQuick
import QtQuick.Controls

Button {
    id: control
    implicitHeight: 38
    implicitWidth: Math.max(90, label.implicitWidth + 30)
    padding: 12
    background: Rectangle {
        radius: 11
        color: control.down ? "#edc98f" : (control.hovered ? "#f4d9ad" : "#f6e5c9")
        border.color: control.activeFocus ? "#bd945e" : "#efdab8"
        Behavior on color { ColorAnimation { duration: 100 } }
    }
    contentItem: Text {
        id: label
        text: control.text
        font.pixelSize: 13
        color: "#81603d"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
