from __future__ import annotations

import hashlib
from pathlib import Path

from .contracts import CapabilityLevel


class NabiCodeNFeEntryAssistantGateway:
    """Executa entrada local confirmada pelo importador oficial, sem SEFAZ."""

    def __init__(self, draft_service, import_service) -> None:
        if draft_service is None or import_service is None:
            raise ValueError("Rascunho e importador oficial de NF-e são obrigatórios.")
        self._drafts = draft_service
        self._imports = import_service

    def execute(self, draft, authorization):
        if getattr(draft, "operation_kind", "") != "NFE_ENTRY_IMPORT":
            raise TypeError("O rascunho não representa entrada de NF-e.")
        if (
            authorization.draft_id != draft.draft_id
            or authorization.fingerprint != draft.fingerprint
        ):
            raise PermissionError("A autorização não pertence a esta entrada de NF-e.")
        if authorization.capability is not CapabilityLevel.REINFORCED_CONFIRMATION:
            raise PermissionError("A entrada de NF-e exige confirmação reforçada.")
        source = Path(draft.source_path).resolve(strict=True)
        if hashlib.sha256(source.read_bytes()).hexdigest() != draft.source_sha256:
            raise PermissionError("O XML mudou depois da confirmação.")
        document = self._drafts.document_for(draft.draft_id)
        items = [{
            "acao": "VINCULAR",
            "produto_id": item.product_id,
            "quantidade": format(item.xml_quantity, "f"),
            "fator": format(item.conversion_factor, "f"),
            "unidade": item.purchase_unit or "UN",
            "custo": format(item.unit_cost, "f"),
            "margem": "0",
            "preco": "0",
        } for item in draft.items]
        return self._imports.importar_atomicamente(
            document,
            arquivo_origem=source,
            itens=items,
            usuario=authorization.username,
            idempotency_key=f"nabi:nfe:{draft.draft_id}",
            operation_fingerprint=draft.fingerprint,
        )
