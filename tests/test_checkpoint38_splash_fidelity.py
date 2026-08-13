from __future__ import annotations

import ast
import hashlib
import unittest
from pathlib import Path

from splash_screen import (
    BRAND,
    DURATION,
    FPS,
    LOGICAL_HEIGHT,
    LOGICAL_WIDTH,
    NAME_STAR_COUNT,
    RARE_STAR_COUNT,
    STAR_COUNT,
    LightspeedSplash,
)


ROOT = Path(__file__).resolve().parents[1]
SPLASH_PATH = ROOT / "splash_screen.py"
ENGINE_PATH = ROOT / "splash_deep_trust_engine.py"
PROTOTYPE_PATH = ROOT / "build_tools" / "references" / "splash_nabicode_deep_trust_fluid.py"
SPLASH_SOURCE = SPLASH_PATH.read_text(encoding="utf-8")
ENGINE_BYTES = ENGINE_PATH.read_bytes()
ENGINE_SOURCE = ENGINE_BYTES.decode("utf-8")
PROTOTYPE_BYTES = PROTOTYPE_PATH.read_bytes()
MAIN_SOURCE = (ROOT / "main.py").read_text(encoding="utf-8")
SPEC_SOURCE = (ROOT / "build_tools" / "pyinstaller" / "nabicode.spec").read_text(encoding="utf-8")
LOCK_SOURCE = (ROOT / "build_tools" / "requirements-windows.lock").read_text(encoding="utf-8")


def numeric_constants(source: str) -> dict[str, object]:
    values: dict[str, object] = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name):
            try:
                values[target.id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
        elif isinstance(target, ast.Tuple):
            try:
                unpacked = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            for item, value in zip(target.elts, unpacked):
                if isinstance(item, ast.Name):
                    values[item.id] = value
    return values


class Checkpoint38SplashFidelityTests(unittest.TestCase):
    def test_01_runtime_engine_is_byte_for_byte_the_approved_prototype(self):
        self.assertEqual(ENGINE_BYTES, PROTOTYPE_BYTES)
        self.assertEqual(
            hashlib.sha256(ENGINE_BYTES).hexdigest(),
            "6697892a47dafc0430bc3b742c6effa7c5418c138055c2c083cfebb004574838",
        )

    def test_02_only_nabicode_is_rendered_as_visual_text(self):
        self.assertEqual(BRAND, "NABICODE")
        self.assertEqual(ENGINE_SOURCE.count("font.render(text"), 1)
        self.assertIn('build_text_points("NABICODE",96,3)', ENGINE_SOURCE)
        for forbidden in ("CARREGANDO", "SLOGAN", "store_name", "nome_loja"):
            self.assertNotIn(forbidden, ENGINE_SOURCE)
            self.assertNotIn(forbidden, SPLASH_SOURCE)

    def test_03_name_colors_and_glow_are_exactly_from_the_prototype(self):
        for color in (
            "(255,255,255)",
            "(248,252,255)",
            "(238,247,255)",
            "(230,243,255)",
        ):
            self.assertIn(color, ENGINE_SOURCE)
        self.assertIn("lerp(br,255,assembled*0.98)", ENGINE_SOURCE)
        self.assertIn("lerp(bg,255,assembled*0.98)", ENGINE_SOURCE)
        self.assertIn("lerp(bb,255,assembled*0.99)", ENGINE_SOURCE)
        self.assertIn("(240,255,253,int((13+31*sweep)*assembled*fade))", ENGINE_SOURCE)

    def test_04_timeline_and_name_formation_match_prototype(self):
        self.assertEqual(DURATION, 12.2)
        self.assertEqual(LightspeedSplash.timeline(4.45)[3], 0.0)
        self.assertEqual(LightspeedSplash.timeline(4.70)[3], 0.0)
        self.assertGreater(LightspeedSplash.timeline(5.20)[3], 0.08)
        self.assertEqual(LightspeedSplash.timeline(7.55)[3], 1.0)
        for expression in (
            "smooth((elapsed - 2.0) / 3.6)",
            "smooth((elapsed - 6.35) / 2.35)",
            "smooth((elapsed - 4.55) / 1.45)",
            "smooth((elapsed - 4.70) / 2.85)",
        ):
            self.assertIn(expression, SPLASH_SOURCE)

    def test_05_speed_curve_and_observed_extrema_match_prototype(self):
        self.assertIn("40.0 + 540.0 * warp ** 2.60", SPLASH_SOURCE)
        samples = [LightspeedSplash.timeline(index / 100.0)[2] for index in range(1221)]
        self.assertEqual(min(samples), 40.0)
        self.assertGreater(max(samples), 386.0)
        self.assertLess(max(samples), 387.0)
        self.assertAlmostEqual(LightspeedSplash.timeline(4.70)[2], 374.9008547, places=5)

    def test_06_density_resolution_mask_and_creation_order_match(self):
        prototype = numeric_constants(ENGINE_SOURCE)
        self.assertEqual(LOGICAL_WIDTH, prototype["W"])
        self.assertEqual(LOGICAL_HEIGHT, prototype["H"])
        self.assertEqual(FPS, prototype["FPS"])
        self.assertEqual(STAR_COUNT, prototype["STAR_COUNT"])
        self.assertEqual(NAME_STAR_COUNT, prototype["NAME_STAR_COUNT"])
        self.assertEqual(RARE_STAR_COUNT, 8)
        self.assertIn("self.engine.WarpStar()", SPLASH_SOURCE)
        self.assertIn("self.engine.RareStar()", SPLASH_SOURCE)
        self.assertIn("self.engine.build_text_points(BRAND, 96, 3)", SPLASH_SOURCE)

    def test_07_warp_and_name_motion_are_unmodified(self):
        for expression in (
            "0.10 * clamp((warp - 0.26) / 0.72)",
            "0.55 + 0.45*depth",
            "1 + (warp**1.65)*2.85",
            "1.0 - (1.0 - p)**2.25",
            "0.82 < p < 0.90",
        ):
            self.assertIn(expression, ENGINE_SOURCE)

    def test_08_helper_uses_pygame_clock_without_sleep_or_tk_event_loop(self):
        self.assertIn("self.clock.tick(self.engine.FPS)", SPLASH_SOURCE)
        self.assertIn("self.pygame.event.get()", SPLASH_SOURCE)
        self.assertIn("self.pygame.display.flip()", SPLASH_SOURCE)
        self.assertNotIn("time.sleep", SPLASH_SOURCE)
        self.assertNotIn("tkinter", SPLASH_SOURCE)
        self.assertNotIn("from PIL", SPLASH_SOURCE)

    def test_09_readiness_pause_parent_and_cleanup_contract_remain_intact(self):
        for expression in (
            "return min(active, READY_HOLD_AT)",
            "self.pause_file.exists()",
            "self._set_window_visible(False)",
            "self._set_window_visible(True)",
            "self._parent_is_alive()",
            "self.pygame.quit()",
        ):
            self.assertIn(expression, SPLASH_SOURCE)
        self.assertIn("_ensure_process_stopped(splash_process", MAIN_SOURCE)

    def test_10_pyinstaller_and_offline_lock_include_the_canonical_engine(self):
        self.assertIn('"pygame"', SPEC_SOURCE)
        self.assertIn('"splash_deep_trust_engine"', SPEC_SOURCE)
        self.assertIn("pygame-ce==2.5.7", LOCK_SOURCE)
        self.assertIn('"--splash-helper"', MAIN_SOURCE)
        self.assertIn('"--metadata-file"', MAIN_SOURCE)


if __name__ == "__main__":
    unittest.main()
