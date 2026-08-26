from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from services.fiscal_service import FiscalResponse, FiscalService


@pytest.fixture
def package_v2():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        database = root / "fiscal.db"
        connection = sqlite3.connect(database)
        connection.execute("CREATE TABLE configuracoes (chave TEXT PRIMARY KEY, valor TEXT)")
        connection.commit()
        connection.close()
        service = FiscalService(
            lambda: sqlite3.connect(database),
            storage_dir=root / "fiscal",
            actor_provider=lambda: "auditor",
            authorization_provider=lambda action: action in {"configure", "transmit"},
        )
        service.save_config({
            "cnpj": "12345678000195", "state": "BA", "environment": "PRODUCAO",
            "issuer": {"name": "EMPRESA TESTE"},
        })
        issued = datetime(2026, 8, 12, 10, 30).astimezone()
        key = service.build_access_key(
            state_code="29", issued_at=issued, cnpj="12345678000195", model="55",
            series=1, number=77, emission_type=1, numeric_code="76543210",
        )
        request = (
            '<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe '
            f'Id="NFe{key}" versao="4.00"><ide><mod>55</mod><dhEmi>{issued.isoformat()}</dhEmi>'
            '</ide><emit><CNPJ>12345678000195</CNPJ></emit></infNFe></NFe>'
        )
        response_xml = (
            f'<ret><protNFe><infProt><cStat>100</cStat><chNFe>{key}</chNFe>'
            '<nProt>12345</nProt></infProt></protNFe></ret>'
        )
        service.store_document(
            access_key=key, model="55", environment="PRODUCAO", request_xml=request,
            response=FiscalResponse(True, "100", "Autorizado", "12345", access_key=key,
                                    raw_xml=response_xml), actor="auditor",
        )
        event_xml, _ = service.build_event_xml(
            event_type="CCE", access_key=key, sequence=1,
            actor_document="12345678000195",
            correction="Corrigir informação complementar para teste.", environment="PRODUCAO",
        )
        service.register_event(
            access_key=key, event_type="CCE", request_xml=event_xml, actor="auditor",
            response=FiscalResponse(
                True, "135", "Evento registrado", "EV123",
                raw_xml="<ret><cStat>135</cStat><nProt>EV123</nProt></ret>",
            ),
        )
        package = root / "contabilidade.zip"
        service.export_accounting_package(
            start_date="2026-08-01", end_date="2026-08-31", output_path=package,
        )
        yield service, package


def _rewrite(source: Path, mutate, *, duplicate: tuple[str, bytes] | None = None) -> Path:
    target = source.with_name(f"mutated_{id(mutate)}.zip")
    with zipfile.ZipFile(source) as archive:
        entries = [(info.filename, archive.read(info.filename)) for info in archive.infolist()]
    entries = mutate(entries)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
        if duplicate:
            archive.writestr(*duplicate)
    return target


def _mutate_manifest(entries, change):
    result = []
    for name, data in entries:
        if name == "manifesto.json":
            manifest = json.loads(data)
            change(manifest)
            data = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode()
        result.append((name, data))
    return result


def test_v2_rejeita_bytes_alterados_em_cada_arquivo_de_evento(package_v2):
    service, package = package_v2
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifesto.json"))
    for event_file in manifest["events"][0]["files"]:
        name = event_file["file"]
        altered = _rewrite(package, lambda rows, target=name: [
            (item_name, data + b"ALTERADO" if item_name == target else data)
            for item_name, data in rows
        ])
        with pytest.raises(ValueError, match="alterado ou corrompido"):
            service.validate_accounting_package(altered)


def test_v2_rejeita_arquivo_ausente_e_extra(package_v2):
    service, package = package_v2
    missing = _rewrite(package, lambda rows: [
        row for index, row in enumerate(rows) if index != 0
    ])
    with pytest.raises(ValueError, match="diverge do manifesto"):
        service.validate_accounting_package(missing)
    extra = _rewrite(package, lambda rows: rows + [("extra.txt", b"fora")])
    with pytest.raises(ValueError, match="diverge do manifesto"):
        service.validate_accounting_package(extra)


def test_v2_rejeita_nome_duplicado_e_ambiguo(package_v2):
    service, package = package_v2
    with zipfile.ZipFile(package) as archive:
        name = next(item for item in archive.namelist() if item.endswith(".xml"))
        data = archive.read(name)
    with pytest.warns(UserWarning, match="Duplicate name"):
        duplicated = _rewrite(package, lambda rows: rows, duplicate=(name, data))
    with pytest.raises(ValueError, match="duplicado"):
        service.validate_accounting_package(duplicated)
    ambiguous = _rewrite(package, lambda rows: rows + [("leia-me.TXT", b"duplicado")])
    with pytest.raises(ValueError, match="repetido ou ambíguo"):
        service.validate_accounting_package(ambiguous)


def test_v2_rejeita_path_traversal(package_v2):
    service, package = package_v2
    unsafe = _rewrite(package, lambda rows: rows + [("../fora.xml", b"<xml/>")])
    with pytest.raises(ValueError, match="caminho interno inseguro"):
        service.validate_accounting_package(unsafe)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda manifest: manifest.update(layout="inventado"), "incompatível ou inconsistente"),
        (lambda manifest: manifest["documents"][0].update(access_key="9" * 44), "Chave do XML diverge"),
        (lambda manifest: manifest["documents"][0].update(protocol="OUTRO"), "Protocolo fiscal diverge"),
        (lambda manifest: manifest["issuer"].update(cnpj="99999999000199"), "CNPJ emitente diverge"),
        (lambda manifest: manifest.update(period={"start": "2026-09-01", "end": "2026-09-30"}), "fora do período"),
        (lambda manifest: manifest["documents"][0].update(status="PENDENTE"), "Status de documento"),
    ],
)
def test_v2_rejeita_divergencia_semantica_do_manifesto(package_v2, change, message):
    service, package = package_v2
    altered = _rewrite(package, lambda rows: _mutate_manifest(rows, change))
    with pytest.raises(ValueError, match=message):
        service.validate_accounting_package(altered)


def test_v2_rejeita_hash_duplicado_ou_referencia_sem_catalogo(package_v2):
    service, package = package_v2
    duplicate = _rewrite(package, lambda rows: _mutate_manifest(
        rows, lambda manifest: manifest["files"].append(dict(manifest["files"][0]))
    ))
    with pytest.raises(ValueError, match="caminho duplicado"):
        service.validate_accounting_package(duplicate)
    missing_catalog = _rewrite(package, lambda rows: _mutate_manifest(
        rows, lambda manifest: manifest["files"].pop(0)
    ))
    with pytest.raises(ValueError, match="diverge do manifesto|fora do catálogo"):
        service.validate_accounting_package(missing_catalog)


def test_v1_e_reconhecido_como_legado_sem_integridade_v2(package_v2):
    service, package = package_v2
    legacy = _rewrite(package, lambda rows: _mutate_manifest(
        rows, lambda manifest: manifest.update(version=1)
    ))
    with pytest.raises(ValueError, match="LEGADO.*insuficiente|LEGADO.*não prova"):
        service.validate_accounting_package(legacy)


def test_v2_declara_limite_de_nao_repodio(package_v2):
    service, package = package_v2
    result = service.validate_accounting_package(package)
    assert result["valid"] is True
    assert result["integrity"] == "SHA256_COMPLETA_SEM_ASSINATURA"
    assert result["non_repudiation"] is False
