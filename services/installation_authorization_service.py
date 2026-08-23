from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import os
import time
import uuid
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping, Protocol

from services.windows_data_protector import WindowsDataProtectionError, WindowsDataProtector


class DataProtector(Protocol):
    def protect(self, data: bytes) -> bytes: ...

    def unprotect(self, data: bytes) -> bytes: ...


class MachineIdentificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstallationAuthorizationStatus:
    required: bool
    authorized: bool
    reason: str
    machine_code: str
    installation_id: str = ""
    activated_at: str = ""


def windows_machine_components() -> dict[str, str]:
    """Obtém identificadores Windows estáveis; os valores brutos nunca são persistidos."""
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
            system_drive,
            None,
            0,
            ctypes.byref(serial_number),
            None,
            None,
            None,
            0,
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


class InstallationAuthorizationService:
    """Autoriza uma instalação local antes da validação normal da licença.

    O fingerprint v1 é SHA-256 de MachineGuid e serial do volume do sistema,
    com rótulos e normalização. Somente o hash é gravado.
    """

    FORMAT_VERSION = 1
    PROFILE_PRODUCTION = "PRODUCAO"
    MAX_FAILED_ATTEMPTS = 5
    COOLDOWN_SECONDS = 30.0
    FILE_NAME = "installation_authorization_v1.dat"
    _FINGERPRINT_DOMAIN = b"NabiCode installation fingerprint v1\0"

    def __init__(
        self,
        *,
        profile: str,
        authorization_file: str | os.PathLike[str],
        protector: DataProtector,
        machine_components_provider: Callable[[], Mapping[str, str]] = windows_machine_components,
        now: Callable[[], datetime] = datetime.now,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.profile = str(profile or "").strip().upper()
        self.authorization_file = Path(authorization_file)
        self.protector = protector
        self.machine_components_provider = machine_components_provider
        self._now = now
        self._monotonic = monotonic
        self._failed_attempts = 0
        self._blocked_until = 0.0

    @classmethod
    def for_windows(
        cls,
        *,
        profile: str,
        app_dir: str | os.PathLike[str],
    ) -> "InstallationAuthorizationService":
        authorization_file = Path(app_dir) / "authorization" / cls.FILE_NAME
        protector = WindowsDataProtector(
            description="NabiCode Installation Authorization v1",
            machine_scope=True,
        )
        return cls(
            profile=profile,
            authorization_file=authorization_file,
            protector=protector,
        )

    @property
    def requires_authorization(self) -> bool:
        # Somente o perfil oficial TESTE tem bypass. Perfil ausente/desconhecido
        # falha fechado, como PRODUCAO.
        return self.profile != "TESTE"

    def _fingerprint(self) -> str:
        components = {
            str(name).strip().casefold(): str(value).strip().casefold()
            for name, value in self.machine_components_provider().items()
            if str(name).strip() and str(value).strip()
        }
        required = {"machine_guid", "system_volume_serial"}
        if not required.issubset(components):
            raise MachineIdentificationError("Fingerprint incompleto.")
        canonical = "\n".join(
            f"{name}={components[name]}" for name in sorted(required)
        ).encode("utf-8")
        return hashlib.sha256(self._FINGERPRINT_DOMAIN + canonical).hexdigest()

    @staticmethod
    def _friendly_code(fingerprint: str) -> str:
        prefix = str(fingerprint).upper()[:12]
        return f"NABI-{prefix[:4]}-{prefix[4:8]}-{prefix[8:12]}"

    def machine_code(self) -> str:
        try:
            return self._friendly_code(self._fingerprint())
        except Exception:
            # Provedor de identificação é uma fronteira de SO; a UI nunca deve
            # cair por uma falha de leitura e PRODUCAO continuará bloqueada.
            return "NABI-INDISPONIVEL"

    def evaluate(self) -> InstallationAuthorizationStatus:
        if not self.requires_authorization:
            return InstallationAuthorizationStatus(
                required=False,
                authorized=True,
                reason="PROFILE_BYPASS",
                machine_code=self.machine_code(),
            )

        try:
            fingerprint = self._fingerprint()
        except (MachineIdentificationError, OSError, ValueError):
            return InstallationAuthorizationStatus(
                required=True,
                authorized=False,
                reason="MACHINE_ID_UNAVAILABLE",
                machine_code="NABI-INDISPONIVEL",
            )

        machine_code = self._friendly_code(fingerprint)
        try:
            encrypted = self.authorization_file.read_bytes()
        except FileNotFoundError:
            return InstallationAuthorizationStatus(True, False, "MISSING", machine_code)
        except OSError:
            return InstallationAuthorizationStatus(True, False, "UNREADABLE", machine_code)

        try:
            raw = self.protector.unprotect(encrypted)
            record = json.loads(raw.decode("utf-8"))
            if not isinstance(record, dict):
                raise ValueError("Registro inválido.")
            if int(record.get("version", 0)) != self.FORMAT_VERSION:
                raise ValueError("Versão inválida.")
            if record.get("authorized") is not True:
                raise ValueError("Estado inválido.")
            installation_id = uuid.UUID(str(record["installation_id"])).hex
            activated_at = str(record["activated_at"])
            datetime.fromisoformat(activated_at)
            authorized_fingerprint = str(record["machine_fingerprint"])
        except (
            WindowsDataProtectionError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ):
            # DPAPI, JSON e validação estrutural falham de forma fechada.
            return InstallationAuthorizationStatus(True, False, "INVALID", machine_code)

        if not hmac.compare_digest(authorized_fingerprint, fingerprint):
            return InstallationAuthorizationStatus(True, False, "MACHINE_MISMATCH", machine_code)
        return InstallationAuthorizationStatus(
            required=True,
            authorized=True,
            reason="AUTHORIZED",
            machine_code=machine_code,
            installation_id=installation_id,
            activated_at=activated_at,
        )

    def authorize(
        self,
        password: str,
        password_verifier: Callable[[str], bool],
    ) -> bool:
        if not self.requires_authorization:
            return True
        current_time = self._monotonic()
        if current_time < self._blocked_until:
            return False
        if not password_verifier(str(password or "")):
            self._failed_attempts += 1
            if self._failed_attempts >= self.MAX_FAILED_ATTEMPTS:
                self._blocked_until = current_time + self.COOLDOWN_SECONDS
                self._failed_attempts = 0
            return False

        try:
            fingerprint = self._fingerprint()
            activated_at = self._now()
            if activated_at.tzinfo is None:
                activated_at = activated_at.astimezone()
            record = {
                "version": self.FORMAT_VERSION,
                "authorized": True,
                "installation_id": uuid.uuid4().hex,
                "machine_fingerprint": fingerprint,
                "activated_at": activated_at.isoformat(timespec="seconds"),
            }
            protected = self.protector.protect(
                json.dumps(record, ensure_ascii=True, sort_keys=True).encode("utf-8")
            )
            self.authorization_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.authorization_file.with_name(
                f".{self.authorization_file.name}.{uuid.uuid4().hex}.tmp"
            )
            try:
                temporary.write_bytes(protected)
                os.replace(temporary, self.authorization_file)
            finally:
                try:
                    temporary.unlink()
                except OSError:
                    pass
        except (
            MachineIdentificationError,
            WindowsDataProtectionError,
            OSError,
            ValueError,
            TypeError,
        ):
            return False

        self._failed_attempts = 0
        self._blocked_until = 0.0
        return self.evaluate().authorized

    def remove_authorization(
        self,
        password: str,
        password_verifier: Callable[[str], bool],
    ) -> bool:
        if not password_verifier(str(password or "")):
            return False
        try:
            self.authorization_file.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            return False
        return True
