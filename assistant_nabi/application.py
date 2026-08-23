from __future__ import annotations

from .contracts import AssistantTurn, LanguageModelPort, ModelReply


class AssistantApplicationService:
    """Orquestra conversa e consultas sem conceder autoridade ao modelo."""

    def __init__(
        self,
        *,
        model: LanguageModelPort,
        registry,
        permissions,
        max_tool_calls: int = 4,
        max_message_length: int = 2000,
    ) -> None:
        self._model = model
        self._registry = registry
        self._permissions = permissions
        self._max_tool_calls = max(1, min(int(max_tool_calls), 10))
        self._max_message_length = max(100, min(int(max_message_length), 10_000))

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

    @staticmethod
    def _failure(message: str) -> AssistantTurn:
        return AssistantTurn(message, safe_failure=True)
