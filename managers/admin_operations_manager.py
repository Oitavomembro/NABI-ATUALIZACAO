from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Any

from services.update_package_service import UpdatePackageService
from core.runtime_profile import DatabaseUsageLock


class AdminOperationsManager:
    """Lógica administrativa não visual extraída do legado."""

    def __init__(
        self,
        *,
        get_config: Callable[[str], Any],
        set_config: Callable[[str, Any], None],
        database_maintenance: Any,
        backup_dir: str,
        connect: Callable[[], Any],
        app_dir: str | None = None,
        install_dir: Callable[[], Any] | None = None,
        current_version: str | None = None,
    ) -> None:
        self.get_config = get_config
        self.set_config = set_config
        self.database_maintenance = database_maintenance
        self.backup_dir = Path(backup_dir)
        self.connect = connect
        self.app_dir = app_dir
        self.install_dir = install_dir
        self.current_version = current_version

    def license_status(self) -> tuple[str, bool]:
        validity = self.get_config("licenca_validade") or "não definida"
        blocked = self.get_config("licenca_bloqueada") == "1"
        return str(validity), blocked

    def renew_license(self, days: int, *, now: datetime | None = None) -> str:
        now = now or datetime.now()
        try:
            current = datetime.strptime(str(self.get_config("licenca_validade")), "%Y-%m-%d")
        except Exception:
            current = now
        new_date = (max(current, now) + timedelta(days=int(days))).strftime("%Y-%m-%d")
        self.set_config("licenca_validade", new_date)
        self.set_config("licenca_expira_em", "")
        self.set_config("licenca_bloqueada", "0")
        return new_date

    def activate_test_license(self, *, minutes: int = 1, now: datetime | None = None) -> datetime:
        limit = (now or datetime.now()) + timedelta(minutes=int(minutes))
        self.set_config("licenca_expira_em", limit.isoformat(timespec="seconds"))
        self.set_config("licenca_bloqueada", "0")
        return limit

    def toggle_license_block(self) -> bool:
        blocked = self.get_config("licenca_bloqueada") == "1"
        self.set_config("licenca_bloqueada", "0" if blocked else "1")
        return not blocked

    def run_database_action(self, action: str):
        if action == "integridade":
            return self.database_maintenance.check()
        if action == "reindex":
            return self.database_maintenance.reindex()
        if action == "vacuum":
            return self.database_maintenance.compact()
        report = self.database_maintenance.check()
        if report.foreign_key_errors:
            raise RuntimeError(
                "Foram encontradas inconsistências de chave estrangeira. "
                "Nenhuma correção automática foi aplicada para evitar perda de dados."
            )
        return self.database_maintenance.reindex()

    def create_backup(self):
        return self.database_maintenance.create_backup(prefix="backup_admin", validate=True)

    def restore_backup(self, source: str):
        return self.database_maintenance.restore(source)

    def cleanup_backups(self, keep: int = 10) -> int:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(
            (path for path in self.backup_dir.iterdir() if path.is_file() and path.suffix.lower() == ".db"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in files[keep:]:
            path.unlink()
        return min(keep, len(files))

    def log_migration(self, file_name: str, stage: str, status: str, details: str) -> None:
        conn = self.connect()
        try:
            conn.execute(
                "INSERT INTO log_migracao (data,arquivo,etapa,status,detalhes) VALUES (?,?,?,?,?)",
                (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), file_name, stage, status, details),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


    def update_service(self) -> UpdatePackageService:
        if not self.app_dir or not self.install_dir or not self.current_version:
            raise RuntimeError("Infraestrutura de atualização não configurada.")
        return UpdatePackageService(
            app_dir=self.app_dir,
            install_dir=self.install_dir(),
            current_version=self.current_version,
        )

    def validate_update_package(self, path: str):
        return self.update_service().validate(path)

    def prepare_update(self, path: str, manifest: dict, snapshot_id: str, *, executable: str, source_dir: str, frozen: bool, pid: int):
        service = self.update_service()
        state = service.prepare(path, manifest, snapshot_id)
        command = [str(Path(executable).resolve()), "--apply-update", "--state", str(service.state_file), "--pid", str(pid)]
        process_started_at = DatabaseUsageLock._process_started_at(pid)
        if process_started_at is not None:
            command.extend(["--process-started-at", repr(process_started_at)])
        if not frozen:
            command.insert(1, str(Path(source_dir) / "main.py"))
        return state, command, str(self.install_dir())

    def register_update_prepare_failure(self, manifest: dict | None, error: Exception) -> None:
        self.update_service().append_history(
            "FALHA_PREPARACAO",
            origem=self.current_version,
            destino=(manifest or {}).get("version"),
            erro=str(error),
        )

    def save_login_mode(self, enabled: bool) -> None:
        self.set_config("login_usuarios_habilitado", "1" if enabled else "0")
        self.set_config("login_usuarios_configurado", "1")
        self.set_config("login_inicio_consentido_v2440", "0")
        self.set_config("login_inicio_ativado_pelo_usuario_v2442", "1" if enabled else "0")
        self.set_config("login_politica_v2442_inicializada", "1")
