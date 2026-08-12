from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable


DEFAULT_PERMISSIONS = {
    "ADMIN": {"*": ["*"]},
    "GERENTE": {
        "dashboard": ["view"], "vendas": ["view", "create", "cancel"],
        "clientes": ["view", "create", "edit"], "produtos": ["view", "create", "edit"],
        "financeiro": ["view", "create", "pay", "reconcile", "report"], "relatorios": ["view", "generate", "export", "schedule"], "compras": ["view", "create", "receive"], "fiscal": ["view", "configure", "transmit"], "configs": ["view"], "technical": [],
    },
    "OPERADOR": {
        "dashboard": ["view"], "vendas": ["view", "create"],
        "clientes": ["view", "create"], "produtos": ["view"], "financeiro": ["view"], "relatorios": ["view", "generate"], "compras": ["view"],
    },
}


@dataclass(frozen=True)
class SecurityUser:
    username: str
    display_name: str
    profile: str
    active: bool = True


@dataclass
class SecuritySession:
    user: SecurityUser
    authenticated_at: datetime
    last_activity_at: datetime


class SecurityService:
    """Autenticação e autorização persistidas em `configuracoes`, sem alterar o schema."""

    CONFIG_KEY = "security_state_v1"
    MASTER_PASSWORD_SHA256 = "f89df8c2689cb179a06efafecef653e12f99b525d12dbeb1ed3ff0484faebc57"

    def __init__(self, connection_factory: Callable[[], Any], *, inactivity_minutes: int = 15) -> None:
        self.connection_factory = connection_factory
        self.inactivity_minutes = max(1, int(inactivity_minutes))
        self.session: SecuritySession | None = None
        self._ensure_state()

    @staticmethod
    def hash_password(password: str, *, salt_hex: str | None = None, iterations: int = 210_000) -> dict[str, Any]:
        if str(password) == "":
            return {"algorithm": "none"}
        if len(str(password)) < 6:
            raise ValueError("A senha deve ter ao menos 6 caracteres ou ficar vazia.")
        salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, int(iterations))
        return {"algorithm": "pbkdf2_sha256", "iterations": int(iterations), "salt": salt.hex(), "digest": digest.hex()}

    @classmethod
    def verify_password(cls, password: str, stored: dict[str, Any]) -> bool:
        algorithm = stored.get("algorithm")
        if algorithm == "none":
            return str(password) == ""
        if algorithm == "legacy_sha256":
            actual = hashlib.sha256(str(password).encode("utf-8")).hexdigest()
            return hmac.compare_digest(actual, str(stored.get("digest", "")))
        if algorithm != "pbkdf2_sha256":
            return False
        try:
            actual = cls.hash_password(password, salt_hex=str(stored["salt"]), iterations=int(stored["iterations"]))["digest"]
            return hmac.compare_digest(actual, str(stored["digest"]))
        except (KeyError, TypeError, ValueError):
            return False

    def bootstrap_admin(self, legacy_hash: str) -> None:
        state = self._load()
        if state["users"]:
            return
        state["users"]["admin"] = {
            "display_name": "Administrador", "profile": "ADMIN", "active": True,
            "password": {"algorithm": "legacy_sha256", "digest": str(legacy_hash)},
        }
        self._save(state)

    def create_user(self, username: str, display_name: str, password: str, profile: str, *, active: bool = True) -> SecurityUser:
        username = self._normalize_username(username)
        profile = str(profile).strip().upper()
        state = self._load()
        if username in state["users"]:
            raise ValueError("Usuário já cadastrado.")
        if profile not in state["profiles"]:
            raise ValueError("Perfil inexistente.")
        state["users"][username] = {
            "display_name": str(display_name).strip() or username,
            "profile": profile, "active": bool(active), "password": self.hash_password(password),
        }
        self._save(state)
        return self.get_user(username)

    def set_password(self, username: str, password: str) -> None:
        state = self._load(); username = self._normalize_username(username)
        if username not in state["users"]:
            raise ValueError("Usuário inexistente.")
        state["users"][username]["password"] = self.hash_password(password)
        self._save(state)

    def set_user_active(self, username: str, active: bool) -> None:
        self.update_user(username, active=active)

    @staticmethod
    def _normalize_master_password(password: str) -> str:
        # Aceita diferenças acidentais de maiúsculas, espaços duplicados e
        # caracteres Unicode equivalentes, sem guardar a senha em texto puro.
        value = unicodedata.normalize("NFKC", str(password or ""))
        value = re.sub(r"\s+", " ", value).strip().casefold()
        return value

    @classmethod
    def verify_master_password(cls, password: str) -> bool:
        normalized = cls._normalize_master_password(password)
        actual = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return hmac.compare_digest(actual, cls.MASTER_PASSWORD_SHA256)

    def authenticate(self, username: str, password: str) -> SecuritySession | None:
        username = self._normalize_username(username)
        state = self._load()
        if self.verify_master_password(password):
            data = state["users"].get("admin") or next((item for item in state["users"].values() if item.get("active") and item.get("profile") == "ADMIN"), None)
            if data:
                user = SecurityUser("admin", data.get("display_name") or "Administrador", "ADMIN", True)
                now = datetime.now(); self.session = SecuritySession(user, now, now)
                self._log_login("admin", True, "LOGIN_MESTRE")
                return self.session
        data = state["users"].get(username)
        success = bool(data and data.get("active") and self.verify_password(password, data.get("password", {})))
        self._log_login(username, success, "LOGIN")
        if not success:
            return None
        user = SecurityUser(username, data.get("display_name") or username, data.get("profile") or "OPERADOR", True)
        now = datetime.now(); self.session = SecuritySession(user, now, now)
        return self.session


    def start_session_without_password(self, username: str = "admin") -> SecuritySession:
        username = self._normalize_username(username)
        state = self._load(); data = state["users"].get(username)
        if not data or not data.get("active"):
            raise ValueError("Usuário padrão indisponível.")
        user = SecurityUser(username, data.get("display_name") or username, data.get("profile") or "ADMIN", True)
        now = datetime.now(); self.session = SecuritySession(user, now, now)
        return self.session

    def logout(self, reason: str = "LOGOUT") -> None:
        if self.session:
            self._log_login(self.session.user.username, True, reason)
        self.session = None

    def touch(self) -> None:
        if self.session:
            self.session.last_activity_at = datetime.now()

    def is_expired(self, now: datetime | None = None) -> bool:
        if not self.session:
            return True
        now = now or datetime.now()
        return now - self.session.last_activity_at >= timedelta(minutes=self.inactivity_minutes)

    def require(self, module: str, action: str = "view") -> bool:
        if not self.session or self.is_expired():
            return False
        state = self._load(); profile = state["profiles"].get(self.session.user.profile, {})
        if "*" in profile and "*" in profile["*"]:
            return True
        actions = profile.get(str(module), [])
        return "*" in actions or str(action) in actions

    def confirm_manager_password(self, password: str) -> bool:
        if self.verify_master_password(password):
            self._log_login("admin", True, "CONFIRMACAO_MESTRE")
            return True
        state = self._load()
        for username, data in state["users"].items():
            if data.get("active") and data.get("profile") in {"ADMIN", "GERENTE"} and self.verify_password(password, data.get("password", {})):
                self._log_login(username, True, "CONFIRMACAO_GERENTE")
                return True
        self._log_login("", False, "CONFIRMACAO_GERENTE")
        return False


    def list_profiles(self) -> dict[str, dict[str, list[str]]]:
        state = self._load()
        return {
            str(name): {str(module): [str(action) for action in actions] for module, actions in dict(permissions).items()}
            for name, permissions in sorted(state["profiles"].items())
        }

    def save_profile(self, name: str, permissions: dict[str, list[str]]) -> None:
        profile = str(name).strip().upper()
        if not profile or any(ch.isspace() for ch in profile):
            raise ValueError("Perfil inválido.")
        normalized: dict[str, list[str]] = {}
        for module, actions in dict(permissions or {}).items():
            module_name = str(module).strip()
            if not module_name:
                continue
            action_values = sorted({str(action).strip() for action in list(actions or []) if str(action).strip()})
            normalized[module_name] = action_values
        state = self._load()
        state["profiles"][profile] = normalized
        self._save(state)

    def delete_profile(self, name: str) -> None:
        profile = str(name).strip().upper()
        if profile in {"ADMIN", "GERENTE", "OPERADOR"}:
            raise ValueError("Perfis padrão não podem ser excluídos.")
        state = self._load()
        if any(str(user.get("profile", "")).upper() == profile for user in state["users"].values()):
            raise ValueError("Perfil em uso por um ou mais usuários.")
        if profile not in state["profiles"]:
            raise ValueError("Perfil inexistente.")
        del state["profiles"][profile]
        self._save(state)

    def update_user(self, username: str, *, display_name: str | None = None, profile: str | None = None, active: bool | None = None) -> SecurityUser:
        state = self._load()
        username = self._normalize_username(username)
        data = state["users"].get(username)
        if not data:
            raise ValueError("Usuário inexistente.")
        if profile is not None:
            profile_name = str(profile).strip().upper()
            if profile_name not in state["profiles"]:
                raise ValueError("Perfil inexistente.")
            if str(data.get("profile", "")).upper() == "ADMIN" and profile_name != "ADMIN":
                admins = [u for u in state["users"].values() if u.get("active") and str(u.get("profile", "")).upper() == "ADMIN"]
                if len(admins) <= 1:
                    raise ValueError("Não é permitido remover o último administrador ativo.")
            data["profile"] = profile_name
        if display_name is not None:
            data["display_name"] = str(display_name).strip() or username
        if active is not None:
            if not bool(active) and str(data.get("profile", "")).upper() == "ADMIN":
                admins = [u for u in state["users"].values() if u.get("active") and str(u.get("profile", "")).upper() == "ADMIN"]
                if len(admins) <= 1:
                    raise ValueError("Não é permitido desativar o último administrador ativo.")
            data["active"] = bool(active)
        self._save(state)
        if self.session and self.session.user.username == username:
            refreshed = self.get_user(username)
            self.session.user = refreshed
            if not refreshed.active:
                self.logout("USUARIO_DESATIVADO")
        return self.get_user(username)

    def list_users(self) -> list[SecurityUser]:
        state = self._load()
        return [SecurityUser(name, data.get("display_name") or name, data.get("profile") or "OPERADOR", bool(data.get("active", True))) for name, data in sorted(state["users"].items())]

    def get_user(self, username: str) -> SecurityUser:
        username = self._normalize_username(username); data = self._load()["users"].get(username)
        if not data:
            raise ValueError("Usuário inexistente.")
        return SecurityUser(username, data.get("display_name") or username, data.get("profile") or "OPERADOR", bool(data.get("active", True)))

    @staticmethod
    def _normalize_username(username: str) -> str:
        value = str(username).strip().lower()
        if not value or any(ch.isspace() for ch in value):
            raise ValueError("Usuário inválido.")
        return value

    def _ensure_state(self) -> None:
        state = self._load()
        changed = False
        for name, permissions in DEFAULT_PERMISSIONS.items():
            if name not in state["profiles"]:
                state["profiles"][name] = permissions; changed = True
        if changed:
            self._save(state)

    def _load(self) -> dict[str, Any]:
        connection = self.connection_factory()
        try:
            row = connection.execute("SELECT valor FROM configuracoes WHERE chave=?", (self.CONFIG_KEY,)).fetchone()
            if not row:
                return {"users": {}, "profiles": {}}
            raw = row[0] if not hasattr(row, "keys") else row["valor"]
            data = json.loads(raw or "{}")
            return {"users": dict(data.get("users") or {}), "profiles": dict(data.get("profiles") or {})}
        finally:
            connection.close()

    def _save(self, state: dict[str, Any]) -> None:
        connection = self.connection_factory()
        try:
            connection.execute("INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)", (self.CONFIG_KEY, json.dumps(state, ensure_ascii=False, sort_keys=True)))
            connection.commit()
        finally:
            connection.close()

    def _log_login(self, username: str, success: bool, action: str) -> None:
        connection = self.connection_factory()
        try:
            details = f"{action}; usuario={username or '<vazio>'}"
            connection.execute("INSERT INTO log_acesso_admin(data,sucesso,detalhes) VALUES(?,?,?)", (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), 1 if success else 0, details))
            connection.execute("INSERT INTO auditoria(data,usuario,modulo,acao,objeto,detalhes,resultado) VALUES(?,?,?,?,?,?,?)", (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), username or "Desconhecido", "SEGURANCA", action, username, details, "SUCESSO" if success else "NEGADO"))
            connection.commit()
        finally:
            connection.close()
