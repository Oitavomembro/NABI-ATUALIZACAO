from __future__ import annotations

from .contracts import (
    CapabilityLevel, ParameterDefinition, ParameterType, ToolDefinition,
    ToolKind, ToolRequest, ToolSchema,
)


PREPARE_CUSTOMER_RECEIPT = ToolDefinition(
    "clientes.preparar_recebimento",
    ToolKind.DRAFT,
    CapabilityLevel.DRAFT,
    "financeiro",
    "pay",
    ToolSchema((
        ParameterDefinition("customer_id", ParameterType.INTEGER, required=True),
        ParameterDefinition("amount", ParameterType.DECIMAL_TEXT, required=True),
        ParameterDefinition("payment_method", ParameterType.TEXT, required=True, max_length=20),
        ParameterDefinition("payment_date", ParameterType.TEXT, required=True, max_length=10),
        ParameterDefinition("notes", ParameterType.TEXT, max_length=300),
    )),
)


class PrepareCustomerReceiptTool:
    def __init__(self, service) -> None:
        self._service = service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        draft = self._service.create(**request.parameters)
        return {
            "draft_id": draft.draft_id,
            "fingerprint": draft.fingerprint,
            "operation_kind": draft.operation_kind,
            "customer_id": draft.customer_id,
            "record_number": draft.record_number,
            "customer_name": draft.customer_name,
            "amount": format(draft.amount, "f"),
            "previous_balance": format(draft.previous_balance, "f"),
            "expected_balance": format(draft.expected_balance, "f"),
            "payment_method": draft.payment_method,
            "payment_date": draft.payment_date.isoformat(),
            "notes": draft.notes,
            "requires_reinforced_confirmation": True,
            "persisted": False,
        }


def register_customer_receipt_tools(registry, service) -> None:
    registry.register(PREPARE_CUSTOMER_RECEIPT, PrepareCustomerReceiptTool(service))
