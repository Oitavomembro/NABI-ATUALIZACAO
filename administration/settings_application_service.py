from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from core.config_manager import ConfigManager
from services.ui_preferences import UIPreferencesService
from services.printing_service import PrintingService
from services.receipt_template_service import ReceiptTemplateService


@dataclass(frozen=True, slots=True)
class SettingsSnapshot:
    username: str
    preferences: Mapping[str, Any]
    backup_directories: tuple[str, ...]
    daily_backup_enabled: bool


@dataclass(frozen=True, slots=True)
class PrintingSettingsSnapshot:
    printers: tuple[str, ...]
    values: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class StoreIdentitySnapshot:
    name: str
    receipt_footer: str


@dataclass(frozen=True, slots=True)
class BackupPackageResult:
    path: str
    filename: str
    backup_format: str
    encrypted: bool
    sha256: str
    schema_version: int


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
        printing_service=None,
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
        self.printing_service = printing_service or PrintingService(
            self.system_repository.get_config
        )

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

    def create_backup_package(
        self, *, directory: str | Path, encrypted: bool, password: str = ""
    ) -> BackupPackageResult:
        self._require("backup")
        destination = self._validated_directory(str(directory), required=True)
        created = ""
        try:
            if encrypted:
                created = self.backup_service.create_encrypted(
                    destination, password, "backup_manual_protegido"
                )
                verification = self.backup_service.verify_restore_in_temporary(
                    created, password
                )
            else:
                created = self.backup_service.create(destination, "backup_manual_legado")
                verification = self.backup_service.verify_restore_in_temporary(created)
        except Exception:
            if created:
                Path(created).unlink(missing_ok=True)
            raise
        return BackupPackageResult(
            path=str(created),
            filename=Path(created).name,
            backup_format=str(verification.backup_format),
            encrypted=bool(verification.encrypted),
            sha256=str(verification.sha256),
            schema_version=int(verification.schema_version),
        )

    def verify_backup_package(
        self, *, backup_path: str | Path, password: str = ""
    ):
        self._require("backup")
        return self.backup_service.verify_restore_in_temporary(
            backup_path, password or None
        )

    def verify_backup_restore(self, backup_path: str | Path):
        """Verifica restauração em TEMP; não oferece mutação do banco ativo."""
        self._require("backup")
        return self.backup_service.verify_restore_in_temporary(backup_path)

    def run_diagnostics(self) -> tuple[dict, str]:
        self._require("diagnose")
        result = self.diagnostics.run(save_report=True)
        return result, self.diagnostics.format_report(result)

    def load_printing(self) -> PrintingSettingsSnapshot:
        self._require("view")
        values = {}
        for category, default_format in PrintingService.DEFAULT_FORMATS.items():
            printer_key = "impressora_historico" if category == "fechamento" else f"impressora_{category}"
            values[printer_key] = self.system_repository.get_config(printer_key, "Padrão do Sistema") or "Padrão do Sistema"
            values[f"formato_impressao_{category}"] = PrintingService.normalize_output_format(
                self.system_repository.get_config(f"formato_impressao_{category}", default_format),
                default_format,
            )
        defaults = {
            "modelo_cupom_visual": ReceiptTemplateService.DEFAULT,
            "impressao_fonte": "Helvetica", "impressao_fonte_tamanho": "10",
            "impressao_corte_automatico": "1", "impressao_tipo_corte": "PARCIAL",
            "impressao_linhas_antes_corte": "4",
        }
        for key, default in defaults.items():
            values[key] = self.system_repository.get_config(key, default) or default
        return PrintingSettingsSnapshot(tuple(self.printing_service.list_printers()), values)

    def save_printing(self, values: Mapping[str, object]) -> PrintingSettingsSnapshot:
        self._require("edit")
        allowed = {"modelo_cupom_visual", "impressao_fonte", "impressao_fonte_tamanho", "impressao_corte_automatico", "impressao_tipo_corte", "impressao_linhas_antes_corte"}
        for category in PrintingService.DEFAULT_FORMATS:
            allowed.add("impressora_historico" if category == "fechamento" else f"impressora_{category}")
            allowed.add(f"formato_impressao_{category}")
        unknown = set(values) - allowed
        if unknown: raise ValueError("Configuração de impressão desconhecida.")
        normalized = {key: str(value).strip() for key, value in values.items()}
        if normalized.get("modelo_cupom_visual") not in ReceiptTemplateService.names(): raise ValueError("Modelo visual inválido.")
        if normalized.get("impressao_fonte") not in {"Helvetica", "Times-Roman", "Courier"}: raise ValueError("Fonte inválida.")
        size = int(normalized.get("impressao_fonte_tamanho", "10")); normalized["impressao_fonte_tamanho"] = str(max(6, min(24, size)))
        lines = int(normalized.get("impressao_linhas_antes_corte", "4")); normalized["impressao_linhas_antes_corte"] = str(max(0, min(12, lines)))
        if normalized.get("impressao_tipo_corte") not in {"PARCIAL", "TOTAL"}: raise ValueError("Tipo de corte inválido.")
        for category, default_format in PrintingService.DEFAULT_FORMATS.items():
            key = f"formato_impressao_{category}"
            if key in normalized:
                normalized[key] = PrintingService.normalize_output_format(
                    normalized[key], default_format
                )
        self.system_repository.set_configs(normalized)
        return self.load_printing()

    def preview_receipt(self, model: str) -> str:
        self._require("view")
        sample = "NabiCode\nCOMPROVANTE DE TESTE\n" + "=" * 42 + "\n1x Produto de demonstração\nTOTAL: R$ 100,00"
        return ReceiptTemplateService.render(sample, model)

    def load_store_identity(self) -> StoreIdentitySnapshot:
        self._require("view")
        return StoreIdentitySnapshot(
            name=self.system_repository.get_config(
                "nome_loja", "NabiCode — Gerenciador de Crediário"
            ).strip(),
            receipt_footer=self.system_repository.get_config(
                "rodape_cupom", "Guarde este comprovante.\nObrigado pela preferência!"
            ).strip(),
        )

    def save_store_identity(self, *, name: str, receipt_footer: str) -> StoreIdentitySnapshot:
        self._require("edit")
        clean_name = self._clean_text(name, field="O nome da loja", maximum=120, multiline=False)
        clean_footer = self._clean_text(
            receipt_footer, field="O rodapé do comprovante", maximum=500, multiline=True
        )
        self.system_repository.set_configs(
            {"nome_loja": clean_name, "rodape_cupom": clean_footer}
        )
        return self.load_store_identity()

    @staticmethod
    def _clean_text(value: str, *, field: str, maximum: int, multiline: bool) -> str:
        text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not multiline: text = " ".join(text.split())
        if not text: raise ValueError(f"{field} é obrigatório.")
        if len(text) > maximum: raise ValueError(f"{field} deve possuir no máximo {maximum} caracteres.")
        if any(ord(char) < 32 and char != "\n" for char in text):
            raise ValueError(f"{field} contém caracteres de controle inválidos.")
        return text

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
