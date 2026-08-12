from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from database import DatabaseMaintenanceService
from services.developer_tools import DeveloperToolsService


@dataclass(frozen=True)
class CommandOutput:
    exit_code: int
    text: str


class DeveloperToolsController:
    def __init__(self, project_dir: str | Path) -> None:
        self.project_dir = Path(project_dir).resolve()

    def execute(self, action: str, *, database_name: str = "fichario_moveis.db") -> CommandOutput:
        database = self.project_dir / database_name
        service = DeveloperToolsService(self.project_dir, database)
        if action == "validate":
            result = service.validate_tooling()
            return CommandOutput(0 if result["ok"] else 2, json.dumps(result, ensure_ascii=False, indent=2))
        if action == "tests":
            result = service.run_tests()
            return CommandOutput(result.returncode, result.stdout + result.stderr)
        if action == "clean":
            return CommandOutput(0, "\n".join(service.clean_build()) or "Nenhum artefato encontrado.")
        if action == "versions":
            return CommandOutput(0, json.dumps(service.runtime_versions(), ensure_ascii=False, indent=2))
        if action != "backup":
            raise ValueError(f"Ação desconhecida: {action}.")
        if not database.is_file():
            raise FileNotFoundError(f"Banco não encontrado: {database}")
        maintenance = DatabaseMaintenanceService(database, self.project_dir / "backups_moveis")
        backup, report = maintenance.create_backup(prefix="backup_manual", validate=True)
        return CommandOutput(0, f"{backup}\nIntegridade: {report.integrity}")
