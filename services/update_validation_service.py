from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class UpdateValidationService:
    """Valida atualização aplicada e coordena rollback de arquivos e banco."""

    package_service: object
    diagnostics_factory: Callable[[], object]
    restore_snapshot: Callable[[str], object]
    app_version: str

    def validate_after_restart(self):
        state = self.package_service.load_state()
        if not state or state.get("status") != "ARQUIVOS_APLICADOS":
            return None
        try:
            if str(state.get("target_version")) != self.app_version:
                raise RuntimeError(
                    f"Versão carregada {self.app_version} difere do pacote {state.get('target_version')}."
                )
            target_revision = int(state.get("target_revision") or 0)
            loaded_revision = int(getattr(self.package_service, "current_revision", 0) or 0)
            if target_revision != loaded_revision:
                raise RuntimeError(
                    f"Revisão carregada R{loaded_revision} difere do pacote R{target_revision}."
                )
            file_errors = self.package_service.validate_installed_files(state)
            if file_errors:
                raise RuntimeError("; ".join(file_errors))
            diagnostic = self.diagnostics_factory().run(save_report=True)
            if not diagnostic.get("aprovado"):
                failures = [
                    item.get("name", "Verificação") + ": " + item.get("detail", "")
                    for item in diagnostic.get("checks", [])
                    if not item.get("ok") and item.get("severity") != "warning"
                ]
                raise RuntimeError("Diagnóstico reprovado: " + "; ".join(failures))
            report = {
                "versao": self.app_version,
                "revisao": loaded_revision,
                "arquivos": len(state.get("manifest", {}).get("files", [])),
                "diagnostico": diagnostic.get("arquivo"),
                "banco_preservado": True,
            }
            self.package_service.mark_success(state, report)
            return {"ok": True, "state": state, "report": report}
        except Exception as exc:
            rolled_back = False
            try:
                self.package_service.restore_files(state)
                snapshot_id = state.get("snapshot_id")
                if snapshot_id:
                    self.restore_snapshot(snapshot_id)
                rolled_back = True
            finally:
                self.package_service.mark_failure(state, str(exc), rolled_back=rolled_back)
            return {"ok": False, "state": state, "error": str(exc), "rolled_back": rolled_back}
