import QtQuick
import QtQuick.Controls

Button {
    id: control
    property string symbol: "close"
    property string label: ""
    property bool selected: false
    implicitWidth: 32
    implicitHeight: 32
    padding: 0
    Accessible.name: label
    ToolTip.visible: hovered
    ToolTip.delay: 600
    ToolTip.timeout: 2500
    ToolTip.text: label
    background: Rectangle {
        radius: 11
        color: control.selected ? "#f5dba8" : (control.hovered ? "#efdfcc" : "#f7ebdd")
        Behavior on color { ColorAnimation { duration: 100 } }
    }
    contentItem: Canvas {
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.save()
            ctx.translate(width / 2 - 10, height / 2 - 10)
            ctx.strokeStyle = "#89684e"
            ctx.lineWidth = 1.6
            ctx.lineCap = "round"
            ctx.lineJoin = "round"
            ctx.beginPath()
            if (control.symbol === "folder") {
                ctx.moveTo(2, 6); ctx.lineTo(2, 4); ctx.lineTo(8, 4)
                ctx.lineTo(10, 7); ctx.lineTo(18, 7); ctx.lineTo(18, 16)
                ctx.lineTo(2, 16); ctx.closePath()
                ctx.moveTo(2, 8); ctx.lineTo(8, 8)
            } else if (control.symbol === "add") {
                ctx.moveTo(10, 4); ctx.lineTo(10, 16)
                ctx.moveTo(4, 10); ctx.lineTo(16, 10)
            } else if (control.symbol === "calendar") {
                ctx.moveTo(5, 5); ctx.lineTo(15, 5)
                ctx.quadraticCurveTo(17, 5, 17, 7)
                ctx.lineTo(17, 15); ctx.quadraticCurveTo(17, 17, 15, 17)
                ctx.lineTo(5, 17); ctx.quadraticCurveTo(3, 17, 3, 15)
                ctx.lineTo(3, 7); ctx.quadraticCurveTo(3, 5, 5, 5)
                ctx.moveTo(3, 9); ctx.lineTo(17, 9)
                ctx.moveTo(7, 3); ctx.lineTo(7, 6)
                ctx.moveTo(13, 3); ctx.lineTo(13, 6)
                ctx.moveTo(7, 12); ctx.lineTo(9, 12)
            } else if (control.symbol === "clock") {
                ctx.arc(10, 10, 7, 0, Math.PI * 2)
                ctx.moveTo(10, 6); ctx.lineTo(10, 10); ctx.lineTo(13, 12)
            } else if (control.symbol === "previous") {
                ctx.moveTo(12, 5); ctx.lineTo(7, 10); ctx.lineTo(12, 15)
            } else if (control.symbol === "next") {
                ctx.moveTo(8, 5); ctx.lineTo(13, 10); ctx.lineTo(8, 15)
            } else if (control.symbol === "trash") {
                ctx.moveTo(4, 5); ctx.lineTo(16, 5)
                ctx.moveTo(7, 5); ctx.lineTo(7, 3); ctx.lineTo(13, 3); ctx.lineTo(13, 5)
                ctx.moveTo(5, 7); ctx.lineTo(6, 17); ctx.lineTo(14, 17); ctx.lineTo(15, 7)
                ctx.moveTo(8, 8); ctx.lineTo(8, 14)
                ctx.moveTo(12, 8); ctx.lineTo(12, 14)
            } else if (control.symbol === "bell") {
                ctx.moveTo(4, 14); ctx.quadraticCurveTo(6, 12, 6, 8)
                ctx.bezierCurveTo(6, 2, 14, 2, 14, 8)
                ctx.quadraticCurveTo(14, 12, 16, 14); ctx.closePath()
                ctx.moveTo(8, 17); ctx.quadraticCurveTo(10, 19, 12, 17)
            } else if (control.symbol === "settings") {
                ctx.moveTo(3, 5); ctx.lineTo(17, 5)
                ctx.moveTo(3, 10); ctx.lineTo(17, 10)
                ctx.moveTo(3, 15); ctx.lineTo(17, 15)
                ctx.moveTo(7, 3); ctx.lineTo(7, 7)
                ctx.moveTo(13, 8); ctx.lineTo(13, 12)
                ctx.moveTo(8, 13); ctx.lineTo(8, 17)
            } else if (control.symbol === "list") {
                for (let y = 5; y <= 15; y += 5) {
                    ctx.moveTo(3, y); ctx.lineTo(4, y)
                    ctx.moveTo(8, y); ctx.lineTo(17, y)
                }
            } else if (control.symbol === "check") {
                ctx.moveTo(4, 10); ctx.lineTo(8, 14); ctx.lineTo(16, 5)
            } else {
                ctx.moveTo(6, 6); ctx.lineTo(14, 14)
                ctx.moveTo(14, 6); ctx.lineTo(6, 14)
            }
            ctx.stroke()
            ctx.restore()
        }
    }
}
