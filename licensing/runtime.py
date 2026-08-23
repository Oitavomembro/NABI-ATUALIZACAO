from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

from services.windows_data_protector import WindowsDataProtector

from .gate import Capability, LicenseGate
from .machine import machine_fingerprint
from .service import LicenseV2Service
from .storage import ProtectedStateStore


PUBLIC_KEY_FILE = "trusted_public_keys.json"


def runtime_license_directory(app_dir: str | Path) -> Path:
    return Path(app_dir).expanduser().resolve() / "licensing_v2"


def trusted_key_path() -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidate = root / "licensing" / PUBLIC_KEY_FILE if hasattr(sys, "_MEIPASS") else root / PUBLIC_KEY_FILE
    return candidate


def load_trusted_public_keys(path: str | Path | None = None) -> dict[str, bytes]:
    source = Path(path) if path is not None else trusted_key_path()
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(value, dict) or set(value) != {"schema", "keys"} or value["schema"] != 1:
        return {}
    keys = value["keys"]
    if not isinstance(keys, dict):
        return {}
    decoded: dict[str, bytes] = {}
    try:
        for key_id, encoded in keys.items():
            if not str(key_id).strip() or not isinstance(encoded, str):
                return {}
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) != 32:
                return {}
            decoded[str(key_id)] = raw
    except (ValueError, TypeError):
        return {}
    return decoded


def build_runtime_license_service(
    app_dir: str | Path, *, public_key_path: str | Path | None = None
) -> LicenseV2Service:
    directory = runtime_license_directory(app_dir)
    protector = WindowsDataProtector(
        description="NabiCode License State v2", machine_scope=True
    )
    return LicenseV2Service(
        license_path=directory / "current.nabilic",
        state_store=ProtectedStateStore(directory / "license_state_v2.dat", protector),
        public_keys=load_trusted_public_keys(public_key_path),
        machine_fingerprint=machine_fingerprint,
    )


def evaluate_runtime_gate(app_dir: str | Path) -> LicenseGate:
    return LicenseGate(build_runtime_license_service(app_dir).evaluate())


def startup_block_message(gate: LicenseGate, capability: Capability) -> str:
    decision = gate.decision
    return (
        f"Licença NabiCode V2: {decision.state.value}.\n\n"
        f"Motivo: {decision.reason}\n"
        f"Código desta máquina: {decision.machine_code}\n\n"
        f"A operação '{capability.value}' está bloqueada. Permanecem disponíveis "
        "ativação, diagnóstico mínimo, backup e exportação segura."
    )
