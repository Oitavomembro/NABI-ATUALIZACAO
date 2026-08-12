from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")


class ReprintOpenIsolationTests(unittest.TestCase):
    def test_legacy_imports_isolated_file_opener(self):
        self.assertIn("from services.windows_file_opener import WindowsFileOpener", SOURCE)

    def test_pdf_open_path_does_not_call_os_startfile(self):
        block = SOURCE.split("def _abrir_arquivo_sistema", 1)[1].split("def _nome_pdf_seguro", 1)[0]
        self.assertIn("WindowsFileOpener", block)
        self.assertNotIn("os.startfile", block)

    def test_no_choice_still_opens_without_closing_application(self):
        block = SOURCE.split("def janela_acoes_pdf", 1)[1].split("def _parent_dialogo_ativo", 1)[0]
        self.assertIn("elif resposta is False", block)
        self.assertIn("self._abrir_arquivo_sistema(caminho_pdf)", block)
        self.assertNotIn("destroy()", block)
        self.assertNotIn("quit()", block)
