import json
from pathlib import Path

import pytest

from services.fiscal_ncm_catalog_service import FiscalNCMCatalogService


def payload(*, updated="Vigente em 18/08/2026", description="Móveis de madeira") -> bytes:
    rows = [
        {
            "Codigo": f"{index:08d}", "Descricao": description if index == 94036000 else f"Produto {index}",
            "Data_Inicio": "01/01/2026", "Data_Fim": "31/12/9999",
        }
        for index in range(1, 5001)
    ]
    rows.append({
        "Codigo": "9403.60.00", "Descricao": description,
        "Data_Inicio": "01/01/2026", "Data_Fim": "31/12/9999",
    })
    return json.dumps({
        "Data_Ultima_Atualizacao_NCM": updated,
        "Ato": "Resolução Gecex de teste", "Nomenclaturas": rows,
    }, ensure_ascii=False).encode()


def service(tmp_path: Path, source: bytes) -> FiscalNCMCatalogService:
    bundled = tmp_path / "bundled.json"
    bundled.write_bytes(source)
    return FiscalNCMCatalogService(
        bundled_path=bundled, cache_path=tmp_path / "cache" / "ncm.json",
    )


def test_carrega_snapshot_e_pesquisa_codigo_ou_descricao_sem_acento(tmp_path):
    catalog = service(tmp_path, payload(description="Móveis de madeira"))
    metadata = catalog.load()
    assert int(metadata["entries"]) >= 5001
    assert catalog.search("94036000")[0].code == "94036000"
    assert catalog.search("moveis madeira")[0].description == "Móveis de madeira"
    assert catalog.validate_code("9403.60.00").code == "94036000"


def test_atualizacao_oficial_valida_e_substitui_cache_atomicamente(tmp_path):
    old = payload(updated="Antiga")
    new = payload(updated="Nova")
    catalog = service(tmp_path, old)
    catalog.downloader = lambda url: new
    metadata = catalog.update()
    assert metadata["updated"] == "Nova"
    assert catalog.cache_path.read_bytes() == new
    assert not list(catalog.cache_path.parent.glob("*.tmp"))


def test_fonte_incompleta_e_rejeitada_sem_destruir_cache_valido(tmp_path):
    old = payload(updated="Preservada")
    catalog = service(tmp_path, old)
    catalog.cache_path.parent.mkdir(parents=True)
    catalog.cache_path.write_bytes(old)
    catalog.downloader = lambda url: json.dumps({"Nomenclaturas": []}).encode()
    with pytest.raises(ValueError, match="incompleta"):
        catalog.update()
    assert catalog.cache_path.read_bytes() == old


def test_cache_corrompido_recua_para_snapshot_embutido(tmp_path):
    catalog = service(tmp_path, payload(updated="Embutida"))
    catalog.cache_path.parent.mkdir(parents=True)
    catalog.cache_path.write_text("corrompido", encoding="utf-8")
    assert catalog.load()["updated"] == "Embutida"
