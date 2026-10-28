import unittest

from PySide6.QtCore import QPoint, QRect
from stardot.geometry import clamp_position, nearest_screen, settle_star_position


class Screen:
    def __init__(self, rect):
        self.rect = rect

    def geometry(self):
        return self.rect


class GeometryTests(unittest.TestCase):
    def test_star_snaps_visible_body_to_all_edges(self):
        available = QRect(-1920, -200, 1920, 1040)
        for original, expected in [
            ((-1920, 100), (-1929, 100)),
            ((-80, 100), (-75, 100)),
            ((-1000, -190), (-1000, -210)),
            ((-1000, 750), (-1000, 765)),
            ((-2300, -900), (-1929, -210)),
            ((500, 2000), (-75, 765)),
        ]:
            with self.subTest(original=original):
                position = settle_star_position(QRect(*original, 84, 84), available)
                self.assertEqual(position, QPoint(*expected))
                visible = QRect(position.x() + 11, position.y() + 12, 62, 61)
                self.assertTrue(available.adjusted(2, 2, -2, -2).contains(visible))

    def test_star_interior_does_not_move_and_snap_has_a_threshold(self):
        available = QRect(0, 0, 1920, 1040)
        self.assertEqual(settle_star_position(QRect(300, 250, 84, 84), available), QPoint(300, 250))
        # The left resting position is -9, so 15 is within the 24 px threshold.
        self.assertEqual(settle_star_position(QRect(15, 250, 84, 84), available), QPoint(-9, 250))
        self.assertEqual(settle_star_position(QRect(16, 250, 84, 84), available), QPoint(16, 250))

    def test_star_handles_tiny_work_area_and_scaled_window(self):
        tiny = QRect(-100, -50, 20, 18)
        position = settle_star_position(QRect(1000, 1000, 84, 84), tiny)
        self.assertEqual(position, QPoint(-132, -84))
        self.assertLessEqual(abs(position.x() + 42 - (tiny.x() + tiny.width() / 2)), 0.5)
        self.assertLessEqual(abs(position.y() + 42.5 - (tiny.y() + tiny.height() / 2)), 0.5)
        available = QRect(0, 0, 1920, 1040)
        self.assertEqual(settle_star_position(QRect(0, 0, 168, 168), available), QPoint(-20, -22))

    def test_all_edges_with_negative_screen_and_taskbar(self):
        available = QRect(-1920, -200, 1920, 1040)
        for x, y in [(-2000, -240), (-30, -240), (-2000, 830), (-30, 830), (800, 2000)]:
            star = QRect(x, y, 84, 84)
            star.moveTopLeft(clamp_position(star, available))
            self.assertTrue(available.adjusted(6, 6, -6, -6).contains(star))

    def test_cross_screen_and_disconnected_screen_recovery(self):
        left = Screen(QRect(-1920, 0, 1920, 1080))
        right = Screen(QRect(0, 0, 2560, 1440))
        self.assertIs(nearest_screen(QRect(-50, 200, 84, 84), [left, right]), left)
        self.assertIs(nearest_screen(QRect(5, 200, 84, 84), [left, right]), right)
        self.assertIs(nearest_screen(QRect(-2500, 500, 84, 84), [right]), right)
        self.assertIsNone(nearest_screen(QRect(), []))
