from __future__ import annotations

import sqlite3
import socket
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from administration.product_ncm_correction_service import (
    ProductNcmCorrectionManagementService,
)
from assistant_nabi.confirmations import DraftConfirmationService
from assistant_nabi.bootstrap import create_draft_assistant
from assistant_nabi.contracts import AssistantActor, CapabilityLevel
from assistant_nabi.safe_error_gateway import NabiCodeSafeErrorRecoveryGateway
from assistant_nabi.safe_error_recovery import SafeErrorRecoveryDraftService
from services.assisted_product_ncm_service import AssistedProductNcmCorrectionService


class ProductPort:
    def __init__(self, ncm=""):
        self.product = {
            "id": 7, "codigo": "P-7", "nome": "MESA", "ncm": ncm,
            "tipo_produto": "MERCADORIA",
        }

    def get_product(self, product_id):
        return dict(self.product) if int(product_id) == 7 else None


class FiscalPort:
    def __init__(self, record):
        self.record = dict(record)
        self.calls = []
        self.actor = "maria"

    def list_transmission_queue(self):
        return [dict(self.record)]

    def require_authenticated_actor(self, action, *, operation):
        self.calls.append(("authenticate", action, operation))
        return self.actor

    def reconcile_unknown(self, queue_id):
        self.calls.append(("reconcile", queue_id))
        if self.record["status"] != "RESPOSTA_DESCONHECIDA":
            raise ValueError("Somente estado desconhecido pode reconciliar.")
        self.record.update(status="PENDENTE", operation="consulta")
        return dict(self.record)

    def force_receipt_check(self, queue_id):
        self.calls.append(("receipt", queue_id))
        self.record["status"] = "PENDENTE"
        return dict(self.record)

    def retry_transmission(self, queue_id):
        self.calls.append(("blind-retry", queue_id))
        raise AssertionError("A Nabi jamais deve chamar reenvio cego.")


class ProductCorrectionPort:
    def __init__(self):
        self.calls = []

    def correct_ncm(self, draft, **kwargs):
        self.calls.append((draft, kwargs))
        return {
            "product_id": draft.product_id, "current_ncm": draft.proposed_ncm,
            "commercial_data_preserved": True,
            "fiscal_authorization_claimed": False,
        }


def actor(username="maria", session_id="sessao-1"):
    return AssistantActor(username, "GERENTE", session_id)


def confirmed(draft, *, current_actor=None):
    current_actor = current_actor or actor()
    broker = DraftConfirmationService()
    challenge = broker.issue(draft, actor=current_actor)
    assert challenge.required_capability is CapabilityLevel.REINFORCED_CONFIRMATION
    return broker.confirm(token=challenge.token, draft=draft, actor=current_actor)


def test_diagnostico_ncm_nao_sugere_classificacao_e_rascunho_exige_fonte_humana():
    products = ProductPort("")
    service = SafeErrorRecoveryDraftService(products, FiscalPort({"id": "q"}))

    diagnosis = service.diagnose_product_ncm(product_id=7)
    assert diagnosis.diagnostic_code == "NCM_AUSENTE"
    assert diagnosis.suggested_ncm is None
    assert diagnosis.mutation_performed is False
    assert products.product["ncm"] == ""

    for proposed, source, reference in (
        ("", "CONTADOR", "CRC 1"),
        ("00000000", "CONTADOR", "CRC 1"),
        ("1234567X", "CONTADOR", "CRC 1"),
        ("94036000", "MODELO_IA", "resposta do modelo"),
        ("94036000", "CONTADOR", ""),
    ):
        with pytest.raises(ValueError):
            service.prepare_ncm_correction(
                product_id=7, proposed_ncm=proposed,
                evidence_source=source, evidence_reference=reference,
            )

    draft = service.prepare_ncm_correction(
        product_id=7, proposed_ncm="94036000",
        evidence_source="CONTADOR", evidence_reference="Parecer CRC 123",
    )
    assert draft.proposed_ncm == "94036000"
    assert draft.expected_current_ncm == ""
    assert products.product["ncm"] == ""


def test_correcao_ncm_so_executa_depois_de_confirmacao_reforcada_e_uso_unico():
    products = ProductPort("")
    fiscal = FiscalPort({"id": "q", "status": "PENDENTE"})
    service = SafeErrorRecoveryDraftService(products, fiscal)
    draft = service.prepare_ncm_correction(
        product_id=7, proposed_ncm="94036000",
        evidence_source="TABELA_OFICIAL", evidence_reference="Tabela NCM 2026 item 94.03",
    )
    correction = ProductCorrectionPort()
    gateway = NabiCodeSafeErrorRecoveryGateway(correction, fiscal)

    with pytest.raises(PermissionError):
        gateway.execute(draft, object())
    assert correction.calls == []

    authorization = confirmed(draft)
    result = gateway.execute(draft, authorization)
    assert result["current_ncm"] == "94036000"
    assert result["commercial_data_preserved"] is True
    assert result["fiscal_authorization_claimed"] is False
    with pytest.raises(PermissionError):
        gateway.execute(draft, authorization)


def test_estado_desconhecido_somente_prepara_consulta_e_preserva_venda_comercial():
    fiscal = FiscalPort({
        "id": "42", "status": "RESPOSTA_DESCONHECIDA", "operation": "autorizacao",
        "receipt": "", "access_key": "1" * 44,
    })
    service = SafeErrorRecoveryDraftService(ProductPort(), fiscal)
    diagnosis = service.diagnose_fiscal_outbox(queue_id="42")
    assert diagnosis.fiscal_outcome == "DESCONHECIDO_REQUER_CONSULTA"
    assert diagnosis.safe_action == "RECONCILIAR_DESCONHECIDO"
    assert diagnosis.authorization_confirmed is False
    assert diagnosis.commercial_sale_preserved is True

    draft = service.prepare_fiscal_recovery(queue_id="42")
    assert draft.operation_kind == "FISCAL_RECONCILE_UNKNOWN"
    gateway = NabiCodeSafeErrorRecoveryGateway(ProductCorrectionPort(), fiscal)
    result = gateway.execute(draft, confirmed(draft))

    assert ("reconcile", "42") in fiscal.calls
    assert not any(call[0] == "blind-retry" for call in fiscal.calls)
    assert result["blind_resend_performed"] is False
    assert result["authorization_claimed"] is False
    assert result["commercial_sale_preserved"] is True


def test_fila_sem_referencia_estado_mudado_e_erro_comum_falham_fechados():
    no_reference = FiscalPort({
        "id": "1", "status": "RESPOSTA_DESCONHECIDA", "operation": "autorizacao",
        "receipt": "", "access_key": "",
    })
    service = SafeErrorRecoveryDraftService(ProductPort(), no_reference)
    assert service.diagnose_fiscal_outbox(queue_id="1").safe_action == "BLOQUEADO_SEM_REFERENCIA"
    with pytest.raises(ValueError, match="nenhum reenvio"):
        service.prepare_fiscal_recovery(queue_id="1")

    ordinary_error = FiscalPort({
        "id": "2", "status": "ERRO", "operation": "autorizacao",
        "receipt": "", "access_key": "2" * 44,
    })
    service = SafeErrorRecoveryDraftService(ProductPort(), ordinary_error)
    assert service.diagnose_fiscal_outbox(queue_id="2").authorization_confirmed is False
    with pytest.raises(ValueError):
        service.prepare_fiscal_recovery(queue_id="2")

    changing = FiscalPort({
        "id": "3", "status": "RESPOSTA_DESCONHECIDA", "operation": "autorizacao",
        "receipt": "123", "access_key": "",
    })
    service = SafeErrorRecoveryDraftService(ProductPort(), changing)
    draft = service.prepare_fiscal_recovery(queue_id="3")
    changing.record["status"] = "CONCLUIDO"
    gateway = NabiCodeSafeErrorRecoveryGateway(ProductCorrectionPort(), changing)
    with pytest.raises(ValueError):
        gateway.execute(draft, confirmed(draft))
    assert not any(call[0] == "blind-retry" for call in changing.calls)


def test_consulta_de_recibo_nao_reenvia_documento_e_usuario_deve_coincidir():
    fiscal = FiscalPort({
        "id": "9", "status": "PENDENTE", "operation": "recibo",
        "receipt": "987654", "access_key": "",
    })
    service = SafeErrorRecoveryDraftService(ProductPort(), fiscal)
    draft = service.prepare_fiscal_recovery(queue_id="9")
    assert draft.operation_kind == "FISCAL_CHECK_RECEIPT"
    gateway = NabiCodeSafeErrorRecoveryGateway(ProductCorrectionPort(), fiscal)
    result = gateway.execute(draft, confirmed(draft))
    assert ("receipt", "9") in fiscal.calls
    assert result["blind_resend_performed"] is False

    other = FiscalPort({
        "id": "10", "status": "RESPOSTA_DESCONHECIDA", "operation": "autorizacao",
        "receipt": "1", "access_key": "",
    })
    other.actor = "outra"
    service = SafeErrorRecoveryDraftService(ProductPort(), other)
    draft = service.prepare_fiscal_recovery(queue_id="10")
    with pytest.raises(PermissionError, match="outro usuário"):
        NabiCodeSafeErrorRecoveryGateway(ProductCorrectionPort(), other).execute(
            draft, confirmed(draft)
        )
    assert not any(call[0] in {"reconcile", "receipt", "blind-retry"} for call in other.calls)


class MemoryDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            CREATE TABLE produtos(
                id INTEGER PRIMARY KEY, codigo TEXT, nome TEXT, ncm TEXT,
                tipo_produto TEXT, preco_venda TEXT, atualizado_em TEXT,
                observacao_comercial TEXT
            );
            CREATE TABLE assistant_operation_journal(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL UNIQUE,
                operation_kind TEXT NOT NULL, fingerprint TEXT NOT NULL,
                status TEXT NOT NULL, result_json TEXT NOT NULL DEFAULT '',
                username TEXT NOT NULL, created_at TEXT NOT NULL,
                committed_at TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO produtos VALUES(7,'P-7','MESA','','MERCADORIA','150.00','','PRESERVAR');
        """)

    @contextmanager
    def session(self, write=False):
        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise


class Repository:
    def __init__(self, database): self.database = database


class OfficialProductService:
    def __init__(self, database): self.produtos = Repository(database)
    def buscar(self, product_id, connection=None):
        row = connection.execute("SELECT * FROM produtos WHERE id=?", (product_id,)).fetchone()
        return dict(row) if row else None


def test_servico_real_corrige_apenas_ncm_atomico_idempotente_e_detecta_stale():
    database = MemoryDatabase()
    official = OfficialProductService(database)
    assisted = AssistedProductNcmCorrectionService(official)
    service = SafeErrorRecoveryDraftService(ProductPort(), FiscalPort({"id": "q"}))
    draft = service.prepare_ncm_correction(
        product_id=7, proposed_ncm="94036000", evidence_source="CONTADOR",
        evidence_reference="Parecer CRC 123",
    )
    kwargs = {
        "username": "maria", "idempotency_key": f"nabi:product-ncm:{draft.draft_id}",
        "operation_fingerprint": draft.fingerprint,
    }
    first = assisted.correct_ncm(draft, **kwargs)
    second = assisted.correct_ncm(draft, **kwargs)
    row = database.connection.execute(
        "SELECT ncm,preco_venda,observacao_comercial FROM produtos WHERE id=7"
    ).fetchone()
    assert first == second
    assert tuple(row) == ("94036000", "150.00", "PRESERVAR")
    assert database.connection.execute(
        "SELECT COUNT(*) FROM assistant_operation_journal"
    ).fetchone()[0] == 1

    product = ProductPort("94036000")
    stale_service = SafeErrorRecoveryDraftService(product, FiscalPort({"id": "q"}))
    stale = stale_service.prepare_ncm_correction(
        product_id=7, proposed_ncm="94032000", evidence_source="FORNECEDOR",
        evidence_reference="Ficha técnica 77",
    )
    database.connection.execute("UPDATE produtos SET ncm='94037000' WHERE id=7")
    database.connection.commit()
    with pytest.raises(RuntimeError, match="mudou desde a revisão"):
        assisted.correct_ncm(
            stale, username="maria", idempotency_key=f"nabi:product-ncm:{stale.draft_id}",
            operation_fingerprint=stale.fingerprint,
        )
    assert database.connection.execute(
        "SELECT COUNT(*) FROM assistant_operation_journal"
    ).fetchone()[0] == 1


class Security:
    def __init__(self):
        self.session = SimpleNamespace(user=SimpleNamespace(username="maria"))
    def is_expired(self): return False
    def require(self, module, action): return (module, action) in {("produtos", "view"), ("produtos", "edit")}
    def touch(self): pass


def test_porta_administrativa_deriva_usuario_da_sessao_e_recusa_forjado():
    product = SimpleNamespace(buscar=lambda product_id: {"id": product_id})
    assisted = SimpleNamespace(correct_ncm=lambda draft, **kwargs: kwargs["username"])
    management = ProductNcmCorrectionManagementService(product, Security(), assisted)
    assert management.get_product(7) == {"id": 7}
    with pytest.raises(PermissionError):
        management.correct_ncm(
            object(), username="invasor", idempotency_key="x", operation_fingerprint="0" * 64
        )


def test_composicao_desacoplada_registra_apenas_leitura_e_rascunho_sem_mutacao():
    security = SimpleNamespace(
        session=SimpleNamespace(user=SimpleNamespace(
            username="maria", profile="GERENTE", active=True,
        )),
        is_expired=lambda: False,
        require=lambda module, action: True,
    )
    audit = SimpleNamespace(record_event=lambda *args, **kwargs: None)
    recovery = SafeErrorRecoveryDraftService(
        ProductPort(), FiscalPort({"id": "1", "status": "PENDENTE"})
    )
    assistant = create_draft_assistant(
        model=object(), query_service=object(), security_service=security,
        audit_service=audit, session_id="sessao-1",
        safe_error_recovery_service=recovery,
        safe_error_recovery_executor=object(),
    )
    definitions = assistant._registry.definitions(actor=assistant._permissions.current_actor())
    by_name = {definition.name: definition for definition in definitions}
    assert by_name["produtos.diagnosticar_ncm"].kind.value == "READ"
    assert by_name["produtos.preparar_correcao_ncm"].kind.value == "DRAFT"
    assert by_name["fiscal.diagnosticar_fila"].kind.value == "READ"
    assert by_name["fiscal.preparar_consulta_segura"].kind.value == "DRAFT"
    assert all(definition.kind.value != "MUTATION" for definition in definitions)


def test_fluxos_offline_nao_abrem_socket_nem_pedem_certificado():
    fiscal = FiscalPort({
        "id": "offline", "status": "RESPOSTA_DESCONHECIDA",
        "operation": "autorizacao", "receipt": "123", "access_key": "",
    })
    service = SafeErrorRecoveryDraftService(ProductPort(), fiscal)
    with patch.object(socket, "socket", side_effect=AssertionError("rede proibida")):
        product_diagnosis = service.diagnose_product_ncm(product_id=7)
        fiscal_diagnosis = service.diagnose_fiscal_outbox(queue_id="offline")
        draft = service.prepare_fiscal_recovery(queue_id="offline")
    assert product_diagnosis.mutation_performed is False
    assert fiscal_diagnosis.mutation_performed is False
    assert draft.authorization_claimed is False
    assert not any("cert" in str(call).casefold() for call in fiscal.calls)
