from __future__ import annotations


class AssistantProviderUnavailableError(RuntimeError):
    """Indica que nenhum provedor de linguagem foi configurado."""


class UnavailableLanguageModelAdapter:
    """Provider inerte: falha localmente e nunca tenta acessar rede ou arquivos."""

    def respond(self, message: str, *, available_tools):
        raise AssistantProviderUnavailableError(
            "Nenhum provedor de linguagem foi configurado para a Nabi."
        )
