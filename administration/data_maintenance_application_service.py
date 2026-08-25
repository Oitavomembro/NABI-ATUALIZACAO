from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from helpers.file_hashing import sha256_file
from services.backup_envelope import decrypt_database, inspect_envelope


@dataclass(frozen=True)
class PreparedRestore:
    request_file: str
    source_sha256: str
    safety_backup: str
    actor: str


class DataMaintenanceApplicationService:
    """Porta autenticada; nunca substitui nem abre o banco ativo para escrita."""

    def __init__(
        self, *, security, audit, migration, backup, database_path,
        backup_directory, staging_directory, connect, backup_database,
    ) -> None:
        self.security, self.audit = security, audit
        self.migration, self.backup = migration, backup
        self.database_path = Path(database_path).resolve()
        self.backup_directory = Path(backup_directory).resolve()
        self.staging_directory = Path(staging_directory).resolve()
        self.connect, self.backup_database = connect, backup_database

    def _require(self) -> str:
        session = self.security.current_session()
        if session is None or not self.security.require("technical", "view"):
            raise PermissionError("A manutenção de dados exige administrador autenticado.")
        if not self.security.require("configs", "backup"):
            raise PermissionError("A manutenção de dados exige permissão de backup.")
        return str(session.user.username)

    def preview_migration(self, package):
        self._require()
        return self.migration.preview(package)

    @staticmethod
    def migration_confirmation(preview) -> str:
        return f"IMPORTAR {preview.package_sha256[:12].upper()}"

    def execute_migration(self, package, *, categories, confirmation, remove_demo_customers=False):
        actor = self._require()
        preview = self.migration.preview(package)
        expected = self.migration_confirmation(preview)
        if not preview.ready or str(confirmation).strip() != expected:
            raise ValueError(f"Digite exatamente: {expected}")
        self.audit.record_event_strict(
            "technical", "MIGRACAO_INICIADA", object_id=preview.package_sha256[:16],
            details=f"categorias={','.join(categories)}", user=actor,
        )
        try:
            result = self.migration.execute(
                package, database_path=self.database_path,
                backup_dir=self.backup_directory, connect=self.connect,
                backup_database=self.backup_database, categories=tuple(categories),
                remove_demo_customers=bool(remove_demo_customers),
            )
        except Exception:
            self.audit.record_event_strict(
                "technical", "MIGRACAO_FALHOU", object_id=preview.package_sha256[:16],
                details="transacao_revertida", result="FALHA", user=actor,
            )
            raise
        self.audit.record_event_strict(
            "technical", "MIGRACAO_CONCLUIDA", object_id=preview.package_sha256[:16],
            details=f"backup={Path(result.backup).name}", user=actor,
        )
        return result

    def verify_backup(self, source, *, password=""):
        self._require()
        return self.backup.verify_restore_in_temporary(source, password or None)

    @staticmethod
    def restore_confirmation(source_sha256: str) -> str:
        return f"PREPARAR {source_sha256[:12].upper()}"

    def prepare_restore(self, source, *, confirmation, password="") -> PreparedRestore:
        """Valida e prepara; um helper oficial ainda deve aplicar após o encerramento."""
        actor = self._require()
        source_path = Path(source).expanduser().resolve()
        verification = self.backup.verify_restore_in_temporary(source_path, password or None)
        expected = self.restore_confirmation(str(verification.sha256))
        if str(confirmation).strip() != expected:
            raise ValueError(f"Digite exatamente: {expected}")
        self.staging_directory.mkdir(parents=True, exist_ok=True)
        self.backup_directory.mkdir(parents=True, exist_ok=True)
        operation = self.staging_directory / f"restore_{uuid.uuid4().hex}"
        operation.mkdir(mode=0o700)
        staged = operation / "database.staged.db"
        try:
            info = inspect_envelope(source_path)
            if info.encrypted:
                if not password:
                    raise ValueError("Informe a senha do backup criptografado.")
                decrypt_database(source_path, staged, password)
            else:
                self.backup_database(source_path, staged)
            os.chmod(staged, 0o600)
            self.backup.verify_restore_in_temporary(staged)
            safety = Path(self.backup.create(
                self.backup_directory, "antes_restauracao_preparada"
            )).resolve()
            if not safety.is_file() or safety.stat().st_size <= 0:
                raise RuntimeError("O pré-backup obrigatório não foi criado.")
            request = operation / "restore-request.json"
            payload = {
                "schema": "nabicode.restore-request.v1",
                "request_id": operation.name,
                "actor": actor,
                "profile_database_name": self.database_path.name,
                "active_database_sha256": sha256_file(self.database_path),
                "staged_file": staged.name,
                "staged_sha256": sha256_file(staged),
                "source_sha256": str(verification.sha256),
                "safety_backup": str(safety),
                "status": "AGUARDANDO_HELPER_OFICIAL",
            }
            temporary = request.with_suffix(".tmp")
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, request)
            self.audit.record_event_strict(
                "technical", "RESTAURACAO_PREPARADA", object_id=operation.name,
                details=f"origem={verification.sha256[:16]};prebackup={safety.name}",
                user=actor,
            )
            return PreparedRestore(str(request), str(verification.sha256), str(safety), actor)
        except Exception:
            shutil.rmtree(operation, ignore_errors=True)
            raise

