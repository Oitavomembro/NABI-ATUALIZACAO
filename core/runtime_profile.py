from __future__ import annotations

import atexit
import json
import os
import socket
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

VALID_PROFILES = {"PRODUCAO", "TESTE"}
_IS_WINDOWS = os.name == "nt"


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resolve_profile_marker(runtime_dir: str | os.PathLike[str] | None = None) -> tuple[str, Path]:
    """Lê o marcador físico do artefato sem configurar AppData ou ambiente.

    Esta função é deliberadamente somente leitura. Ela não aceita o perfil da
    variável de ambiente como evidência, não cria diretórios e não aplica valor
    padrão: marcador ausente ou inválido é uma falha real do artefato.
    """

    root = Path(runtime_dir).resolve() if runtime_dir is not None else Path(
        getattr(sys, "_MEIPASS", _runtime_root())
    ).resolve()
    marker = root / "PERFIL_NABICODE.txt"
    try:
        profile = marker.read_text(encoding="utf-8-sig").strip().upper()
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"Marcador de perfil indisponível: {marker}") from exc
    if profile not in VALID_PROFILES:
        raise RuntimeError(f"Marcador de perfil inválido: {profile!r}")
    return profile, marker


def load_packaged_profile(default: str = "PRODUCAO") -> str:
    profile = os.environ.get("NABICODE_PROFILE", "").strip().upper()
    if not profile:
        marker = _runtime_root() / "PERFIL_NABICODE.txt"
        if marker.exists():
            profile = marker.read_text(encoding="utf-8").strip().upper()
    if profile not in VALID_PROFILES:
        profile = default
    return profile


def configure_profile_environment(default: str = "PRODUCAO") -> "RuntimeProfile":
    profile = load_packaged_profile(default)
    base = Path(os.environ.get("APPDATA") or Path.home()) / "NabiCode"
    app_dir = base / ("Producao" if profile == "PRODUCAO" else "Teste")
    app_dir.mkdir(parents=True, exist_ok=True)
    os.environ["NABICODE_PROFILE"] = profile
    os.environ["NABICODE_APP_DIR"] = str(app_dir)
    return RuntimeProfile(profile=profile, app_dir=app_dir)


@dataclass(frozen=True)
class RuntimeProfile:
    profile: str
    app_dir: Path

    @property
    def paths(self) -> "RuntimePaths":
        return RuntimePaths(self.app_dir)

    @property
    def label(self) -> str:
        return "PRODUÇÃO" if self.profile == "PRODUCAO" else "TESTE"

    def validate_database(self, database_path: str | os.PathLike[str]) -> Path:
        db = Path(database_path).expanduser().resolve()
        normalized = str(db).replace("\\", "/").lower()
        if self.profile == "TESTE" and "/nabicode/producao/" in normalized:
            raise RuntimeError("A versão de TESTE tentou abrir o banco de PRODUÇÃO.")
        if self.profile == "PRODUCAO" and "/nabicode/teste/" in normalized:
            raise RuntimeError("A versão de PRODUÇÃO tentou abrir o banco de TESTE.")

        marker = db.with_suffix(db.suffix + ".profile.json")
        if marker.exists():
            try:
                data = json.loads(marker.read_text(encoding="utf-8"))
                marked = str(data.get("profile", "")).strip().upper()
            except Exception as exc:
                raise RuntimeError(f"Marcador de perfil do banco inválido: {marker}") from exc
            if marked in VALID_PROFILES and marked != self.profile:
                raise RuntimeError(
                    f"Banco marcado como {marked}, mas a aplicação está em {self.profile}."
                )
        else:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                json.dumps(
                    {
                        "profile": self.profile,
                        "database": str(db),
                        "created_by": "NabiCode",
                    },
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )
        return db


@dataclass(frozen=True)
class RuntimePaths:
    """Caminhos mutáveis isolados do diretório imutável do programa."""

    app_dir: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "app_dir", Path(self.app_dir).expanduser().resolve())

    @property
    def database(self) -> Path:
        return self.app_dir / "fichario_moveis.db"

    @property
    def backups(self) -> Path:
        return self.app_dir / "backups_moveis"

    @property
    def pdfs(self) -> Path:
        return self.app_dir / "pdf_cupons_moveis"

    @property
    def reports(self) -> Path:
        return self.app_dir / "relatorios"

    @property
    def logs(self) -> Path:
        return self.app_dir / "logs"

    @property
    def config(self) -> Path:
        return self.app_dir / "config"

    @property
    def diagnostics(self) -> Path:
        return self.app_dir / "diagnosticos"

    @property
    def rollback(self) -> Path:
        return self.app_dir / "rollback"

    @property
    def releases(self) -> Path:
        return self.app_dir / "releases"

    @property
    def updates(self) -> Path:
        return self.app_dir / "atualizacoes"

    @property
    def fiscal(self) -> Path:
        return self.app_dir / "fiscal"

    def mutable_directories(self) -> tuple[Path, ...]:
        return (
            self.backups,
            self.pdfs,
            self.reports,
            self.logs,
            self.config,
            self.diagnostics,
            self.rollback,
            self.releases,
            self.updates,
            self.fiscal,
        )


class DatabaseInUseError(RuntimeError):
    """Conflito esperado de instância; deve ser exibido sem traceback ao usuário."""

    def __init__(self, database_path: Path, requested_profile: str, owner_profile: str) -> None:
        self.database_path = Path(database_path)
        self.requested_profile = requested_profile
        self.owner_profile = owner_profile
        super().__init__(
            "Este banco já está em uso por outra instância do NabiCode "
            f"({owner_profile}). Feche a outra instância ou use outro banco."
        )


class DatabaseUsageLock:
    def __init__(self, database_path: str | os.PathLike[str], profile: str) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.profile = profile
        self.lock_path = self.database_path.with_suffix(self.database_path.suffix + ".nabicode.lock")
        self._owned = False
        self._owner_token = uuid.uuid4().hex

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if _IS_WINDOWS:
            return DatabaseUsageLock._windows_pid_alive(pid)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    @staticmethod
    def _windows_pid_alive(pid: int) -> bool:
        """Consulta um PID no Windows sem enviar sinais ao processo alvo."""
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        still_active = 259
        error_invalid_parameter = 87

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE

        get_exit_code_process = kernel32.GetExitCodeProcess
        get_exit_code_process.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit_code_process.restype = wintypes.BOOL

        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        handle = open_process(process_query_limited_information, False, pid)
        if not handle:
            # PID inexistente retorna ERROR_INVALID_PARAMETER. Falhas de acesso
            # são tratadas de forma conservadora como processo ativo para nunca
            # remover o lock pertencente a outra instância.
            return ctypes.get_last_error() != error_invalid_parameter

        exit_code = wintypes.DWORD()
        try:
            if not get_exit_code_process(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == still_active
        finally:
            close_handle(handle)

    @staticmethod
    def _process_started_at(pid: int) -> float | None:
        """Retorna a criação do processo para distinguir PID ativo reutilizado."""

        if pid <= 0:
            return None
        if _IS_WINDOWS:
            return DatabaseUsageLock._windows_process_started_at(pid)
        try:
            stat_fields = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8").split()
            start_ticks = int(stat_fields[21])
            clock_ticks = int(os.sysconf("SC_CLK_TCK"))
            boot_line = next(
                line for line in Path("/proc/stat").read_text(encoding="utf-8").splitlines()
                if line.startswith("btime ")
            )
            boot_time = int(boot_line.split()[1])
            return boot_time + start_ticks / clock_ticks
        except (OSError, ValueError, IndexError, StopIteration):
            return None

    @staticmethod
    def _windows_process_started_at(pid: int) -> float | None:
        import ctypes
        from ctypes import wintypes

        process_query_limited_information = 0x1000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return None
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        try:
            if not kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            ):
                return None
            filetime = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            return filetime / 10_000_000.0 - 11_644_473_600.0
        finally:
            kernel32.CloseHandle(handle)

    def _owner_is_current_process(self, current: dict) -> bool:
        """Valida PID e instante de criação, mantendo hosts remotos conservadores."""

        if current.get("host") != socket.gethostname():
            return True
        try:
            pid = int(current.get("pid") or 0)
        except (TypeError, ValueError):
            return True
        if not self._pid_alive(pid):
            return False
        actual_start = self._process_started_at(pid)
        recorded_start = current.get("process_started_at")
        if actual_start is not None and isinstance(recorded_start, (int, float)):
            return abs(actual_start - float(recorded_start)) <= 2.0
        if actual_start is not None and recorded_start is None:
            try:
                return actual_start <= self.lock_path.stat().st_mtime + 1.0
            except OSError:
                return True
        return True

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "profile": self.profile,
            "database": str(self.database_path),
            "owner_token": self._owner_token,
            "process_started_at": self._process_started_at(os.getpid()),
        }
        while True:
            try:
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    current = json.loads(self.lock_path.read_text(encoding="utf-8"))
                except Exception:
                    current = {}
                if not self._owner_is_current_process(current):
                    try:
                        self.lock_path.unlink()
                    except OSError:
                        pass
                    continue
                owner = current.get("profile") or "outra instância"
                raise DatabaseInUseError(self.database_path, self.profile, owner)
            else:
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(payload, handle, ensure_ascii=False, indent=2)
                        handle.write("\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                except Exception:
                    try:
                        self.lock_path.unlink()
                    except OSError:
                        pass
                    raise
                self._owned = True
                atexit.register(self.release)
                return

    def release(self) -> None:
        if not self._owned:
            return
        try:
            current = json.loads(self.lock_path.read_text(encoding="utf-8"))
        except Exception:
            current = {}
        if current.get("owner_token") == self._owner_token:
            for attempt in range(10):
                try:
                    self.lock_path.unlink()
                    break
                except FileNotFoundError:
                    break
                except PermissionError:
                    if not _IS_WINDOWS or attempt == 9:
                        raise
                    time.sleep(0.01)
        self._owned = False
        atexit.unregister(self.release)
