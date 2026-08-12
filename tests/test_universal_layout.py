import unittest

from core.universal_layout import UniversalLayoutPolicy


class UniversalLayoutPolicyTests(unittest.TestCase):
    def test_rejects_invalid_screen_size(self):
        with self.assertRaises(ValueError):
            UniversalLayoutPolicy.metrics(0, 1080)

    def test_keeps_window_inside_small_screen(self):
        metrics = UniversalLayoutPolicy.metrics(800, 600, preferred_width=1200, preferred_height=900)
        self.assertLessEqual(metrics.width, 800)
        self.assertLessEqual(metrics.height, 600)
        self.assertEqual(metrics.columns, 1)

    def test_never_exceeds_very_small_screen(self):
        metrics = UniversalLayoutPolicy.metrics(640, 480, preferred_width=1200, preferred_height=900)
        self.assertLessEqual(metrics.width, 640)
        self.assertLessEqual(metrics.height, 480)
        self.assertEqual(UniversalLayoutPolicy.safe_minsize(metrics), (metrics.width, metrics.height))

    def test_field_position_wraps_colspan_safely(self):
        self.assertEqual(UniversalLayoutPolicy.field_position(2, 3, colspan=2), (1, 0, 2))
        self.assertEqual(UniversalLayoutPolicy.field_position(0, 1, colspan=3), (0, 0, 1))

    def test_uses_three_columns_on_wide_window(self):
        metrics = UniversalLayoutPolicy.metrics(1920, 1080, preferred_width=1200, preferred_height=800)
        self.assertEqual(metrics.columns, 3)
        self.assertEqual(UniversalLayoutPolicy.geometry(metrics), f"{metrics.width}x{metrics.height}")


if __name__ == "__main__":
    unittest.main()
