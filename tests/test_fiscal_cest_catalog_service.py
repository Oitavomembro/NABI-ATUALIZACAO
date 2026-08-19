from pathlib import Path

import pytest

from services.fiscal_cest_catalog_service import FiscalCESTCatalogService


def payload(*, last_description="Moveis de madeira vigentes") -> bytes:
    rows = []
    for index in range(1, 1002):
        code = f"{index % 100:02d}.{index % 1000:03d}.{index % 100:02d}"
        rows.append(
            f"<tr><td>{index}.0</td><td>{code}</td><td>0101</td>"
            f"<td>Descrição fiscal {index}</td></tr>"
        )
    rows.extend([
        "<tr><td>1</td><td>28.001.00</td><td>9403.60.00</td><td>Redação antiga</td></tr>",
        f"<tr><td>1</td><td>28.001.00</td><td>9403.60.00</td><td>{last_description}</td></tr>",
    ])
    return ("<html><body><table>" + "".join(rows) + "</table></body></html>").encode()


def service(tmp_path: Path, source: bytes) -> FiscalCESTCatalogService:
    bundled = tmp_path / "cest.html"
    bundled.write_bytes(source)
    return FiscalCESTCatalogService(
        bundled_path=bundled, cache_path=tmp_path / "cache" / "cest.html",
    )


def test_consolida_ultima_redacao_e_pesquisa_por_ncm(tmp_path):
    catalog = service(tmp_path, payload())
    metadata = catalog.load()
    assert int(metadata["entries"]) >= 1000
    assert catalog.get("28.001.00").description == "Moveis de madeira vigentes"
    result = catalog.search("", ncm="94036000")
    assert any(item.code == "2800100" for item in result)


def test_pesquisa_por_cest_e_descricao_sem_acento(tmp_path):
    catalog = service(tmp_path, payload())
    assert catalog.search("28.001")[0].code == "2800100"
    assert catalog.search("moveis madeira")[0].code == "2800100"


def test_atualiza_atomicamente_e_preserva_cache_quando_fonte_incompleta(tmp_path):
    old = payload(last_description="Versao preservada")
    catalog = service(tmp_path, old)
    catalog.downloader = lambda url: payload(last_description="Versao atualizada")
    assert int(catalog.update()["entries"]) >= 1000
    assert catalog.get("2800100").description == "Versao atualizada"
    saved = catalog.cache_path.read_bytes()
    catalog.downloader = lambda url: b"<html><table></table></html>"
    with pytest.raises(ValueError, match="incompleta"):
        catalog.update()
    assert catalog.cache_path.read_bytes() == saved


def test_cache_corrompido_recua_para_snapshot_oficial(tmp_path):
    catalog = service(tmp_path, payload(last_description="Snapshot"))
    catalog.cache_path.parent.mkdir(parents=True)
    catalog.cache_path.write_text("inválido", encoding="utf-8")
    catalog.load()
    assert catalog.get("2800100").description == "Snapshot"
