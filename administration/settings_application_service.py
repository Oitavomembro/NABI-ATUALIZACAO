from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from core.config_manager import ConfigManager
from services.ui_preferences import UIPreferencesService


@dataclass(frozen=True, slots=True)
class SettingsSnapshot:
    username: str
    preferences: Mapping[str, Any]
    backup_directories: tuple[str, ...]
    daily_backup_enabled: bool


class SettingsApplicationService:
    """Porta autenticada para as configurações não fiscais do Qt."""

    def __init__(
        self,
        *,
        security,
        system_repository,
        config_path: str | Path,
        backup_service,
        diagnostics,
    ) -> None:
        self.security = security
        self.system_repository = system_repository
        self.config = ConfigManager(
            config_path,
            {
                "interface": UIPreferencesService.DEFAULTS,
                "interface_usuarios": {},
            },
        )
        self.backup_service = backup_service
        self.diagnostics = diagnostics

    def _require(self, action: str) -> str:
        session = getattr(self.security, "session", None)
        if session is None or self.security.is_expired():
            raise PermissionError("Sessão expirada. Entre novamente.")
        if not self.security.require("configs", action):
            raise PermissionError(
                "Seu perfil não possui permissão para esta ação de configurações."
            )
        self.security.touch()
        return session.user.username

    def can(self, action: str) -> bool:
        session = getattr(self.security, "session", None)
        return bool(
            session is not None
            and not self.security.is_expired()
            and self.security.require("configs", action)
        )

    def load(self) -> SettingsSnapshot:
        username = self._require("view")
        key = UIPreferencesService.user_key(username)
        users = self.config.get("interface_usuarios", {})
        if not isinstance(users, Mapping):
            users = {}
        values = users.get(key)
        if not isinstance(values, Mapping):
            values = self.config.get("interface", {})
        preferences = UIPreferencesService.normalize(values)
        return SettingsSnapshot(
            username=key,
            preferences=deepcopy(preferences),
            backup_directories=tuple(self.backup_service.configured_directories()),
            daily_backup_enabled=(
                self.system_repository.get_config("backup_diario_ativo", "1") != "0"
            ),
        )

    def save_preferences(self, values: Mapping[str, Any]) -> SettingsSnapshot:
        username = self._require("edit")
        key = UIPreferencesService.user_key(username)
        normalized = UIPreferencesService.normalize(values)
        users = self.config.get("interface_usuarios", {})
        if not isinstance(users, dict):
            users = {}
        users = deepcopy(users)
        users[key] = normalized
        self.config.set("interface_usuarios", users)
        return self.load()

    def configure_backup(
        self, *, local_directory: str, cloud_directory: str = "", daily: bool
    ) -> SettingsSnapshot:
        self._require("edit")
        local = self._validated_directory(local_directory, required=True)
        cloud = self._validated_directory(cloud_directory, required=False)
        self.system_repository.set_configs({
            "pasta_backup_local": local,
            "pasta_backup_nuvem": cloud,
            "backup_diario_ativo": "1" if daily else "0",
        })
        return self.load()

    def create_backup(self):
        self._require("backup")
        result = self.backup_service.create_all("backup_manual")
        if not result.created:
            detail = "; ".join(result.errors) or "Nenhum destino de backup disponível."
            raise RuntimeError(detail)
        return result

    def run_diagnostics(self) -> tuple[dict, str]:
        self._require("diagnose")
        result = self.diagnostics.run(save_report=True)
        return result, self.diagnostics.format_report(result)

    @staticmethod
    def _validated_directory(value: str, *, required: bool) -> str:
        raw = str(value or "").strip()
        if not raw:
            if required:
                raise ValueError("A pasta principal de backup é obrigatória.")
            return ""
        path = Path(raw).expanduser()
        if not path.is_absolute():
            raise ValueError("Informe um caminho absoluto para o backup.")
        return str(path.resolve())
