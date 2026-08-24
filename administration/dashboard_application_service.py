from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    indicators: object
    history: object


class DashboardApplicationService:
    """Fachada somente leitura com autorização e paginação obrigatórias."""

    def __init__(self, repository, security) -> None:
        if repository is None or security is None:
            raise ValueError("Dashboard e segurança são obrigatórios.")
        self.repository = repository; self.security = security

    def _require(self) -> None:
        if self.security.session is None or self.security.is_expired():
            raise PermissionError("Sessão expirada. Entre novamente.")
        if not self.security.require("dashboard", "view"):
            raise PermissionError("Usuário sem permissão para visualizar o Início.")
        self.security.touch()

    def load(self, *, limit: int = 50, offset: int = 0) -> DashboardSnapshot:
        self._require()
        safe_limit = max(1, min(int(limit), 100))
        safe_offset = max(0, int(offset))
        return DashboardSnapshot(
            indicators=self.repository.indicators(),
            history=self.repository.day_history_page(limit=safe_limit, offset=safe_offset),
        )

    def load_client_summary(self):
        """Resumo lateral autorizado; a GUI nunca consulta o banco diretamente."""

        self._require()
        return self.repository.client_summary()
