import QtQuick

Item {
    id: mascot
    property bool highlighted: false
    property string expression: ""
    property real eyeHeight: highlighted ? 15 : 10
    readonly property bool happy: expression === "received" || expression === "completed"
    Behavior on eyeHeight { NumberAnimation { duration: 150 } }

    Image {
        anchors.fill: parent
        source: "../assets/star-body.svg"
        sourceSize: Qt.size(256, 256)
        fillMode: Image.PreserveAspectFit
        smooth: true
    }
    Image {
        objectName: "starGlow"
        anchors.fill: parent
        source: "../assets/star-rim.svg"
        sourceSize: Qt.size(256, 256)
        fillMode: Image.PreserveAspectFit
        smooth: true
        opacity: mascot.highlighted ? 1 : (mascot.happy ? 0.65 : 0)
        Behavior on opacity { NumberAnimation { duration: 240; easing.type: Easing.InOutQuad } }
    }
    Item {
        anchors.centerIn: parent
        width: 100
        height: 100
        scale: Math.min(mascot.width, mascot.height) / 100
        Repeater {
            model: [32, 68]
            Rectangle {
                required property real modelData
                x: modelData - 6
                y: 54
                width: 12
                height: 7
                radius: 6
                color: "#ee9975"
                opacity: mascot.happy ? 0.65 : 0.46
            }
        }
        Repeater {
            model: [36, 58]
            Rectangle {
                required property real modelData
                x: modelData
                y: 48 - height / 2
                width: mascot.highlighted ? 7 : 6
                height: mascot.eyeHeight
                radius: width / 2
                color: "#69442e"
                visible: mascot.expression !== "completed"
                Rectangle { x: 1.2; y: 1.5; width: 2; height: 2; radius: 1; color: "#fff7dd" }
            }
        }
        Canvas {
            id: smile
            anchors.fill: parent
            onPaint: {
                const ctx = getContext("2d")
                ctx.reset()
                ctx.strokeStyle = "#815039"
                ctx.lineWidth = 2.4
                ctx.lineCap = "round"
                ctx.beginPath()
                if (mascot.expression === "completed") {
                    ctx.moveTo(35, 49); ctx.quadraticCurveTo(39, 43, 43, 49)
                    ctx.moveTo(57, 49); ctx.quadraticCurveTo(61, 43, 65, 49)
                }
                ctx.moveTo(mascot.happy ? 42 : 44, 58)
                ctx.quadraticCurveTo(50, mascot.happy ? 70 : 65, mascot.happy ? 58 : 56, 58)
                ctx.stroke()
            }
        }
    }
    onExpressionChanged: smile.requestPaint()
}
