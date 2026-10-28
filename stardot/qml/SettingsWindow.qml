import QtQuick
import QtQuick.Controls

Window {
    id: window
    required property QtObject controller
    required property QtObject desktop
    objectName: "settingsWindow"
    title: "星点 · 设置与备份"
    width: 520; height: 560
    color: "#fff9ee"
    flags: Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
    onClosing: function(event) { event.accepted = false; controller.closeSettings() }
    Shortcut { sequence: "Escape"; onActivated: window.controller.closeSettings() }
    Text {
        x: 26; y: 26
        width: parent.width - 104
        text: "让星点更顺手"
        font.pixelSize: 24; font.weight: Font.DemiBold
        color: "#755235"
        elide: Text.ElideRight
    }
    IconButton {
        objectName: "closeSettingsButton"
        anchors.right: parent.right; anchors.rightMargin: 26
        y: 26
        symbol: "close"
        label: "关闭设置与备份"
        onClicked: window.controller.closeSettings()
    }
    ScrollView {
        anchors.fill: parent; anchors.margins: 26
        anchors.topMargin: 78
        clip: true
        contentWidth: availableWidth
        Column {
            width: parent.width; spacing: 18
            Text { text: "快捷键"; color: "#9c7954"; font.pixelSize: 14 }
            Row {
                spacing: 18
                Text { text: "复制文字录入"; color: "#846747"; width: 116; anchors.verticalCenter: parent.verticalCenter }
                WarmComboBox {
                    id: capture
                    objectName: "captureShortcutCombo"
                    width: 225
                    model: ["Ctrl+Alt+S", "Ctrl+Shift+S", "Ctrl+Alt+D"]
                    Component.onCompleted: currentIndex = model.indexOf(window.desktop.captureShortcut)
                }
            }
            Row {
                spacing: 18
                Text { text: "找回星星"; color: "#846747"; width: 116; anchors.verticalCenter: parent.verticalCenter }
                WarmComboBox {
                    id: reveal
                    width: 225
                    model: ["Ctrl+Alt+Space", "Ctrl+Shift+Space", "Ctrl+Alt+H"]
                    Component.onCompleted: currentIndex = model.indexOf(window.desktop.revealShortcut)
                }
            }
            Row {
                spacing: 10
                WarmButton { objectName: "saveShortcuts"; text: "保存快捷键"; onClicked: window.desktop.applyShortcuts(capture.currentText, reveal.currentText) }
                WarmButton { text: "暂时隐藏星星"; onClicked: window.controller.hideStar() }
            }
            Rectangle { width: parent.width; height: 1; color: "#ead8bc" }
            Text { text: "本地数据"; color: "#9c7954"; font.pixelSize: 14 }
            Row {
                spacing: 10
                WarmButton { text: "导出备份"; onClicked: window.desktop.exportBackup() }
                WarmButton { text: "恢复备份"; onClicked: window.desktop.importBackup() }
            }
            Text {
                width: parent.width
                text: "有具体时刻的任务默认提前 10 分钟提醒，可点铃铛修改。仅有日期的任务不提醒。\n\n请保持星点在托盘运行。睡眠唤醒或重新启动后，遗漏提醒会合并补发；系统勿扰模式可能隐藏通知。"
                wrapMode: Text.Wrap; font.pixelSize: 12; lineHeight: 1.35; color: "#ad906d"
            }
            Text {
                width: parent.width
                text: window.desktop.status
                textFormat: Text.PlainText; wrapMode: Text.WrapAnywhere
                color: "#99733f"; font.pixelSize: 12
            }
        }
    }
}
