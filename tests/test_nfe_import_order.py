import subprocess
import sys


def test_repositorio_pode_ser_importado_antes_de_services():
    result = subprocess.run(
        [sys.executable, "-c", "from repositories import NFeImportRepository; from services import NFeImportService"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

