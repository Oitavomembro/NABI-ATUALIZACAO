from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "build_tools" / "homologate_first_use.py"


def test_runner_homologa_jornada_completa_em_temp(tmp_path):
    active_appdata = tmp_path / "perfil-ativo-que-nao-deve-ser-tocado"
    sandbox = tmp_path / "ensaio"
    environment = dict(os.environ, APPDATA=str(active_appdata), QT_QPA_PLATFORM="offscreen")
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--root", str(sandbox)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert result["profile"] == "TESTE"
    assert result["license_absent_restricted"] is True
    assert result["ephemeral_license"]["state"] == "ATIVA"
    assert result["ephemeral_license"]["private_key_saved"] is False
    assert result["database_created"] is True
    assert result["first_admin_created"] is True
    assert result["login_required_and_validated"] is True
    assert result["shell_opened"] is True
    assert result["sales_opened"] is True
    assert result["fiscal_network_used"] is False
    assert not active_appdata.exists()
    assert (sandbox / "homologacao_primeiro_uso.json").is_file()
    assert not list(sandbox.rglob("*.pem"))
    assert not list(sandbox.rglob("*.pfx"))


def test_runner_nao_embute_caminho_da_maquina_de_desenvolvimento():
    source = RUNNER.read_text(encoding="utf-8").casefold()
    for forbidden in ("c:\\users\\famil", "desktop\\nabicode", "program files\\nabicode"):
        assert forbidden not in source
    assert "tempfile" in source
    assert '"teste"' in source


def test_runner_recusa_diretorio_com_dados_existentes(tmp_path):
    occupied = tmp_path / "ocupado"
    occupied.mkdir()
    (occupied / "dado.txt").write_text("preservar", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--root", str(occupied)],
        cwd=ROOT, capture_output=True, text=True, timeout=20, check=False,
    )
    assert completed.returncode != 0
    assert (occupied / "dado.txt").read_text(encoding="utf-8") == "preservar"
