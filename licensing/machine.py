from __future__ import annotations

import hashlib
from typing import Callable, Mapping

from services.installation_authorization_service import windows_machine_components


_DOMAIN = b"NabiCode license machine fingerprint v2\0"


def machine_fingerprint(
    provider: Callable[[], Mapping[str, str]] = windows_machine_components,
) -> str:
    components = {
        str(key).strip().casefold(): str(value).strip().casefold()
        for key, value in provider().items()
        if str(key).strip() and str(value).strip()
    }
    required = {"machine_guid", "system_volume_serial"}
    if not required.issubset(components):
        raise RuntimeError("Identificação segura da máquina indisponível.")
    canonical = "\n".join(f"{key}={components[key]}" for key in sorted(required)).encode()
    return hashlib.sha256(_DOMAIN + canonical).hexdigest()


def machine_code(fingerprint: str) -> str:
    value = str(fingerprint).upper()
    return f"NABI2-{value[:4]}-{value[4:8]}-{value[8:12]}-{value[12:16]}"
