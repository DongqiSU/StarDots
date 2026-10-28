"""窗口使用 Qt 逻辑坐标；允许负坐标屏幕，不手动乘 DPI。"""

from math import ceil, floor

from PySide6.QtCore import QPoint, QRect


def clamp_position(window: QRect, available: QRect, margin: int = 6) -> QPoint:
    left, top = available.left() + margin, available.top() + margin
    right = max(left, available.right() + 1 - window.width() - margin)
    bottom = max(top, available.bottom() + 1 - window.height() - margin)
    return QPoint(max(left, min(window.x(), right)), max(top, min(window.y(), bottom)))


def settle_star_position(
    window: QRect, available: QRect, *, snap_distance: int = 24, edge_gap: int = 2
) -> QPoint:
    """松手后，以可见星星而不是透明窗口边界吸附。

    Main.qml 的 84×84 窗口中，StarMascot 四周留 7 像素；SVG 本身也
    留有透明区域。含细小投影的可见边界为 [11, 73) × [12, 73)。
    这里随窗口尺寸缩放并向外取整，允许透明留白越界，星星本体始终
    留在工作区内。极小工作区容不下本体时居中，尽量保留可见部分。
    """
    if snap_distance < 0 or edge_gap < 0:
        raise ValueError("吸附距离和边距不能为负数")

    def settle_axis(position, start, length, body_start, body_end):
        minimum = start + edge_gap - body_start
        maximum = start + length - edge_gap - body_end
        if maximum < minimum:
            return round(start + length / 2 - (body_start + body_end) / 2)
        position = max(minimum, min(position, maximum))
        nearest_edge = min((minimum, maximum), key=lambda edge: abs(position - edge))
        return nearest_edge if abs(position - nearest_edge) <= snap_distance else position

    left = floor(window.width() * 11 / 84)
    right = ceil(window.width() * 73 / 84)
    top = floor(window.height() * 12 / 84)
    bottom = ceil(window.height() * 73 / 84)
    return QPoint(
        settle_axis(window.x(), available.x(), available.width(), left, right),
        settle_axis(window.y(), available.y(), available.height(), top, bottom),
    )


def nearest_screen(window: QRect, screens):
    """优先中心所在屏幕；完全移出桌面时选距离最近的屏幕。"""
    center = window.center()
    for screen in screens:
        if screen.geometry().contains(center):
            return screen
    def distance(screen):
        area = screen.geometry()
        x = max(area.left(), min(center.x(), area.right()))
        y = max(area.top(), min(center.y(), area.bottom()))
        return (center.x() - x) ** 2 + (center.y() - y) ** 2
    return min(screens, key=distance) if screens else None
