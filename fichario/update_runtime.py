from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from core.runtime_profile import DatabaseUsageLock
from database.maintenance import DatabaseMaintenanceService
from services.update_package_service import UpdatePackageService


class FicharioUpdateRuntime:
    def __init__(self, profile, database_path: Path) -> None:
        self.profile = profile
        self.database_path = Path(database_path).resolve()
        self.install_dir = (
            Path(sys.executable).resolve().parent
            if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
        )
        self.version = self._read_text("VERSAO.txt", "0.0.0")
        self.package_service = UpdatePackageService(
            app_dir=profile.app_dir, install_dir=self.install_dir,
            current_version=self.version,
        )

    def _read_text(self, name: str, default: str) -> str:
        for path in (self.install_dir / name, self.install_dir / "_internal" / name):
            try:
                return path.read_text(encoding="utf-8-sig").strip()
            except OSError:
                continue
        return default

    def maintenance(self) -> DatabaseMaintenanceService:
        return DatabaseMaintenanceService(
            self.database_path, self.profile.paths.backups,
            expected_schema_version=21,
            required_tables=(
                "clientes", "movimentacoes", "parcelas", "configuracoes",
                "historico_clientes",
            ),
        )

    def prepare(self, package_path: str | Path) -> tuple[dict, dict, Path]:
        manifest = self.package_service.validate(package_path)
        backup, report = self.maintenance().create_backup(prefix="antes_atualizacao")
        if not report.valid:
            raise RuntimeError("O backup anterior à atualização não foi aprovado.")
        state = self.package_service.prepare(package_path, manifest, str(backup))
        return manifest, state, backup

    def launch_helper(self, state: dict, *, rollback: bool = False) -> None:
        pid = os.getpid()
        started = DatabaseUsageLock._process_started_at(pid)
        if getattr(sys, "frozen", False):
            helper = self.install_dir / "NabiCode_Fichario_Updater.exe"
            if not helper.is_file():
                raise FileNotFoundError("Atualizador externo não foi instalado.")
            command = [str(helper)]
            launcher = str(Path(sys.executable).resolve())
            source_main = None
        else:
            helper = self.install_dir / "build_tools" / "fichario_update_helper.py"
            command = [str(Path(sys.executable).resolve()), str(helper)]
            launcher = str(Path(sys.executable).resolve())
            source_main = str(self.install_dir / "main_fichario_qt.py")
        command.extend([
            "--state", str(self.package_service.state_file), "--pid", str(pid),
            "--launcher", launcher,
        ])
        if rollback: command.append("--rollback")
        if source_main: command.extend(["--source-main", source_main])
        if started is not None: command.extend(["--process-started-at", repr(started)])
        subprocess.Popen(command, cwd=str(self.install_dir))

    def validate_after_restart(self) -> dict | None:
        state = self.package_service.load_state()
        if not state or state.get("status") != "ARQUIVOS_APLICADOS":
            return None
        try:
            loaded_version = self._read_text("VERSAO.txt", "0.0.0")
            loaded_revision = int(self._read_text("REVISAO.txt", "0") or 0)
            if loaded_version != str(state.get("target_version")):
                raise RuntimeError("A versão carregada diverge do pacote aplicado.")
            if loaded_revision != int(state.get("target_revision") or 0):
                raise RuntimeError("A revisão carregada diverge do pacote aplicado.")
            errors = self.package_service.validate_installed_files(state)
            if errors: raise RuntimeError("; ".join(errors))
            report = self.maintenance().check()
            if not report.valid: raise RuntimeError("O banco não passou na validação pós-atualização.")
            evidence = {
                "versao": loaded_version, "revisao": loaded_revision,
                "arquivos": len(state.get("manifest", {}).get("files", [])),
                "banco_preservado": True,
            }
            self.package_service.mark_success(state, evidence)
            return {"ok": True, "report": evidence}
        except Exception as error:
            restored = False
            try:
                snapshot = state.get("snapshot_id")
                if snapshot: self.maintenance().restore(snapshot)
                restored = True
            finally:
                pending = dict(state)
                pending.update(status="ROLLBACK_PENDENTE", error=str(error), banco_restaurado=restored)
                self.package_service.atomic_json(self.package_service.state_file, pending)
            self.launch_helper(pending, rollback=True)
            return {
                "ok": False, "error": str(error), "rolled_back": restored,
                "restart_required": True,
            }
