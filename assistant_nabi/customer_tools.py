from __future__ import annotations

from .contracts import (
    CapabilityLevel, ParameterDefinition, ParameterType, ToolDefinition,
    ToolKind, ToolRequest, ToolSchema,
)


PREPARE_CUSTOMER_REGISTRATION = ToolDefinition(
    "clientes.preparar_cadastro",
    ToolKind.DRAFT,
    CapabilityLevel.DRAFT,
    "clientes",
    "create",
    ToolSchema((
        ParameterDefinition("name", ParameterType.TEXT, required=True, max_length=160),
        ParameterDefinition("code", ParameterType.TEXT, max_length=40),
        ParameterDefinition("record_number", ParameterType.INTEGER),
        ParameterDefinition("cpf", ParameterType.TEXT, max_length=20),
        ParameterDefinition("rg", ParameterType.TEXT, max_length=30),
        ParameterDefinition("phone", ParameterType.TEXT, max_length=30),
        ParameterDefinition("address", ParameterType.TEXT, max_length=300),
        ParameterDefinition("notes", ParameterType.TEXT, max_length=500),
        ParameterDefinition("credit_limit", ParameterType.DECIMAL_TEXT),
    )),
)


class PrepareCustomerRegistrationTool:
    def __init__(self, service) -> None:
        self._service = service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        draft = self._service.create(**request.parameters)
        return {
            "draft_id": draft.draft_id,
            "fingerprint": draft.fingerprint,
            "operation_kind": draft.operation_kind,
            "name": draft.name,
            "code": draft.code,
            "record_number": draft.record_number,
            "cpf": draft.cpf,
            "rg": draft.rg,
            "phone": draft.phone,
            "address": draft.address,
            "notes": draft.notes,
            "credit_limit": format(draft.credit_limit, "f"),
            "requires_reinforced_confirmation": True,
            "persisted": False,
        }


def register_customer_draft_tools(registry, service) -> None:
    registry.register(
        PREPARE_CUSTOMER_REGISTRATION,
        PrepareCustomerRegistrationTool(service),
    )
