from __future__ import annotations

from .contracts import (
    CapabilityLevel, ParameterDefinition, ParameterType, ToolDefinition,
    ToolKind, ToolRequest, ToolSchema,
)


PREPARE_NFE_ENTRY = ToolDefinition(
    "compras.preparar_entrada_nfe_exata",
    ToolKind.DRAFT,
    CapabilityLevel.DRAFT,
    "compras",
    "create",
    ToolSchema((
        ParameterDefinition("review_draft_id", ParameterType.TEXT, required=True, max_length=64),
        ParameterDefinition("conversion_factors", ParameterType.DECIMAL_TEXT_LIST, required=True),
    )),
)


class PrepareNFeEntryTool:
    def __init__(self, service) -> None:
        self._service = service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        draft = self._service.prepare_exact_import(
            request.parameters["review_draft_id"],
            request.parameters["conversion_factors"],
        )
        return {
            "draft_id": draft.draft_id,
            "fingerprint": draft.fingerprint,
            "operation_kind": draft.operation_kind,
            "access_key": draft.access_key,
            "number": draft.number,
            "supplier_name": draft.supplier_name,
            "recipient_name": draft.recipient_name,
            "recipient_document": draft.recipient_document,
            "document_total": format(draft.document_total, "f"),
            "items": [{
                "product_id": item.product_id,
                "code": item.code,
                "description": item.description,
                "xml_quantity": format(item.xml_quantity, "f"),
                "conversion_factor": format(item.conversion_factor, "f"),
                "stock_quantity": format(item.stock_quantity, "f"),
                "unit_cost": format(item.unit_cost, "f"),
            } for item in draft.items],
            "requires_reinforced_confirmation": True,
            "persisted": False,
            "sefaz_access": False,
        }


def register_nfe_entry_draft_tools(registry, service) -> None:
    registry.register(PREPARE_NFE_ENTRY, PrepareNFeEntryTool(service))
