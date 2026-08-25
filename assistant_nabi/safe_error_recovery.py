"""Diagnóstico e rascunhos seguros para falhas cadastrais e fiscais.

Este módulo não transmite, não consulta a rede e não altera dados. Ele apenas lê
portas oficiais e produz rascunhos imutáveis que ainda exigem confirmação humana.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Any, Mapping
from uuid import uuid4


NCM_EVIDENCE_SOURCES = frozenset({
    "CONTADOR",
    "DOCUMENTO_FISCAL",
    "FORNECEDOR",
    "TABELA_OFICIAL",
})


def _digits(value: Any) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


def _fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _field(value: Any, name: str, default: Any = "") -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


@dataclass(frozen=True, slots=True)
class ProductNcmDiagnosis:
    product_id: int
    product_code: str
    product_description: str
    current_ncm: str
    diagnostic_code: str
    message: str
    suggested_ncm: None = None
    mutation_performed: bool = False


@dataclass(frozen=True, slots=True)
class ProductNcmCorrectionDraft:
    draft_id: str
    fingerprint: str
    product_id: int
    product_code: str
    product_description: str
    expected_current_ncm: str
    proposed_ncm: str
    evidence_source: str
    evidence_reference: str
    operation_kind: str = "PRODUCT_NCM_CORRECTION"


@dataclass(frozen=True, slots=True)
class FiscalOutboxDiagnosis:
    queue_id: str
    status: str
    operation: str
    fiscal_outcome: str
    safe_action: str
    has_receipt: bool
    has_access_key: bool
    commercial_sale_preserved: bool = True
    authorization_confirmed: bool = False
    mutation_performed: bool = False


@dataclass(frozen=True, slots=True)
class FiscalRecoveryDraft:
    draft_id: str
    fingerprint: str
    queue_id: str
    observed_status: str
    safe_action: str
    operation_kind: str
    commercial_sale_preserved: bool = True
    authorization_claimed: bool = False


class SafeErrorRecoveryDraftService:
    """Prepara correções/consultas sem inventar classificação ou efeito fiscal."""

    def __init__(self, product_port, fiscal_outbox_port, *, max_drafts: int = 30) -> None:
        if product_port is None or fiscal_outbox_port is None:
            raise ValueError("As portas oficiais de produto e fila fiscal são obrigatórias.")
        self._products = product_port
        self._fiscal = fiscal_outbox_port
        self._max = max(1, min(int(max_drafts), 100))
        self._drafts: OrderedDict[str, Any] = OrderedDict()
        self._lock = Lock()

    def _store(self, draft):
        with self._lock:
            self._drafts[draft.draft_id] = draft
            while len(self._drafts) > self._max:
                self._drafts.popitem(last=False)
        return draft

    def get(self, draft_id: str):
        with self._lock:
            draft = self._drafts.get(str(draft_id or ""))
        if draft is None:
            raise ValueError("Rascunho de recuperação não encontrado ou descartado.")
        return draft

    def diagnose_product_ncm(self, *, product_id: int) -> ProductNcmDiagnosis:
        product = self._products.get_product(int(product_id))
        if product is None:
            raise ValueError("Produto não encontrado.")
        raw_ncm = str(_field(product, "ncm") or "").strip()
        normalized = _digits(raw_ncm)
        if not normalized:
            code = "NCM_AUSENTE"
            message = "O produto não possui NCM; confirme a classificação com uma fonte humana confiável."
        elif len(normalized) != 8 or normalized == "00000000":
            code = "NCM_INVALIDO"
            message = "O NCM cadastrado é inválido; a Nabi não propõe nem completa classificações."
        else:
            code = "NCM_FORMATO_VALIDO_NAO_CLASSIFICADO"
            message = (
                "O NCM possui formato válido, mas a Nabi não confirma a classificação fiscal; "
                "valide-a com a contabilidade ou outra fonte oficial."
            )
        return ProductNcmDiagnosis(
            product_id=int(_field(product, "product_id", _field(product, "id"))),
            product_code=str(_field(product, "code", _field(product, "codigo")) or ""),
            product_description=str(
                _field(product, "description", _field(product, "nome", "PRODUTO")) or "PRODUTO"
            ),
            current_ncm=normalized,
            diagnostic_code=code,
            message=message,
        )

    def prepare_ncm_correction(
        self, *, product_id: int, proposed_ncm: str,
        evidence_source: str, evidence_reference: str,
    ) -> ProductNcmCorrectionDraft:
        diagnosis = self.diagnose_product_ncm(product_id=int(product_id))
        proposed = str(proposed_ncm or "").strip()
        if not proposed.isdigit() or len(proposed) != 8 or proposed == "00000000":
            raise ValueError("Informe exatamente os 8 dígitos de um NCM não genérico.")
        source = str(evidence_source or "").strip().upper()
        if source not in NCM_EVIDENCE_SOURCES:
            raise ValueError("A origem humana/documental do NCM é obrigatória e deve ser reconhecida.")
        reference = str(evidence_reference or "").strip()
        if len(reference) < 3 or len(reference) > 160:
            raise ValueError("Informe uma referência verificável da origem do NCM.")
        if proposed == diagnosis.current_ncm:
            raise ValueError("O NCM proposto é igual ao cadastro atual.")
        payload = {
            "product_id": diagnosis.product_id,
            "expected_current_ncm": diagnosis.current_ncm,
            "proposed_ncm": proposed,
            "evidence_source": source,
            "evidence_reference": reference,
        }
        return self._store(ProductNcmCorrectionDraft(
            draft_id=uuid4().hex,
            fingerprint=_fingerprint(payload),
            product_id=diagnosis.product_id,
            product_code=diagnosis.product_code,
            product_description=diagnosis.product_description,
            expected_current_ncm=diagnosis.current_ncm,
            proposed_ncm=proposed,
            evidence_source=source,
            evidence_reference=reference,
        ))

    def _queue_item(self, queue_id: str) -> Mapping[str, Any]:
        normalized_id = str(queue_id or "").strip()
        if not normalized_id or len(normalized_id) > 80:
            raise ValueError("Identificador da fila fiscal inválido.")
        rows = self._fiscal.list_transmission_queue()
        target = next(
            (row for row in rows if str(_field(row, "id")) == normalized_id), None
        )
        if target is None:
            raise ValueError("Item da fila fiscal não encontrado.")
        return target

    def diagnose_fiscal_outbox(self, *, queue_id: str) -> FiscalOutboxDiagnosis:
        target = self._queue_item(queue_id)
        status = str(_field(target, "status") or "").strip().upper()
        operation = str(_field(target, "operation") or "").strip().lower()
        has_receipt = bool(_digits(_field(target, "receipt")))
        has_key = len(_digits(_field(target, "access_key"))) == 44
        if status == "RESPOSTA_DESCONHECIDA":
            outcome = "DESCONHECIDO_REQUER_CONSULTA"
            action = "RECONCILIAR_DESCONHECIDO" if has_receipt or has_key else "BLOQUEADO_SEM_REFERENCIA"
        elif operation == "recibo" and has_receipt and status not in {"CONCLUIDO", "CANCELADO"}:
            outcome = "PENDENTE_DE_CONSULTA"
            action = "CONSULTAR_RECIBO"
        elif status == "CONCLUIDO":
            outcome = "FINALIZADO_NAO_INFERIDO"
            action = "NENHUMA"
        elif status == "CANCELADO":
            outcome = "CANCELADO_LOCALMENTE"
            action = "NENHUMA"
        elif status in {"PENDENTE", "PROCESSANDO", "ERRO"}:
            outcome = "SEM_AUTORIZACAO_COMPROVADA"
            action = "AGUARDAR_OU_ANALISAR_MANUALMENTE"
        else:
            outcome = "ESTADO_NAO_RECONHECIDO"
            action = "BLOQUEADO_PARA_ANALISE_HUMANA"
        return FiscalOutboxDiagnosis(
            queue_id=str(_field(target, "id")), status=status, operation=operation,
            fiscal_outcome=outcome, safe_action=action,
            has_receipt=has_receipt, has_access_key=has_key,
        )

    def prepare_fiscal_recovery(self, *, queue_id: str) -> FiscalRecoveryDraft:
        diagnosis = self.diagnose_fiscal_outbox(queue_id=queue_id)
        operations = {
            "RECONCILIAR_DESCONHECIDO": "FISCAL_RECONCILE_UNKNOWN",
            "CONSULTAR_RECIBO": "FISCAL_CHECK_RECEIPT",
        }
        operation_kind = operations.get(diagnosis.safe_action)
        if operation_kind is None:
            raise ValueError(
                "O estado atual não permite uma consulta fiscal segura pela Nabi; nenhum reenvio foi preparado."
            )
        payload = {
            "queue_id": diagnosis.queue_id,
            "observed_status": diagnosis.status,
            "safe_action": diagnosis.safe_action,
            "operation_kind": operation_kind,
        }
        return self._store(FiscalRecoveryDraft(
            draft_id=uuid4().hex,
            fingerprint=_fingerprint(payload),
            queue_id=diagnosis.queue_id,
            observed_status=diagnosis.status,
            safe_action=diagnosis.safe_action,
            operation_kind=operation_kind,
        ))
