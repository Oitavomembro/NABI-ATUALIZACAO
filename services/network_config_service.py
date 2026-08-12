from __future__ import annotations

import json
import os
import socket
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from database.sqlite_connection import connection_session


@dataclass(frozen=True)
class NetworkPaths:
    app_dir: Path
    config_file: Path
    installation_file: Path
    local_db: Path
    server_dir: Path
    server_db: Path


class NetworkConfigService:
    """Gerencia a configuração local/servidor/cliente sem esconder falhas de I/O."""

    def __init__(self, paths: NetworkPaths) -> None:
        self.paths = paths
        self.paths.app_dir.mkdir(parents=True, exist_ok=True)
        self.last_warning = ""

    def load(self) -> dict[str, Any]:
        data: dict[str, Any] = {"modo": "local", "db_path": str(self.paths.local_db)}
        self.last_warning = ""
        if not self.paths.config_file.exists():
            return data
        try:
            saved = json.loads(self.paths.config_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.last_warning = f"Configuração de rede inválida: {exc}"
            return data
        if isinstance(saved, dict):
            data.update(saved)
        else:
            self.last_warning = "Configuração de rede ignorada porque não contém um objeto JSON."
        return data

    def save(self, mode: str, db_path: str | os.PathLike[str], role: str = "local") -> None:
        payload = {
            "modo": str(mode or "local").strip().lower(),
            "db_path": str(Path(db_path).expanduser().resolve()),
            "papel": str(role or "local").strip().lower(),
            "computador": socket.gethostname(),
        }
        self._atomic_json(self.paths.config_file, payload)

    def mark_installation_complete(self, role: str) -> None:
        self._atomic_json(
            self.paths.installation_file,
            {
                "papel": str(role or "local").strip().lower(),
                "computador": socket.gethostname(),
                "data": datetime.now().isoformat(timespec="seconds"),
            },
        )

    def prepare_server(self, db_path: str | os.PathLike[str] | None = None) -> str:
        target = Path(db_path or self.paths.server_db).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        self._assert_writable(target.parent)
        self.save("rede", target, "servidor")
        self.mark_installation_complete("servidor")
        return str(target)

    def repair_server_configuration(self) -> None:
        config = self.load()
        if config.get("papel") != "servidor":
            return
        target = Path(config.get("db_path") or self.paths.server_db).expanduser().resolve()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            self._assert_writable(target.parent)
        except OSError:
            self.prepare_server(self.paths.server_db)

    @staticmethod
    def client_paths(server: str) -> tuple[str, str, str]:
        normalized = str(server or "").strip().replace("\\", "").replace("/", "")
        share = rf"\\{normalized}\BancoCompartilhado"
        database = share + r"\fichario_moveis_compartilhado.db"
        return normalized, share, database

    def test_client(
        self,
        server: str,
        username: str = "",
        password: str = "",
        persistent: bool = True,
    ) -> str:
        normalized, share, database = self.client_paths(server)
        if not normalized:
            raise ValueError("Informe o IP ou o nome do computador servidor.")

        username = str(username or "").strip()
        password = str(password or "")
        if os.name == "nt" and username:
            command = [
                "net",
                "use",
                share,
                password,
                f"/user:{username}",
                "/persistent:yes" if persistent else "/persistent:no",
            ]
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="cp850",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            if process.returncode != 0:
                detail = (process.stdout or process.stderr or "Falha desconhecida do Windows.").strip()
                raise ConnectionError(f"O Windows não conseguiu autenticar no servidor.\n\n{detail}")

        if not os.path.isdir(share):
            raise FileNotFoundError(f"A pasta compartilhada não foi encontrada:\n{share}")
        if not os.path.isfile(database):
            raise FileNotFoundError(f"O banco compartilhado não foi encontrado:\n{database}")

        with connection_session(database, timeout=10, apply_journal=False) as connection:
            connection.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        self._assert_writable(Path(share))
        return database

    @staticmethod
    def _assert_writable(directory: Path) -> None:
        probe = directory / f".teste_nabicode_{socket.gethostname()}.tmp"
        try:
            probe.write_text("ok", encoding="utf-8")
        finally:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
