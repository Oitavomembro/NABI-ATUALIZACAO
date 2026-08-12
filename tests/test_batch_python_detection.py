from pathlib import Path
import unittest


class BatchPythonDetectionTests(unittest.TestCase):
    def test_scripts_detect_py_or_python_without_stale_errorlevel(self):
        root = Path(__file__).resolve().parents[1]
        scripts = [
            "ATUALIZAR_DEPENDENCIAS.bat",
            "GERAR_EXE_FINAL.bat",
            "GERAR_EXE_DEBUG.bat",
            "GERAR_EXE_TESTE.bat",
            "GERAR_INSTALLADOR.bat",
            "BACKUP_BANCO.bat",
            "EXECUTAR_TESTES.bat",
        ]
        for name in scripts:
            text = (root / name).read_text(encoding="utf-8-sig")
            self.assertIn('where py >nul 2>nul && set "PYTHON_CMD=py"', text, name)
            self.assertIn('if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"', text, name)
            self.assertIn('if not defined PYTHON_CMD (', text, name)
            self.assertNotIn('if %errorlevel%==0', text, name)


if __name__ == "__main__":
    unittest.main()
