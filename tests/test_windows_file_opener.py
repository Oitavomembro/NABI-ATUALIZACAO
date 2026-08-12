from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from services.windows_file_opener import WindowsFileOpenError, WindowsFileOpener


class WindowsFileOpenerTests(unittest.TestCase):
    def test_command_uses_external_powershell_start_process(self):
        opener = WindowsFileOpener(is_windows=True)
        command = opener.command(Path("comprovante.pdf"))
        self.assertEqual(command[:4], ["powershell", "-NoProfile", "-NonInteractive", "-Command"])
        self.assertIn("Start-Process", command[-1])
        self.assertNotIn("os.startfile", command[-1])

    def test_open_dispatches_without_waiting_inside_python(self):
        with TemporaryDirectory() as temp_dir:
            pdf = Path(temp_dir) / "comprovante.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            runner = Mock()
            opener = WindowsFileOpener(runner=runner, is_windows=True)
            result = opener.open(pdf)
            self.assertEqual(result, str(pdf.resolve()))
            runner.assert_called_once()

    def test_missing_file_is_rejected(self):
        opener = WindowsFileOpener(is_windows=True)
        with self.assertRaises(FileNotFoundError):
            opener.open("arquivo-inexistente.pdf")

    def test_non_windows_is_rejected(self):
        with TemporaryDirectory() as temp_dir:
            pdf = Path(temp_dir) / "comprovante.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            opener = WindowsFileOpener(is_windows=False)
            with self.assertRaises(WindowsFileOpenError):
                opener.open(pdf)
