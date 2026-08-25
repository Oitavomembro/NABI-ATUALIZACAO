from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from services.accountant_delivery_service import AccountantDeliveryService
from services.accountant_delivery_transport import (
    LocalFolderAccountantTransport,
    ReceiptQuery,
    TransportError,
    TransportReceipt,
    TransportUncertainError,
)
from services.accountant_monthly_package_service import AccountantMonthlyPackageService


def _package(
    path: Path,
    *,
    cnpj="12345678000195",
    competence="2026-08",
    profile="ESSENCIAL",
) -> Path:
    content = b"conteudo contabil de teste"
    manifest = {
        "layout": "nabicode.accountant-monthly-package.v1",
        "version": 1,
        "cnpj": cnpj,
        "competence": competence,
        "profile": profile,
        "status": "CONCILIADO",
        "files": [{
            "file": "LEIA-ME_CONTADOR.txt",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
        }],
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("LEIA-ME_CONTADOR.txt", content)
        archive.writestr("manifesto.json", json.dumps(manifest, sort_keys=True))
    return path


def _service(tmp_path: Path, transport=None) -> AccountantDeliveryService:
    transport = transport or LocalFolderAccountantTransport(tmp_path / "destino")
    return AccountantDeliveryService(
        outbox_path=tmp_path / "estado" / "outbox.sqlite3",
        spool_dir=tmp_path / "estado" / "spool",
        transport=transport,
    )


def _prepare(
    service: AccountantDeliveryService,
    package: Path,
    *,
    key="entrega-2026-08-0001",
    recipient="Contador Teste",
):
    return service.prepare(
        package_path=package,
        recipient=recipient,
        cnpj="12.345.678/0001-95",
        cnpj_confirmed=True,
        consent=True,
        competence="2026-08",
        profile="ESSENCIAL",
        idempotency_key=key,
    )


def test_fluxo_local_distingue_envio_de_recebimento_e_sobrevive_reinicio(tmp_path):
    destination = tmp_path / "destino"
    destination.mkdir()
    package = _package(tmp_path / "pacote.zip")
    service = _service(tmp_path)

    assert _prepare(service, package).status == "PREPARADO"
    assert service.enqueue("entrega-2026-08-0001").status == "ENFILEIRADO"
    sent = service.dispatch("entrega-2026-08-0001")
    assert sent.status == "ENVIADO_AO_TRANSPORTE"
    assert sent.receipt_sha256
    assert len(list(destination.glob("*.zip"))) == 1

    restarted = _service(tmp_path)
    assert restarted.dispatch("entrega-2026-08-0001").status == "ENVIADO_AO_TRANSPORTE"
    assert len(list(destination.glob("*.zip"))) == 1
    assert restarted.confirm_receipt("entrega-2026-08-0001").status == "RECEBIDO_CONFIRMADO"


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"recipient": ""}, "destinatário"),
        ({"cnpj_confirmed": False}, "Confirme"),
        ({"consent": False}, "consentimento"),
        ({"cnpj": "11111111000191"}, "divergem"),
        ({"competence": "2026-07"}, "divergem"),
        ({"profile": "COMPLETO"}, "divergem"),
    ],
)
def test_preparo_exige_contrato_confirmado(tmp_path, changes, message):
    (tmp_path / "destino").mkdir()
    service = _service(tmp_path)
    values = dict(
        package_path=_package(tmp_path / "pacote.zip"), recipient="Contador",
        cnpj="12345678000195", cnpj_confirmed=True, consent=True,
        competence="2026-08", profile="ESSENCIAL", idempotency_key="entrega-validacao-01",
    )
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        service.prepare(**values)


def test_idempotencia_preserva_snapshot_e_rejeita_payload_divergente(tmp_path):
    (tmp_path / "destino").mkdir()
    source = _package(tmp_path / "pacote.zip")
    service = _service(tmp_path)
    first = _prepare(service, source)
    assert _prepare(service, source) == first
    with pytest.raises(ValueError, match="outra entrega"):
        _prepare(service, source, recipient="Outro contador")

    source.write_bytes(b"origem alterada depois do preparo")
    assert service.dispatch("entrega-2026-08-0001").status == "PREPARADO"
    service.enqueue("entrega-2026-08-0001")
    assert service.dispatch("entrega-2026-08-0001").status == "ENVIADO_AO_TRANSPORTE"


class UncertainTransport:
    transport_id = "TEST_UNCERTAIN"
    binding_fingerprint = hashlib.sha256(b"test-uncertain-v1").hexdigest()

    def __init__(self):
        self.sends = 0
        self.query_status = "UNKNOWN"

    def send(self, **_kwargs):
        self.sends += 1
        raise TransportUncertainError("incerto")

    def query_receipt(self, *, reference, package_sha256):
        if self.query_status == "CONFIRMED":
            return ReceiptQuery("CONFIRMED", TransportReceipt(reference, package_sha256, "f" * 64))
        return ReceiptQuery(self.query_status)


def test_resultado_ambiguo_consulta_antes_de_repetir_e_mantem_chave(tmp_path):
    transport = UncertainTransport()
    service = _service(tmp_path, transport)
    _prepare(service, _package(tmp_path / "pacote.zip"))
    service.enqueue("entrega-2026-08-0001")
    assert service.dispatch("entrega-2026-08-0001").status == "DESCONHECIDO"
    assert service.dispatch("entrega-2026-08-0001").status == "DESCONHECIDO"
    assert transport.sends == 1
    with pytest.raises(RuntimeError, match="Consulte"):
        service.enqueue("entrega-2026-08-0001")
    assert service.reconcile_unknown("entrega-2026-08-0001").status == "DESCONHECIDO"
    transport.query_status = "NOT_FOUND"
    assert service.reconcile_unknown("entrega-2026-08-0001").status == "FALHA"
    assert service.enqueue("entrega-2026-08-0001").idempotency_key == "entrega-2026-08-0001"


def test_adulteracao_do_spool_falha_antes_do_transporte(tmp_path):
    destination = tmp_path / "destino"
    destination.mkdir()
    service = _service(tmp_path)
    record = _prepare(service, _package(tmp_path / "pacote.zip"))
    service.enqueue(record.idempotency_key)
    spool = next((tmp_path / "estado" / "spool").glob("*.zip"))
    spool.write_bytes(b"adulterado")
    failed = service.dispatch(record.idempotency_key)
    assert (failed.status, failed.last_error_code) == ("FALHA", "PACKAGE_TAMPERED")
    assert not list(destination.iterdir())


def test_recibo_adulterado_bloqueia_reenvio(tmp_path):
    destination = tmp_path / "destino"
    destination.mkdir()
    service = _service(tmp_path)
    record = _prepare(service, _package(tmp_path / "pacote.zip"))
    service.enqueue(record.idempotency_key)
    service.dispatch(record.idempotency_key)
    next(destination.glob("*.receipt.json")).write_text("{}", encoding="utf-8")
    failed = service.confirm_receipt(record.idempotency_key)
    assert (failed.status, failed.last_error_code) == ("FALHA", "RECEIPT_MISMATCH")
    with pytest.raises(RuntimeError, match="intervenção"):
        service.enqueue(record.idempotency_key)


def test_falha_entre_copia_e_recibo_fica_desconhecida_sem_duplicar(tmp_path, monkeypatch):
    destination = tmp_path / "destino"
    destination.mkdir()
    service = _service(tmp_path)
    record = _prepare(service, _package(tmp_path / "pacote.zip"))
    service.enqueue(record.idempotency_key)
    original_publish = LocalFolderAccountantTransport._publish_without_overwrite

    def fail_receipt(source, target):
        if str(target).endswith(".receipt.json"):
            raise OSError("falha simulada")
        return original_publish(source, target)

    monkeypatch.setattr(
        LocalFolderAccountantTransport,
        "_publish_without_overwrite",
        staticmethod(fail_receipt),
    )
    unknown = service.dispatch(record.idempotency_key)
    assert unknown.status == "DESCONHECIDO"
    assert len(list(destination.glob("*.zip"))) == 1
    assert not list(destination.glob("*.tmp"))
    assert service.dispatch(record.idempotency_key).attempts == 1
    monkeypatch.setattr(
        LocalFolderAccountantTransport,
        "_publish_without_overwrite",
        staticmethod(original_publish),
    )
    reconciled = service.reconcile_unknown(record.idempotency_key)
    assert reconciled.status == "RECEBIDO_CONFIRMADO"
    assert len(list(destination.glob("*.zip"))) == 1
    assert len(list(destination.glob("*.receipt.json"))) == 1


def test_destino_invalido_falha_sem_vazar_destinatario_no_banco(tmp_path):
    destination = tmp_path / "destino"
    destination.write_text("não é pasta", encoding="utf-8")
    service = _service(tmp_path)
    record = _prepare(service, _package(tmp_path / "pacote.zip"), recipient="Pessoa Muito Secreta")
    service.enqueue(record.idempotency_key)
    failed = service.dispatch(record.idempotency_key)
    assert (failed.status, failed.last_error_code) == ("FALHA", "TRANSPORT_FAILED")
    assert b"Pessoa Muito Secreta" not in (tmp_path / "estado" / "outbox.sqlite3").read_bytes()
    with sqlite3.connect(tmp_path / "estado" / "outbox.sqlite3") as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(accountant_delivery_outbox)"
            )
        }
    assert "recipient" not in columns


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("cnpj_confirmed", 1, "Confirme explicitamente"),
        ("cnpj_confirmed", "sim", "Confirme explicitamente"),
        ("consent", 1, "consentimento explícito"),
        ("consent", "sim", "consentimento explícito"),
        ("recipient", "Contador\nforjado", "destinatário/contador válido"),
        ("recipient", "X" * 201, "destinatário/contador válido"),
    ],
)
def test_confirmacoes_e_destinatario_exigem_valores_explicitos(
    tmp_path, field, value, message
):
    (tmp_path / "destino").mkdir()
    service = _service(tmp_path)
    values = dict(
        package_path=_package(tmp_path / "pacote.zip"),
        recipient="Contador",
        cnpj="12345678000195",
        cnpj_confirmed=True,
        consent=True,
        competence="2026-08",
        profile="ESSENCIAL",
        idempotency_key="entrega-validacao-02",
    )
    values[field] = value
    with pytest.raises(ValueError, match=message):
        service.prepare(**values)


def test_outbox_vincula_a_pasta_preparada_e_recusa_troca_silenciosa(tmp_path):
    first_destination = tmp_path / "destino-a"
    second_destination = tmp_path / "destino-b"
    first_destination.mkdir()
    second_destination.mkdir()
    package = _package(tmp_path / "pacote.zip")
    service = _service(tmp_path, LocalFolderAccountantTransport(first_destination))
    record = _prepare(service, package)
    service.enqueue(record.idempotency_key)

    changed = _service(tmp_path, LocalFolderAccountantTransport(second_destination))
    failed = changed.dispatch(record.idempotency_key)
    assert (failed.status, failed.last_error_code) == (
        "FALHA",
        "TRANSPORT_CONFIGURATION_CHANGED",
    )
    assert not list(first_destination.iterdir())
    assert not list(second_destination.iterdir())

    restored = _service(tmp_path, LocalFolderAccountantTransport(first_destination))
    restored.enqueue(record.idempotency_key)
    assert restored.dispatch(record.idempotency_key).status == "ENVIADO_AO_TRANSPORTE"


class InvalidReceiptTransport:
    transport_id = "TEST_INVALID_RECEIPT"
    binding_fingerprint = hashlib.sha256(b"test-invalid-receipt-v1").hexdigest()

    def send(self, *, idempotency_key, package_path, package_sha256):
        return TransportReceipt(idempotency_key, "0" * 64, "f" * 64)

    def query_receipt(self, *, reference, package_sha256):
        return ReceiptQuery(
            "CONFIRMED",
            TransportReceipt(reference + "-wrong", package_sha256, "f" * 64),
        )


def test_recibo_inconsistente_nunca_promove_envio_ou_recebimento(tmp_path):
    service = _service(tmp_path, InvalidReceiptTransport())
    record = _prepare(service, _package(tmp_path / "pacote.zip"))
    service.enqueue(record.idempotency_key)
    unknown = service.dispatch(record.idempotency_key)
    assert (unknown.status, unknown.last_error_code) == (
        "DESCONHECIDO",
        "TRANSPORT_PROTOCOL_ERROR",
    )
    with pytest.raises(RuntimeError, match="Consulte"):
        service.enqueue(record.idempotency_key)
    mismatch = service.reconcile_unknown(record.idempotency_key)
    assert (mismatch.status, mismatch.last_error_code) == (
        "FALHA",
        "RECEIPT_MISMATCH",
    )


def test_destino_preexistente_incompativel_nao_e_sobrescrito(tmp_path):
    destination = tmp_path / "destino"
    destination.mkdir()
    collision = destination / "entrega-2026-08-0001.zip"
    collision.write_bytes(b"conteudo de terceiro")
    service = _service(tmp_path)
    record = _prepare(service, _package(tmp_path / "pacote.zip"))
    service.enqueue(record.idempotency_key)
    failed = service.dispatch(record.idempotency_key)
    assert (failed.status, failed.last_error_code) == (
        "FALHA",
        "DESTINATION_COLLISION",
    )
    assert collision.read_bytes() == b"conteudo de terceiro"
    with pytest.raises(RuntimeError, match="intervenção"):
        service.enqueue(record.idempotency_key)


class FlakyTransport:
    transport_id = "TEST_FLAKY"
    binding_fingerprint = hashlib.sha256(b"test-flaky-v1").hexdigest()

    def __init__(self):
        self.sends = 0

    def send(self, *, idempotency_key, package_path, package_sha256):
        self.sends += 1
        if self.sends == 1:
            raise TransportError("falha definida")
        return TransportReceipt(idempotency_key, package_sha256, "e" * 64)

    def query_receipt(self, *, reference, package_sha256):
        return ReceiptQuery(
            "CONFIRMED",
            TransportReceipt(reference, package_sha256, "e" * 64),
        )


def test_retry_de_falha_definida_reutiliza_a_mesma_chave(tmp_path):
    transport = FlakyTransport()
    service = _service(tmp_path, transport)
    record = _prepare(service, _package(tmp_path / "pacote.zip"))
    service.enqueue(record.idempotency_key)
    first = service.dispatch(record.idempotency_key)
    assert (first.status, first.attempts) == ("FALHA", 1)
    enqueued = service.enqueue(record.idempotency_key)
    assert enqueued.idempotency_key == record.idempotency_key
    second = service.dispatch(record.idempotency_key)
    assert (second.status, second.attempts) == ("ENVIADO_AO_TRANSPORTE", 2)
    assert service.confirm_receipt(record.idempotency_key).status == "RECEBIDO_CONFIRMADO"
    assert transport.sends == 2


def test_validacao_e_hash_ocorrem_sobre_snapshot_imutavel(tmp_path, monkeypatch):
    destination = tmp_path / "destino"
    destination.mkdir()
    source = _package(tmp_path / "pacote.zip")
    original_validate = AccountantMonthlyPackageService.validate
    observed_paths = []

    def validate_snapshot(cls, path):
        observed_paths.append(Path(path))
        source.write_bytes(b"origem alterada durante o preparo")
        return original_validate(path)

    monkeypatch.setattr(
        AccountantMonthlyPackageService,
        "validate",
        classmethod(validate_snapshot),
    )
    service = _service(tmp_path)
    record = _prepare(service, source)
    assert observed_paths and observed_paths[0] != source
    spool = next((tmp_path / "estado" / "spool").glob("*.zip"))
    assert hashlib.sha256(spool.read_bytes()).hexdigest() == record.package_sha256
    service.enqueue(record.idempotency_key)
    assert service.dispatch(record.idempotency_key).status == "ENVIADO_AO_TRANSPORTE"


def test_recibo_local_minimiza_dados_e_vincula_hash_e_transporte(tmp_path):
    destination = tmp_path / "destino"
    destination.mkdir()
    service = _service(tmp_path)
    record = _prepare(
        service,
        _package(tmp_path / "pacote.zip"),
        recipient="Pessoa Muito Secreta",
    )
    service.enqueue(record.idempotency_key)
    sent = service.dispatch(record.idempotency_key)
    receipt_path = next(destination.glob("*.receipt.json"))
    raw = receipt_path.read_bytes()
    payload = json.loads(raw)
    assert payload["package_sha256"] == record.package_sha256
    assert payload["transport_binding"] == record.transport_binding
    assert hashlib.sha256(raw).hexdigest() == sent.receipt_sha256
    assert b"Pessoa Muito Secreta" not in raw
    assert b"12345678000195" not in raw
