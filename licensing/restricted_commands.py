from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from services.backup_service import BackupService

from .gate import Capability, LicenseGate
from .runtime import build_runtime_license_service


RESTRICTED_FLAGS = {
    "--license-status", "--activate-license", "--restricted-backup", "--safe-export",
}


def _decision_data(decision) -> dict:
    payload = decision.payload
    return {
        "state": decision.state.value, "reason": decision.reason,
        "machine_code": decision.machine_code,
        "license_id": payload.license_id if payload else "",
        "edition": payload.edition.value if payload else "",
        "valid_until": payload.valid_until.isoformat() if payload else "",
        "grace_days_remaining": decision.grace_days_remaining,
    }


def handle_restricted_command(
    argv: list[str], profile, *, service_factory=build_runtime_license_service,
    backup_factory=BackupService,
) -> int | None:
    selected = next((flag for flag in RESTRICTED_FLAGS if flag in argv), None)
    if selected is None:
        return None
    service = service_factory(profile.app_dir)
    gate = LicenseGate(service.evaluate())
    if selected == "--license-status":
        gate.require(Capability.DIAGNOSTIC)
        print(json.dumps(_decision_data(gate.decision), ensure_ascii=False, sort_keys=True))
        return 0 if gate.decision.operational else 3
    try:
        value = argv[argv.index(selected) + 1]
    except IndexError as exc:
        raise ValueError(f"Informe o caminho após {selected}.") from exc
    if selected == "--activate-license":
        gate.require(Capability.ACTIVATE)
        decision = service.activate(Path(value).expanduser().resolve())
        print(json.dumps(_decision_data(decision), ensure_ascii=False, sort_keys=True))
        return 0 if decision.operational else 3
    capability = Capability.BACKUP if selected == "--restricted-backup" else Capability.EXPORT
    gate.require(capability)
    database = profile.validate_database(profile.paths.database)
    destination = Path(value).expanduser().resolve()
    backup = backup_factory(
        database_path=database, default_directory=profile.paths.backups,
        get_config=lambda _key: "", set_config=lambda _key, _value: None,
    ).create(destination, prefix="exportacao_segura" if capability is Capability.EXPORT else "backup_modo_restrito")
    print(json.dumps({
        "created": backup, "operation": capability.value,
        "at": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, sort_keys=True))
    return 0
