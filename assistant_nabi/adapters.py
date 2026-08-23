from __future__ import annotations

from .contracts import AssistantActor, ToolRequest, ToolResult


class CurrentSessionPermissionAdapter:
    """Vincula a Nabi à sessão autenticada real e às permissões do NabiCode."""

    def __init__(self, security_service, *, session_id: str) -> None:
        self._security = security_service
        self._session_id = str(session_id or "").strip()
        if not self._session_id:
            raise ValueError("A identificação da sessão da Nabi é obrigatória.")

    def current_actor(self) -> AssistantActor:
        session = getattr(self._security, "session", None)
        if session is None or self._security.is_expired():
            raise PermissionError("Não existe sessão autenticada ativa para a Nabi.")
        user = session.user
        if not bool(getattr(user, "active", False)):
            raise PermissionError("O usuário atual está inativo.")
        return AssistantActor(user.username, user.profile, self._session_id)

    def allows(self, actor: AssistantActor, module: str, action: str) -> bool:
        try:
            current = self.current_actor()
        except PermissionError:
            return False
        if actor != current:
            return False
        return bool(self._security.require(str(module), str(action)))


class AdminAssistantAuditAdapter:
    """Registra metadados operacionais sem persistir parâmetros ou segredos."""

    def __init__(self, audit_service, *, event_bus=None) -> None:
        self._audit = audit_service
        self._event_bus = event_bus

    def record(
        self,
        *,
        actor: AssistantActor,
        request: ToolRequest,
        result: ToolResult,
    ) -> None:
        self._audit.record_event(
            "IA_NABI",
            "CONSULTA_FERRAMENTA",
            object_id=request.tool_name,
            details=(
                f"request_id={request.request_id}; success={str(result.success).lower()}; "
                f"session_id={actor.session_id}"
            ),
            result="SUCESSO" if result.success else "NEGADO_OU_FALHA",
            user=actor.username,
            event_bus=self._event_bus,
        )
