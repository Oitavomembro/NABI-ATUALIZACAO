import ast
import unittest
from pathlib import Path


class TransparentCanvasRegressionTests(unittest.TestCase):
    def test_canvas_nao_recebe_transparent_diretamente(self):
        source = Path(__file__).resolve().parents[1].joinpath("nabicode_legacy.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        target = classes["BidirectionalScrollableFrame"]
        init = next(node for node in target.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
        init_source = ast.get_source_segment(source, init) or ""
        self.assertIn("_resolve_canvas_background", init_source)
        self.assertNotIn('bg="transparent"', init_source)

    def test_resolvedor_tem_fallback_concreto(self):
        source = Path(__file__).resolve().parents[1].joinpath("nabicode_legacy.py").read_text(encoding="utf-8")
        self.assertIn('candidate = ("#f2f2f2", "#242424")', source)
        self.assertIn('candidate in (None, "", "transparent")', source)


if __name__ == "__main__":
    unittest.main()
