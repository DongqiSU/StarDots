"""创建 Qt 应用，连接窗口、任务状态与本地存储。"""

from dataclasses import dataclass
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QPoint, Property, Signal, Slot, QUrl, QTimer, Qt, QStandardPaths, QLockFile
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent, QQmlEngine
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QMessageBox

from stardot.geometry import settle_star_position, nearest_screen
from stardot.storage import TaskStore
from stardot.tasks import TaskController
from stardot.calendar import CalendarController
from stardot.desktop import DesktopServices
from stardot.reminders import ReminderService
from stardot import __version__


PACKAGE_DIR = Path(__file__).resolve().parent


class AppController(QObject):
    """只管理交互状态和窗口位置；绘制交给 QML。"""

    panelVisibleChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._panel_visible = False
        self._star: QQuickWindow | None = None
        self._panel: QQuickWindow | None = None
        self.before_panel_close = None
        self.engine = self.tasks = self.desktop = self.calendar = None
        self._calendar_window = self._settings_window = None
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.setInterval(120)
        self._settle_timer.timeout.connect(self._settle_after_release)

    @Property(bool, notify=panelVisibleChanged)
    def panelVisible(self) -> bool:
        return self._panel_visible

    def attach_windows(self, star: QQuickWindow, panel: QQuickWindow) -> None:
        self._star, self._panel = star, panel
        star.xChanged.connect(self._position_panel)
        star.yChanged.connect(self._position_panel)
        star.screenChanged.connect(self._position_panel)
        star.xChanged.connect(self.queueStarSettlement)
        star.yChanged.connect(self.queueStarSettlement)
        app = QApplication.instance()
        for screen in app.screens():
            screen.availableGeometryChanged.connect(self.queueStarSettlement)
        app.screenAdded.connect(self._screen_added)
        app.screenRemoved.connect(self.queueStarSettlement)
        self._position_panel()

    def _screen_added(self, screen) -> None:
        screen.availableGeometryChanged.connect(self.queueStarSettlement)
        self.queueStarSettlement()

    @Slot()
    def queueStarSettlement(self, *_args) -> None:
        self._settle_timer.start()

    def _settle_after_release(self) -> None:
        if self._mouse_is_down():
            self._settle_timer.start()
            return
        self.settleStar()

    @staticmethod
    def _mouse_is_down() -> bool:
        # 原生移动期间 Qt 不一定收到鼠标松开事件，Windows 查询真实按键状态。
        if sys.platform == "win32":
            import ctypes
            return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        return bool(QApplication.mouseButtons() & Qt.LeftButton)

    @Slot()
    def settleStar(self) -> None:
        if self._star is None:
            return
        screen = nearest_screen(self._star.geometry(), QApplication.screens())
        if screen is not None:
            point = settle_star_position(self._star.geometry(), screen.availableGeometry())
            if point != self._star.position():
                self._star.setPosition(point)
            if self.desktop is not None:
                self.desktop.savePosition(self._star, screen)
        self._position_panel()

    @Slot()
    def togglePanel(self) -> None:
        self._set_panel_visible(not self._panel_visible)

    @Slot()
    def hidePanel(self) -> None:
        self._set_panel_visible(False)

    @Slot()
    def showPanel(self) -> None:
        if not self._close_calendar():
            return
        if self._star is not None:
            self._star.show()
        self._set_panel_visible(True)

    @Slot()
    def quitApp(self) -> None:
        QApplication.inputMethod().commit()
        if self.before_panel_close and not self.before_panel_close():
            return
        self.settleStar()
        QApplication.instance().quit()

    @Slot()
    def revealStar(self):
        if self._star:
            self._star.show()
            self.settleStar()
            self._star.raise_()

    @Slot()
    def hideStar(self):
        self.hidePanel()
        if self._panel_visible or not self._close_calendar():
            return
        if self._star:
            self._star.hide()

    @Slot()
    def showEditor(self):
        if self._calendar_window:
            self._calendar_window.raise_()
            self._calendar_window.requestActivate()
        else:
            self.showPanel()

    def _create_window(self, filename, properties, width, height):
        component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(PACKAGE_DIR / "qml" / filename)))
        window = component.createWithInitialProperties(properties)
        if window is None:
            self.tasks._notify("窗口载入失败：" + "; ".join(e.toString() for e in component.errors()), error=True)
            return None
        QQmlEngine.setObjectOwnership(window, QQmlEngine.CppOwnership)
        QObject.setParent(window, self.engine)
        # 动态组件持有 QML 上下文，必须与窗口同寿命。
        component.setParent(window)
        area = (self._star.screen() or QApplication.primaryScreen()).availableGeometry()
        window.setWidth(min(width, area.width() - 24))
        window.setHeight(min(height, area.height() - 24))
        window.setPosition(area.x() + (area.width() - window.width()) // 2,
                           area.y() + (area.height() - window.height()) // 2)
        window.show()
        window.raise_()
        window.requestActivate()
        return window

    @Slot()
    def showCalendar(self):
        self.revealStar()
        self.hidePanel()
        if self._panel_visible:
            return
        if not self._calendar_window:
            self.calendar.refresh()
            self._calendar_window = self._create_window("CalendarWindow.qml", {
                "controller": self, "tasks": self.tasks, "calendar": self.calendar}, 1060, 760)
        if self._calendar_window:
            self._calendar_window.raise_()
            self._calendar_window.requestActivate()
        self.tasks.setPanelVisible(self._calendar_window is not None)

    def _close_calendar(self):
        if self._calendar_window:
            QApplication.inputMethod().commit()
            if not self.before_panel_close():
                return False
            window, self._calendar_window = self._calendar_window, None
            window.hide()
            window.deleteLater()
            self.tasks.setPanelVisible(self.panelVisible)
        return True

    @Slot()
    def closeCalendar(self):
        self._close_calendar()

    @Slot()
    def showSettings(self):
        self.hidePanel()
        if self._panel_visible or not self._close_calendar():
            return
        if not self._settings_window:
            self._settings_window = self._create_window("SettingsWindow.qml", {
                "controller": self, "desktop": self.desktop}, 520, 560)
        elif self._settings_window:
            self._settings_window.show()
            self._settings_window.raise_()
            self._settings_window.requestActivate()

    @Slot()
    def closeSettings(self):
        if self._settings_window:
            window, self._settings_window = self._settings_window, None
            window.hide()
            window.deleteLater()

    def _set_panel_visible(self, visible: bool) -> None:
        if visible and not self._close_calendar():
            return
        if not visible and self._panel_visible and self.before_panel_close is not None:
            # 单击窗口按钮时先提交输入法的组词，再保存 QML 已同步的文字。
            QApplication.inputMethod().commit()
            if not self.before_panel_close():
                return
        self._position_panel()
        if visible != self._panel_visible:
            self._panel_visible = visible
            # QML 收到这个信号后，会重新读取 panelVisible。
            self.panelVisibleChanged.emit()
        if visible and self._panel is not None:
            self._panel.raise_()
            self._panel.requestActivate()

    def _position_panel(self, *_signal_arguments: object) -> None:
        if self._star is None or self._panel is None:
            return

        star, panel = self._star, self._panel
        center = QPoint(star.x() + star.width() // 2, star.y() + star.height() // 2)
        screen = QApplication.screenAt(center) or star.screen()
        if screen is None:
            return
        area = screen.availableGeometry()
        gap, margin = 8, 12
        right_x = star.x() + star.width() + gap
        if right_x + panel.width() <= area.right() + 1 - margin:
            x = right_x
        else:
            x = star.x() - panel.width() - gap

        # Qt 窗口使用逻辑坐标；这里不额外乘显示缩放倍数。
        max_x = max(area.left() + margin, area.right() + 1 - panel.width() - margin)
        max_y = max(area.top() + margin, area.bottom() + 1 - panel.height() - margin)
        x = max(area.left() + margin, min(x, max_x))
        y = max(area.top() + margin, min(star.y() - 18, max_y))
        panel.setPosition(x, y)


@dataclass
class Runtime:
    """保留 Qt 对象的引用，确保它们与应用同寿命。"""

    app: QApplication
    engine: QQmlApplicationEngine
    controller: AppController
    star: QQuickWindow
    panel: QQuickWindow
    tray: QSystemTrayIcon
    tray_menu: QMenu
    tasks: TaskController
    store: TaskStore
    desktop: DesktopServices
    calendar: CalendarController
    reminders: ReminderService


def create_runtime(argv: list[str] | None = None, *, database_path: Path | None = None) -> Runtime:
    system_integrations = database_path is None
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Stardot")
    app.setApplicationVersion(__version__)
    app.setApplicationDisplayName("Stardot · 星点")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    icon = QIcon(str(PACKAGE_DIR / "assets" / "star.svg"))
    app.setWindowIcon(icon)
    QQuickStyle.setStyle("Basic")

    controller = AppController(app)
    database_path = database_path or Path(
        QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
    ) / "stardot.sqlite3"
    store = TaskStore(database_path)
    tasks = TaskController(store, app)
    calendar = CalendarController(tasks, app)
    desktop = DesktopServices(controller, tasks, database_path.parent / "settings.ini", app, enabled=system_integrations)
    controller.tasks, controller.desktop, controller.calendar = tasks, desktop, calendar
    controller.before_panel_close = tasks.finishDraft
    tasks.editorRequested.connect(controller.showEditor)
    controller.panelVisibleChanged.connect(lambda: tasks.setPanelVisible(controller.panelVisible))
    app.aboutToQuit.connect(store.close)
    engine = QQmlApplicationEngine(app)
    controller.engine = engine
    # 像给函数传参一样，把 Python 对象交给 QML 的 required 属性。
    engine.setInitialProperties({"controller": controller, "tasks": tasks})
    engine.load(QUrl.fromLocalFile(str(PACKAGE_DIR / "qml" / "Main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("无法加载 Stardot 界面，请查看上方 QML 错误。")

    star = engine.rootObjects()[0]
    panel = star.findChild(QQuickWindow, "taskPanel")
    if not isinstance(star, QQuickWindow) or panel is None:
        raise RuntimeError("界面缺少星星或清单窗口。")

    screen = app.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        star.setPosition(area.right() + 1 - star.width() - 24,
                         area.top() + round(area.height() * 0.36))
    controller.attach_windows(star, panel)
    desktop.restorePosition(star)
    controller.settleStar()

    tray_menu = QMenu()
    open_action = QAction("打开星点", tray_menu)
    open_action.triggered.connect(controller.showPanel)
    tray_menu.addAction(open_action)
    for title, callback in (("日历", controller.showCalendar), ("复制文字录入", desktop.captureClipboard),
                            ("显示星星", controller.revealStar), ("暂时隐藏星星", controller.hideStar),
                            ("设置与备份", controller.showSettings)):
        action = QAction(title, tray_menu)
        action.triggered.connect(callback)
        tray_menu.addAction(action)
    tray_menu.addSeparator()
    quit_action = QAction("退出 Stardot", tray_menu)
    quit_action.triggered.connect(controller.quitApp)
    tray_menu.addAction(quit_action)

    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("Stardot · 星点")
    tray.setContextMenu(tray_menu)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show()
        if system_integrations and "已被占用" in desktop.status:
            QTimer.singleShot(800, tray, lambda: tray.showMessage("星点 · 快捷键未启用", "快捷键被其他程序占用，请从托盘打开设置，更换组合。", QSystemTrayIcon.Information, 8000))
    app.aboutToQuit.connect(tray.hide)
    app.aboutToQuit.connect(desktop.close)
    tray.activated.connect(lambda reason: controller.showPanel() if reason == QSystemTrayIcon.DoubleClick else None)
    tray.messageClicked.connect(controller.showPanel)

    def notify(items):
        if not QSystemTrayIcon.isSystemTrayAvailable() or not QSystemTrayIcon.supportsMessages():
            return False
        title = "星点 · 任务提醒" if len(items) == 1 else f"星点 · {len(items)} 件事待提醒"
        lines = [f"{t.due_date} {t.due_time}  {t.body[:80]}" for t in items[:3]]
        if len(items) > 3:
            lines.append(f"另有 {len(items) - 3} 件，点击查看清单")
        tray.showMessage(title, "\n".join(lines), QSystemTrayIcon.Information, 10000)
        return True

    reminders = ReminderService(store, notify, app)
    reminders.failed.connect(lambda message: tasks._notify(message, error=True))
    if system_integrations:
        reminders.start()
        tasks.stateChanged.connect(reminders.start)
        desktop.resumed.connect(reminders.check)
    app.aboutToQuit.connect(reminders.timer.stop)
    star.show()
    return Runtime(app, engine, controller, star, panel, tray, tray_menu, tasks, store, desktop, calendar, reminders)


def main(*, database_path: Path | None = None) -> int:
    import sqlite3
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Stardot")
    directory = database_path.parent if database_path is not None else Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
    directory.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(directory / "instance.lock"))
    lock.setStaleLockTime(0)
    server_name = "Stardot-" + __import__("hashlib").sha256(str(directory).encode()).hexdigest()[:20]
    if not lock.tryLock(0):
        client = QLocalSocket()
        client.connectToServer(server_name)
        if client.waitForConnected(800):
            client.write(b"show")
            client.waitForBytesWritten(800)
        else:
            QMessageBox.information(None, "星点正在运行", "星点已经启动，请从系统托盘打开。")
        return 0
    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.UserAccessOption)
    server.listen(server_name)
    try:
        runtime = create_runtime(database_path=database_path)
    except (sqlite3.Error, OSError, ValueError, RuntimeError) as error:
        QMessageBox.critical(None, "Stardot 无法启动", f"无法载入界面或本地数据，现有数据未清除。\n\n{error}")
        return 1
    def activate():
        while server.hasPendingConnections():
            client = server.nextPendingConnection()
            client.disconnectFromServer()
            client.deleteLater()
        runtime.controller.showPanel()
    server.newConnection.connect(activate)
    # exec() 等待鼠标、键盘等事件，不是我们自己不断刷新界面的循环。
    return runtime.app.exec()
