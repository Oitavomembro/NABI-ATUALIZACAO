from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional


@dataclass(frozen=True)
class LicenseStatus:
    blocked: bool
    days_remaining: Optional[int] = None
    reason: str = ""
    invalid_value: bool = False


class LicenseService:
    """Centraliza as regras de expiração sem depender da interface gráfica."""

    def __init__(
        self,
        get_config: Callable[[str], str],
        set_config: Callable[[str, str], None],
        *,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._get = get_config
        self._set = set_config
        self._now = now

    def evaluate(self) -> LicenseStatus:
        if self._value("licenca_bloqueada") == "1":
            return LicenseStatus(True, reason="BLOQUEADA")

        current = self._now()
        exact = self._value("licenca_expira_em")
        if exact:
            try:
                limit = datetime.fromisoformat(exact)
            except ValueError:
                self._set("licenca_expira_em", "")
                return LicenseStatus(False, reason="EXPIRACAO_EXATA_INVALIDA", invalid_value=True)
            if current >= limit:
                self._block(clear_exact=False)
                return LicenseStatus(True, reason="EXPIRACAO_EXATA")
            return LicenseStatus(False, reason="ATIVA_EXATA")

        date_value = self._value("licenca_validade")
        if not date_value:
            return LicenseStatus(False, reason="SEM_VALIDADE")
        try:
            valid_date = datetime.strptime(date_value, "%Y-%m-%d")
        except ValueError:
            return LicenseStatus(False, reason="VALIDADE_INVALIDA", invalid_value=True)

        exclusive_limit = valid_date + timedelta(days=1)
        if current >= exclusive_limit:
            self._block(clear_exact=False)
            return LicenseStatus(True, reason="VALIDADE_EXPIRADA")
        return LicenseStatus(False, days_remaining=(valid_date.date() - current.date()).days, reason="ATIVA")

    def monitor_exact_expiration(self) -> LicenseStatus:
        """Verificação leve usada pelo monitor periódico da interface."""
        if self._value("licenca_bloqueada") == "1":
            return LicenseStatus(True, reason="BLOQUEADA")
        exact = self._value("licenca_expira_em")
        if not exact:
            return LicenseStatus(False, reason="SEM_EXPIRACAO_EXATA")
        try:
            expired = self._now() >= datetime.fromisoformat(exact)
        except ValueError:
            self._set("licenca_expira_em", "")
            return LicenseStatus(False, reason="EXPIRACAO_EXATA_INVALIDA", invalid_value=True)
        if expired:
            self._block(clear_exact=True)
            return LicenseStatus(True, reason="EXPIRACAO_EXATA")
        return LicenseStatus(False, reason="ATIVA")

    def unlock_for_days(self, days: int = 30) -> str:
        """Persiste a liberação administrativa já adotada pela interface."""

        if int(days) <= 0:
            raise ValueError("A duração da liberação deve ser positiva.")
        new_date = (self._now() + timedelta(days=int(days))).strftime("%Y-%m-%d")
        self._set("licenca_validade", new_date)
        self._set("licenca_expira_em", "")
        self._set("licenca_bloqueada", "0")
        return new_date

    def attempt_admin_unlock(
        self,
        password: str,
        verifier: Callable[[str], bool],
        *,
        days: int = 30,
    ) -> bool:
        """Só persiste a liberação depois de autenticação administrativa válida."""

        if not verifier(str(password or "")):
            return False
        self.unlock_for_days(days)
        return True

    def _block(self, *, clear_exact: bool) -> None:
        self._set("licenca_bloqueada", "1")
        if clear_exact:
            self._set("licenca_expira_em", "")

    def _value(self, key: str) -> str:
        value = self._get(key)
        return "" if value is None else str(value).strip()
