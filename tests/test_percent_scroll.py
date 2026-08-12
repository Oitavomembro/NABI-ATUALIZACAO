import unittest

from core.scroll_utils import PercentScrollController


class PercentScrollControllerTests(unittest.TestCase):
    def test_clamp_limits(self):
        self.assertEqual(PercentScrollController.clamp(-1), 0.0)
        self.assertEqual(PercentScrollController.clamp(2), 1.0)
        self.assertEqual(PercentScrollController.clamp(0.45), 0.45)

    def test_advance_is_bounded(self):
        self.assertEqual(PercentScrollController.advance(0.98, 5), 1.0)
        self.assertEqual(PercentScrollController.advance(0.02, -5), 0.0)
        self.assertAlmostEqual(PercentScrollController.advance(0.5, 5), 0.55)

    def test_percent(self):
        self.assertEqual(PercentScrollController.percent(0), 0)
        self.assertEqual(PercentScrollController.percent(0.5), 50)
        self.assertEqual(PercentScrollController.percent(1), 100)

    def test_viewport_percent_uses_real_scrollable_range(self):
        self.assertEqual(PercentScrollController.viewport_percent(0.0, 0.25), 0)
        self.assertEqual(PercentScrollController.viewport_percent(0.375, 0.625), 50)
        self.assertEqual(PercentScrollController.viewport_percent(0.75, 1.0), 100)

    def test_viewport_percent_without_overflow_is_zero(self):
        self.assertEqual(PercentScrollController.viewport_percent(0.0, 1.0), 0)

    def test_moveto_for_percent_respects_visible_fraction(self):
        self.assertEqual(PercentScrollController.moveto_for_percent(0, 0.0, 0.25), 0.0)
        self.assertAlmostEqual(PercentScrollController.moveto_for_percent(50, 0.0, 0.25), 0.375)
        self.assertAlmostEqual(PercentScrollController.moveto_for_percent(100, 0.0, 0.25), 0.75)

    def test_wheel_direction(self):
        self.assertEqual(PercentScrollController.wheel_direction(120), -1)
        self.assertEqual(PercentScrollController.wheel_direction(-120), 1)
        self.assertEqual(PercentScrollController.wheel_direction(0), 0)


if __name__ == "__main__":
    unittest.main()
