from __future__ import annotations

import hashlib
import ctypes
import os
from ctypes import wintypes
from typing import Callable, Mapping


_DOMAIN = b"NabiCode license machine fingerprint v2\0"


class MachineIdentificationError(RuntimeError):
    pass


def windows_machine_components() -> dict[str, str]:
    """Obtém identificadores Windows estáveis sem persistir valores brutos."""
    if os.name != "nt":
        raise MachineIdentificationError("A identificação da instalação exige Windows.")

    try:
        import winreg

        access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            access,
        ) as key:
            machine_guid = str(winreg.QueryValueEx(key, "MachineGuid")[0]).strip()
    except (OSError, ValueError, TypeError) as exc:
        raise MachineIdentificationError("MachineGuid do Windows indisponível.") from exc

    system_drive = str(os.environ.get("SystemDrive") or "C:").rstrip("\\/") + "\\"
    serial_number = wintypes.DWORD()
    try:
        get_volume_information = ctypes.windll.kernel32.GetVolumeInformationW
        get_volume_information.argtypes = (
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPWSTR,
            wintypes.DWORD,
        )
        get_volume_information.restype = wintypes.BOOL
        ok = get_volume_information(
            system_drive, None, 0, ctypes.byref(serial_number), None, None, None, 0
        )
    except (AttributeError, OSError) as exc:
        raise MachineIdentificationError("Volume do sistema Windows indisponível.") from exc
    if not ok:
        raise MachineIdentificationError("Serial do volume do sistema indisponível.")
    if not machine_guid:
        raise MachineIdentificationError("Identificadores obrigatórios da máquina indisponíveis.")
    return {
        "machine_guid": machine_guid,
        "system_volume_serial": f"{serial_number.value:08X}",
    }


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
