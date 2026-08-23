from __future__ import annotations

from .contracts import AssistantTurn, LanguageModelPort, ModelReply


class UnavailableAssistantService:
    """Falha fechada usada enquanto modelo e sessao nao foram homologados."""

    available = False

    def __init__(self, message: str) -> None:
        self.unavailable_message = str(message).strip()

    def ask(self, message: str) -> AssistantTurn:
        return AssistantTurn(self.unavailable_message, safe_failure=True)


class AssistantApplicationService:
    """Orquestra conversa e consultas sem conceder autoridade ao modelo."""

    available = True

    def __init__(
        self,
        *,
        model: LanguageModelPort,
        registry,
        permissions,
        max_tool_calls: int = 4,
        max_message_length: int = 2000,
        draft_service=None,
        confirmation_service=None,
        purchase_executor=None,
    ) -> None:
        self._model = model
        self._registry = registry
        self._permissions = permissions
        self._max_tool_calls = max(1, min(int(max_tool_calls), 10))
        self._max_message_length = max(100, min(int(max_message_length), 10_000))
        self._drafts = draft_service
        self._confirmations = confirmation_service
        self._purchase_executor = purchase_executor

    def ask(self, message: str) -> AssistantTurn:
        text = str(message or "").strip()
        if not text:
            return self._failure("Digite uma pergunta para a Nabi.")
        if len(text) > self._max_message_length:
            return self._failure("A mensagem excede o tamanho permitido.")
        try:
            actor = self._permissions.current_actor()
            definitions = self._registry.definitions(actor=actor)
            reply = self._model.respond(text, available_tools=definitions)
        except Exception:
            return self._failure(
                "A Nabi está indisponível no momento. O NabiCode continua funcionando normalmente."
            )
        if not isinstance(reply, ModelReply):
            return self._failure("O provedor da Nabi retornou uma resposta inválida.")
        if len(reply.tool_requests) > self._max_tool_calls:
            return self._failure("A solicitação excedeu o limite seguro de consultas.")
        results = tuple(
            self._registry.execute(request, actor=actor)
            for request in reply.tool_requests
        )
        return AssistantTurn(reply.message, results)

    def review_draft(self, draft_id: str, fingerprint: str):
        if self._drafts is None or self._confirmations is None:
            raise RuntimeError("Confirmação de rascunho não está configurada.")
        actor = self._permissions.current_actor()
        draft = self._drafts.get(draft_id)
        if draft.fingerprint != str(fingerprint or ""):
            raise PermissionError("O rascunho mudou antes da revisão.")
        return self._confirmations.issue(draft, actor=actor)

    def confirm_draft(self, token: str, draft_id: str, fingerprint: str):
        if self._drafts is None or self._confirmations is None:
            raise RuntimeError("Confirmação de rascunho não está configurada.")
        actor = self._permissions.current_actor()
        draft = self._drafts.get(draft_id)
        permission = {
            "SALE": ("vendas", "create"),
            "PURCHASE_RECEIPT": ("compras", "create"),
        }.get(str(getattr(draft, "operation_kind", "")))
        if permission is None or not self._permissions.allows(actor, *permission):
            raise PermissionError("A permissão para confirmar o rascunho não está disponível.")
        if draft.fingerprint != str(fingerprint or ""):
            raise PermissionError("O rascunho mudou depois da revisão.")
        authorization = self._confirmations.confirm(
            token=token, draft=draft, actor=actor
        )
        return draft, authorization

    def confirm_and_execute_purchase(
        self, token: str, draft_id: str, fingerprint: str
    ):
        if self._purchase_executor is None:
            raise RuntimeError("Execução assistida de compras não está configurada.")
        draft, authorization = self.confirm_draft(token, draft_id, fingerprint)
        if getattr(draft, "operation_kind", "") != "PURCHASE_RECEIPT":
            raise TypeError("O rascunho confirmado não é um recebimento de compra.")
        result = self._purchase_executor.execute(draft, authorization)
        return result, authorization

    def invalidate_confirmations(self) -> None:
        if self._confirmations is None:
            return
        try:
            actor = self._permissions.current_actor()
        except PermissionError:
            return
        self._confirmations.invalidate_session(actor.session_id)

    @staticmethod
    def _failure(message: str) -> AssistantTurn:
        return AssistantTurn(message, safe_failure=True)
