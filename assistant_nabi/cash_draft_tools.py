from __future__ import annotations

from .contracts import (CapabilityLevel, ParameterDefinition, ParameterType,
                        ToolDefinition, ToolKind, ToolRequest, ToolSchema)


def _definition(name, fields):
    return ToolDefinition(name, ToolKind.DRAFT, CapabilityLevel.DRAFT,
                          "financeiro", "pay", ToolSchema(tuple(fields)))


PREPARE_CASH_OPEN = _definition("caixa.preparar_abertura", (
    ParameterDefinition("opening_balance", ParameterType.DECIMAL_TEXT, True),
    ParameterDefinition("informed", ParameterType.BOOLEAN, True),
))
PREPARE_CASH_MOVEMENT = _definition("caixa.preparar_movimento", (
    ParameterDefinition("movement_type", ParameterType.TEXT, True, 10, ("SANGRIA", "SUPRIMENTO")),
    ParameterDefinition("amount", ParameterType.DECIMAL_TEXT, True),
    ParameterDefinition("note", ParameterType.TEXT, max_length=300),
))
PREPARE_CASH_CLOSE = _definition("caixa.preparar_fechamento", (
    ParameterDefinition("counted_cash", ParameterType.DECIMAL_TEXT, True),
    ParameterDefinition("note", ParameterType.TEXT, max_length=300),
))


class _Tool:
    method = ""
    def __init__(self, service): self._service = service
    def execute(self, request: ToolRequest, *, actor):
        draft = getattr(self._service, self.method)(**request.parameters)
        return {"draft_id": draft.draft_id, "fingerprint": draft.fingerprint,
                "operation_kind": draft.operation_kind, "terminal": draft.terminal,
                "amount": format(draft.amount, ".2f"), "note": draft.note,
                "expected_session_id": draft.expected_session_id,
                "requires_reinforced_confirmation": True, "persisted": False}


class PrepareCashOpenTool(_Tool): method = "prepare_open"
class PrepareCashMovementTool(_Tool): method = "prepare_movement"
class PrepareCashCloseTool(_Tool): method = "prepare_close"


def register_cash_draft_tools(registry, service):
    registry.register(PREPARE_CASH_OPEN, PrepareCashOpenTool(service))
    registry.register(PREPARE_CASH_MOVEMENT, PrepareCashMovementTool(service))
    registry.register(PREPARE_CASH_CLOSE, PrepareCashCloseTool(service))
