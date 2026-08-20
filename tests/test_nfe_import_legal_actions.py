from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "nabicode_legacy.py").read_text(encoding="utf-8")


def test_historico_de_entrada_oferece_estorno_sem_exclusao_fiscal():
    block = SOURCE.split("def abrir_historico_nfe_importadas", 1)[1].split("def abrir_importacao_xml", 1)[0]
    assert "Estornar lançamento" in block
    assert "XML e o histórico serão preservados" in block
    assert "NFE_IMPORT_SERVICE.estornar_importacao" in block
    assert "Excluir selecionadas" not in block
    assert "NFE_IMPORT_SERVICE.excluir_importacao" not in block
