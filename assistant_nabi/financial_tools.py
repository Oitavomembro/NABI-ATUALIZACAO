from __future__ import annotations

from .contracts import (
    CapabilityLevel, ParameterDefinition, ParameterType, ToolDefinition,
    ToolKind, ToolRequest, ToolSchema,
)


def _definition(name, action, fields):
    return ToolDefinition(name, ToolKind.DRAFT, CapabilityLevel.DRAFT,
                          "financeiro", action, ToolSchema(tuple(fields)))


PREPARE_FINANCIAL_TITLE = _definition("financeiro.preparar_titulo", "create", (
    ParameterDefinition("title_type", ParameterType.TEXT, True, 10, ("RECEBER", "PAGAR")),
    ParameterDefinition("amount", ParameterType.DECIMAL_TEXT, True),
    ParameterDefinition("due_date", ParameterType.TEXT, True, 10),
    ParameterDefinition("party_id", ParameterType.INTEGER),
    ParameterDefinition("party_name", ParameterType.TEXT, max_length=120),
    ParameterDefinition("document", ParameterType.TEXT, max_length=80),
    ParameterDefinition("description", ParameterType.TEXT, max_length=200),
    ParameterDefinition("notes", ParameterType.TEXT, max_length=300),
    ParameterDefinition("issue_date", ParameterType.TEXT, max_length=10),
))

PREPARE_FINANCIAL_SETTLEMENT = _definition("financeiro.preparar_baixa", "pay", (
    ParameterDefinition("title_type", ParameterType.TEXT, True, 10, ("RECEBER", "PAGAR")),
    ParameterDefinition("title_id", ParameterType.INTEGER, True),
    ParameterDefinition("amount", ParameterType.DECIMAL_TEXT, True),
    ParameterDefinition("payment_method", ParameterType.TEXT, True, 20),
    ParameterDefinition("payment_date", ParameterType.TEXT, True, 10),
    ParameterDefinition("notes", ParameterType.TEXT, max_length=300),
))


class PrepareFinancialTitleTool:
    def __init__(self, service): self._service = service
    def execute(self, request: ToolRequest, *, actor):
        return _payload(self._service.create_title(**request.parameters))


class PrepareFinancialSettlementTool:
    def __init__(self, service): self._service = service
    def execute(self, request: ToolRequest, *, actor):
        return _payload(self._service.settle_title(**request.parameters))


def _payload(draft):
    data = {
        "draft_id": draft.draft_id, "fingerprint": draft.fingerprint,
        "operation_kind": draft.operation_kind, "title_type": draft.title_type,
        "title_id": draft.title_id, "amount": format(draft.amount, "f"),
        "party_id": draft.party_id, "party_name": draft.party_name,
        "document": draft.document, "description": draft.description,
        "notes": draft.notes, "payment_method": draft.payment_method,
        "due_date": draft.due_date.isoformat() if draft.due_date else None,
        "issue_date": draft.issue_date.isoformat() if draft.issue_date else None,
        "payment_date": draft.payment_date.isoformat() if draft.payment_date else None,
        "previous_open_amount": (format(draft.previous_open_amount, "f")
                                 if draft.previous_open_amount is not None else None),
        "expected_open_amount": (format(draft.expected_open_amount, "f")
                                 if draft.expected_open_amount is not None else None),
        "requires_reinforced_confirmation": True, "persisted": False,
    }
    return data


def register_financial_draft_tools(registry, service):
    registry.register(PREPARE_FINANCIAL_TITLE, PrepareFinancialTitleTool(service))
    registry.register(PREPARE_FINANCIAL_SETTLEMENT, PrepareFinancialSettlementTool(service))
