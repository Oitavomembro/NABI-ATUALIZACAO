from __future__ import annotations

import json
import re

from repositories.assistant_operation_journal_repository import (
    AssistantOperationJournalRepository,
)
from services.fiscal_product_profile import FiscalProductProfile


class AssistedProductNcmCorrectionService:
    """Altera somente o NCM e o diário idempotente na mesma transação local."""

    OPERATION = "PRODUCT_NCM_CORRECTION"
    EVIDENCE_SOURCES = frozenset({
        "CONTADOR", "DOCUMENTO_FISCAL", "FORNECEDOR", "TABELA_OFICIAL",
    })

    def __init__(self, product_service) -> None:
        if product_service is None or getattr(product_service, "produtos", None) is None:
            raise ValueError("O serviço oficial de produtos é obrigatório.")
        self._products = product_service
        self._database = product_service.produtos.database
        self._journal = AssistantOperationJournalRepository()

    @staticmethod
    def _identity(key: str, fingerprint: str, username: str) -> tuple[str, str, str]:
        key = str(key or "").strip()
        fingerprint = str(fingerprint or "").strip().lower()
        username = str(username or "").strip()
        if not key or len(key) > 160:
            raise ValueError("Chave idempotente inválida.")
        if not key.startswith("nabi:product-ncm:"):
            raise ValueError("A chave idempotente não pertence à correção NCM.")
        if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise ValueError("Impressão digital da operação inválida.")
        if not username:
            raise PermissionError("Usuário autenticado é obrigatório.")
        return key, fingerprint, username

    @staticmethod
    def _valid_ncm(value: str) -> str:
        normalized = FiscalProductProfile.digits(value)
        if str(value or "").strip() != normalized:
            raise ValueError("A correção exige exatamente os 8 dígitos do NCM.")
        if len(normalized) != 8 or normalized == "00000000":
            raise ValueError("NCM deve possuir 8 dígitos e não pode ser genérico.")
        return normalized

    def correct_ncm(
        self, draft, *, username: str, idempotency_key: str,
        operation_fingerprint: str,
    ) -> dict[str, object]:
        if str(getattr(draft, "operation_kind", "")) != self.OPERATION:
            raise TypeError("Rascunho de correção NCM inválido.")
        key, fingerprint, actor = self._identity(
            idempotency_key, operation_fingerprint, username
        )
        proposed = self._valid_ncm(draft.proposed_ncm)
        source = str(getattr(draft, "evidence_source", "")).strip().upper()
        reference = str(getattr(draft, "evidence_reference", "")).strip()
        if source not in self.EVIDENCE_SOURCES or not 3 <= len(reference) <= 160:
            raise ValueError("A correção NCM exige uma fonte humana/documental verificável.")
        with self._database.session(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            replay = self._journal.get(connection, key)
            if replay is not None:
                if replay["fingerprint"].lower() != fingerprint:
                    raise ValueError("A chave idempotente já pertence a outro conteúdo.")
                if replay["status"] != "COMMITTED":
                    raise RuntimeError("A correção assistida possui estado persistente desconhecido.")
                return json.loads(replay["result_json"])
            self._journal.begin(
                connection, idempotency_key=key, operation_kind=self.OPERATION,
                fingerprint=fingerprint, username=actor,
            )
            product = self._products.buscar(int(draft.product_id), connection=connection)
            if product is None:
                raise ValueError("Produto não encontrado durante a confirmação.")
            if str(product.get("tipo_produto") or "MERCADORIA").upper() == "SERVICO":
                raise ValueError("Serviço não recebe correção NCM por este trilho.")
            current = FiscalProductProfile.digits(product.get("ncm"))
            if current != str(draft.expected_current_ncm):
                raise RuntimeError("O NCM mudou desde a revisão; gere um novo diagnóstico.")
            if current == proposed:
                raise ValueError("O NCM proposto já está cadastrado.")
            updated = connection.execute(
                "UPDATE produtos SET ncm=?,atualizado_em=datetime('now','localtime') WHERE id=?",
                (proposed, int(draft.product_id)),
            )
            if updated.rowcount != 1:
                raise RuntimeError("A correção pontual do NCM não foi aplicada.")
            payload: dict[str, object] = {
                "product_id": int(draft.product_id),
                "previous_ncm": current,
                "current_ncm": proposed,
                "evidence_source": source,
                "commercial_data_preserved": True,
                "fiscal_authorization_claimed": False,
            }
            self._journal.commit(
                connection, idempotency_key=key,
                result_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
            )
            return payload
