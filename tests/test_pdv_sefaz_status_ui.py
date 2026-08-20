from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")


def test_pdv_exibe_status_sefaz_sem_consulta_automatica_na_abertura():
    opening = SOURCE.split("def abrir_pdv_independente", 1)[1].split("def _consultar_status_sefaz_pdv", 1)[0]
    assert "SEFAZ: consultar" in opening
    assert "SEFAZ: configuração pendente" in opening
    assert "check_service_status" not in opening


def test_consulta_sefaz_do_pdv_roda_em_segundo_plano_e_reabilita_botao():
    block = SOURCE.split("def _consultar_status_sefaz_pdv", 1)[1].split("def _enter_contexto_pdv", 1)[0]
    assert "TASK_MANAGER.submit" in block
    assert "check_service_status" in block
    assert "SEFAZ: disponível" in block
    assert "SEFAZ: indisponível" in block
