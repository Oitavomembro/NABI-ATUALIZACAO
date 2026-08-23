from __future__ import annotations

from .contracts import (
    AssistantActor,
    AssistantAuditPort,
    CapabilityLevel,
    PermissionPort,
    ReadToolPort,
    ToolDefinition,
    ToolKind,
    ToolRequest,
    ToolResult,
)


class ReadOnlyToolRegistry:
    """Catálogo fail-closed da Fase 0; aceita exclusivamente consultas registradas."""

    def __init__(self, *, permissions: PermissionPort, audit: AssistantAuditPort) -> None:
        self._permissions = permissions
        self._audit = audit
        self._tools: dict[str, tuple[ToolDefinition, ReadToolPort]] = {}

    def register(self, definition: ToolDefinition, handler: ReadToolPort) -> None:
        if definition.kind is not ToolKind.READ or definition.capability is not CapabilityLevel.READ:
            raise ValueError("A Fase 0 aceita somente ferramentas de leitura.")
        if not isinstance(handler, ReadToolPort):
            raise TypeError("O manipulador não cumpre a porta de leitura.")
        if definition.name in self._tools:
            raise ValueError(f"Ferramenta já registrada: {definition.name}.")
        self._tools[definition.name] = (definition, handler)
    def definitions(self, *, actor: AssistantActor) -> tuple[ToolDefinition, ...]:
        return tuple(
            definition
            for definition, _handler in self._tools.values()
            if self._permissions.allows(
                actor, definition.permission_module, definition.permission_action
            )
        )

    def execute(self, request: ToolRequest, *, actor: AssistantActor) -> ToolResult:
        registered = self._tools.get(request.tool_name)
        if registered is None:
            return self._audited_failure(actor, request, "Ferramenta não registrada.")
        definition, handler = registered
        if not self._permissions.allows(
            actor, definition.permission_module, definition.permission_action
        ):
            return self._audited_failure(actor, request, "Permissão insuficiente.")
        try:
            definition.schema.validate(request.parameters)
        except ValueError as error:
            return self._audited_failure(actor, request, str(error))
        try:
            payload = handler.execute(request, actor=actor)
            result = ToolResult(request.request_id, request.tool_name, True, payload)
        except Exception:
            result = ToolResult(
                request.request_id,
                request.tool_name,
                False,
                message="A consulta não pôde ser concluída.",
            )
        self._audit.record(actor=actor, request=request, result=result)
        return result

    def _audited_failure(
        self, actor: AssistantActor, request: ToolRequest, message: str
    ) -> ToolResult:
        result = ToolResult(request.request_id, request.tool_name, False, message=message)
        self._audit.record(actor=actor, request=request, result=result)
        return result


class DraftToolRegistry(ReadOnlyToolRegistry):
    """Aceita consultas e rascunhos, mas recusa qualquer mutação."""

    def register(self, definition: ToolDefinition, handler: ReadToolPort) -> None:
        if (definition.kind, definition.capability) not in {
            (ToolKind.READ, CapabilityLevel.READ),
            (ToolKind.DRAFT, CapabilityLevel.DRAFT),
        }:
            raise ValueError("A Fase 2 aceita somente consultas e rascunhos.")
        if not isinstance(handler, ReadToolPort):
            raise TypeError("O manipulador não cumpre a porta de ferramenta.")
        if definition.name in self._tools:
            raise ValueError(f"Ferramenta já registrada: {definition.name}.")
        self._tools[definition.name] = (definition, handler)
