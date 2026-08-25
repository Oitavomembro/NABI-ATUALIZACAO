import ast
import hashlib
import json
import os
import re
import socket
import sqlite3
import sys
import _socket
import _sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SERVICES_DIR = str(ROOT / "services")
sys.path.insert(0, SERVICES_DIR)
from fiscal_offline_dossier import (  # noqa: E402
    FakeFiscalStore,
    FakeFiscalTransport,
    FakeReadinessAdapter,
    OfflineBoundaryViolation,
    OfflineFiscalDossierService,
    offline_boundary_guards,
    run_offline_dossier,
    write_dossier,
)
sys.path.remove(SERVICES_DIR)


def test_dossie_executa_matriz_completa_sem_alegar_homologacao():
    report = run_offline_dossier()

    assert report["perfil"] == "TESTE"
    assert report["ambiente"] == "SIMULADO_OFFLINE"
    assert report["nao_e_homologacao_fisica"] is True
    assert report["nao_houve_sucesso_sefaz"] is True
    assert report["resumo"]["reprovados"] == 0
    assert report["resumo"]["homologacao_fiscal_real"] == "NAO_EXECUTADA"
    assert report["resumo"]["producao_fiscal"] == "BLOQUEADA"

    categories = {scenario["categoria"] for scenario in report["cenarios"]}
    assert categories == {
        "prontidao",
        "autorizacao",
        "rejeicao",
        "timeout",
        "resposta_desconhecida",
        "consulta_reconciliacao",
        "cancelamento",
        "inutilizacao",
        "contingencia",
        "bloqueio",
    }


def test_perfil_diferente_de_teste_falha_antes_de_tocar_adapters():
    readiness = FakeReadinessAdapter(profile="PRODUCAO")
    store = FakeFiscalStore()
    transport = FakeFiscalTransport()
    service = OfflineFiscalDossierService(
        profile="PRODUCAO", readiness=readiness, store=store, transport=transport
    )

    with pytest.raises(PermissionError, match="exclusivo do perfil TESTE"):
        run_offline_dossier(service=service)

    assert readiness.checks == 0
    assert store.writes == 0
    assert transport.calls == []


def test_adapters_nao_identificados_como_fake_sao_recusados():
    class RealLookingTransport:
        pass

    with pytest.raises(TypeError, match="somente adapters fake"):
        OfflineFiscalDossierService(transport=RealLookingTransport())


def test_prova_de_isolamento_registra_zero_rede_banco_e_certificado():
    report = run_offline_dossier()
    proof = report["prova_de_isolamento"]

    assert proof["real_network_attempts"] == 0
    assert proof["real_database_attempts"] == 0
    assert proof["real_certificate_attempts"] == 0
    assert proof["real_network_calls_by_adapter"] == 0
    assert proof["real_database_connections_by_adapter"] == 0
    assert proof["real_certificate_reads_by_adapters"] == 0
    assert proof["fake_transport_calls"] > 0
    assert proof["in_memory_writes"] > 0


def test_guard_adversarial_bloqueia_socket_se_fake_tentar_escapar():
    class HostileFakeTransport(FakeFiscalTransport):
        def authorize(self, outcome):
            socket.create_connection(("127.0.0.1", 9))

    service = OfflineFiscalDossierService(transport=HostileFakeTransport())
    with pytest.raises(OfflineBoundaryViolation, match="socket/rede"):
        run_offline_dossier(service=service)


def test_guards_adversariais_cobrem_aliases_de_rede_sqlite_e_arquivos_sensiveis():
    with offline_boundary_guards() as audit:
        with pytest.raises(OfflineBoundaryViolation, match="socket/rede"):
            socket.getaddrinfo("sefaz.invalid", 443)
        with pytest.raises(OfflineBoundaryViolation, match="socket/rede"):
            socket.SocketType()
        with pytest.raises(OfflineBoundaryViolation, match="socket/rede"):
            _socket.getaddrinfo("sefaz.invalid", 443)

        with pytest.raises(OfflineBoundaryViolation, match="SQLite"):
            sqlite3.dbapi2.connect(":memory:")
        with pytest.raises(OfflineBoundaryViolation, match="SQLite"):
            sqlite3.Connection(":memory:")
        with pytest.raises(OfflineBoundaryViolation, match="SQLite"):
            _sqlite3.connect(":memory:")

        with pytest.raises(OfflineBoundaryViolation, match="certificado/chave"):
            Path("segredo-teste.pfx").read_bytes()
        with pytest.raises(OfflineBoundaryViolation, match="certificado/chave"):
            os.open("segredo-teste.pem", os.O_RDONLY)
        with pytest.raises(OfflineBoundaryViolation, match="certificado/chave"):
            open(b"segredo-teste.p12", "rb")

    assert audit.real_network_attempts == 3
    assert audit.real_database_attempts == 3
    assert audit.real_certificate_attempts == 3


def test_reconciliacao_nao_reenvia_autorizacao_e_cancelamento_incerto_e_bloqueado():
    report = run_offline_dossier()
    scenarios = {scenario["id"]: scenario for scenario in report["cenarios"]}

    reconciliation = scenarios["CONSULTA-RECONCILIACAO"]
    assert reconciliation["evidencia"]["authorization_calls_added"] == 0
    assert reconciliation["evidencia"]["query_calls"] == 1

    blocked = scenarios["CANCELAMENTO-BLOQUEADO-INCERTO"]
    assert blocked["resultado_fiscal_simulado"] == "BLOQUEADO"
    assert blocked["evidencia"]["event_calls_added"] == 0


def test_contingencia_fica_pendente_e_modelo_55_e_bloqueado():
    report = run_offline_dossier()
    scenarios = {scenario["id"]: scenario for scenario in report["cenarios"]}

    contingency = scenarios["CONTINGENCIA-OFFLINE-65"]
    assert contingency["evidencia"]["fake_transport_calls_added"] == 0
    assert contingency["evidencia"]["authorization_claimed"] is False
    assert contingency["evidencia"]["legal_deadline_validated"] is False
    assert "PENDENTE" in contingency["resultado_fiscal_simulado"]
    assert scenarios["BLOQUEIO-CONTINGENCIA-55"]["resultado_fiscal_simulado"] == "BLOQUEADO"


def test_evidencias_e_payload_possuem_hashes_sha256_validos():
    report = run_offline_dossier()
    sha256 = re.compile(r"^[0-9a-f]{64}$")

    assert report["schema_version"] == "1.0"
    assert report["versao_harness"] == "1.0.0"
    assert report["versao_aplicacao"] == "2.5.1"
    assert report["revisao_aplicacao"] == "21"
    assert report["limitacoes"]
    assert sha256.fullmatch(report["payload_sha256"])
    assert sha256.fullmatch(report["harness_source_sha256"])
    unhashed_report = dict(report)
    payload_hash = unhashed_report.pop("payload_sha256")
    canonical_report = json.dumps(
        unhashed_report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert hashlib.sha256(canonical_report).hexdigest() == payload_hash
    source = ROOT / "services" / "fiscal_offline_dossier.py"
    canonical_source = source.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    assert (
        hashlib.sha256(canonical_source).hexdigest()
        == report["harness_source_sha256"]
    )
    for item in report["cenarios"]:
        assert item["id"]
        assert item["resultado_teste"] in {"APROVADO", "REPROVADO"}
        assert item["resultado_fiscal_simulado"]
        assert item["comportamento_esperado"]
        assert sha256.fullmatch(item["evidencia_sha256"])
        canonical_evidence = json.dumps(
            item["evidencia"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        assert (
            hashlib.sha256(canonical_evidence).hexdigest()
            == item["evidencia_sha256"]
        )


def test_hash_do_harness_independe_de_lf_ou_crlf(tmp_path):
    source = (ROOT / "services" / "fiscal_offline_dossier.py").read_text(
        encoding="utf-8"
    )
    lf_path = tmp_path / "harness-lf.py"
    crlf_path = tmp_path / "harness-crlf.py"
    lf_path.write_bytes(source.replace("\r\n", "\n").encode("utf-8"))
    crlf_path.write_bytes(
        source.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    )

    lf_hash = hashlib.sha256(lf_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    crlf_hash = hashlib.sha256(
        crlf_path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    assert lf_hash == crlf_hash == run_offline_dossier()["harness_source_sha256"]


def test_artefatos_sao_deterministicos_sanitizados_e_distinguem_prova_fisica(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    json_a, summary_a, json_hash_a, summary_hash_a = write_dossier(first)
    json_b, summary_b, json_hash_b, summary_hash_b = write_dossier(second)

    assert json_a.read_bytes() == json_b.read_bytes()
    assert summary_a.read_bytes() == summary_b.read_bytes()
    assert json_hash_a == json_hash_b
    assert summary_hash_a == summary_hash_b

    content = json_a.read_text(encoding="utf-8") + summary_a.read_text(encoding="utf-8")
    assert "NÃO É HOMOLOGAÇÃO FÍSICA" in content
    assert "NÃO HOUVE" in content
    assert "sucesso SEFAZ" in content or "SUCESSO SEFAZ" in content
    assert not re.search(r"(?<!\d)\d{44}(?!\d)", content)
    assert not re.search(r"(?<!\d)\d{14}(?!\d)", content)
    assert ".pfx" not in content.lower()
    assert "PRIVATE KEY" not in content
    assert "C:\\Users\\" not in content
    assert "/Users/" not in content
    artifact = json.loads(json_a.read_text(encoding="utf-8"))
    assert artifact["resumo"]["producao_fiscal"] == "BLOQUEADA"


def test_harness_nao_importa_servico_fiscal_banco_repositorio_ou_ui():
    source_path = Path(__file__).parents[1] / "services" / "fiscal_offline_dossier.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")

    assert not any(name == "services" or name.startswith("services.") for name in imports)
    assert not any(name.startswith("repositories") for name in imports)
    assert not any(name.startswith("database") for name in imports)
    assert not any(name.startswith("ui") for name in imports)
    assert not imports.intersection({"cryptography", "ssl", "subprocess", "requests", "httpx"})
