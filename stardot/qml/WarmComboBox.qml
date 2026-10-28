import QtQuick
import QtQuick.Controls

ComboBox {
    id: control
    implicitHeight: 38
    leftPadding: 12
    rightPadding: 30
    background: Rectangle { radius: 10; color: "#fffdf8"; border.color: control.activeFocus ? "#c29862" : "#e4cda9" }
    contentItem: Text { text: control.displayText; color: "#7d5c3b"; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter }
    indicator: Canvas {
        x: control.width - 23; y: (control.height - height) / 2
        width: 12; height: 8
        onPaint: {
            const ctx = getContext("2d")
            ctx.strokeStyle = "#a98351"; ctx.lineWidth = 1.5
            ctx.beginPath(); ctx.moveTo(1, 1); ctx.lineTo(6, 6); ctx.lineTo(11, 1); ctx.stroke()
        }
    }
    delegate: ItemDelegate {
        required property string modelData
        required property int index
        objectName: "shortcutChoice-" + modelData
        width: control.width; height: 36
        highlighted: control.highlightedIndex === index
        background: Rectangle { radius: 8; color: parent.highlighted ? "#f7e4be" : "#fffaf0" }
        contentItem: Text { text: parent.modelData; color: "#81603d"; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter }
    }
    popup: Popup {
        y: control.height + 4
        width: control.width
        implicitHeight: contentItem.implicitHeight + 8
        padding: 4
        background: Rectangle { radius: 11; color: "#fffaf0"; border.color: "#e8d0ab" }
        contentItem: ListView {
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            clip: true
        }
    }
}
