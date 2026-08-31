from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable
from services.critical_audit_policy import record_in_transaction


DEFAULT_PERMISSIONS = {
    "ADMIN": {"*": ["*"]},
    "GERENTE": {
        "dashboard": ["view"], "vendas": ["view", "create", "cancel"],
        "clientes": ["view", "create", "edit"], "produtos": ["view", "create", "edit"],
        "financeiro": ["view", "create", "pay", "reconcile", "report"], "relatorios": ["view", "generate", "export", "schedule"], "compras": ["view", "create", "receive"], "fiscal": ["view", "configure", "transmit", "cancel"], "configs": ["view"], "technical": [],
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
    LOGIN_THROTTLE_KEY = "security_login_throttle_v1"
    INITIAL_SETUP_KEY = "configuracao_inicial_concluida_v1"
    MAX_LOGIN_FAILURES = 5
    LOGIN_COOLDOWN_SECONDS = 60
    MANAGER_CONFIRMATION_THROTTLE_ID = "__confirmacao_gerencial__"

    def __init__(self, connection_factory: Callable[[], Any], *, inactivity_minutes: int | None = None) -> None:
        self.connection_factory = connection_factory
        self.inactivity_minutes = (
            max(1, int(inactivity_minutes)) if inactivity_minutes is not None else None
        )
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
        self._save_critical(state,"CRIAR_USUARIO","admin","Bootstrap da identidade administrativa legada.")

    def has_users(self) -> bool:
        """Informa se a instalação já possui uma identidade administrativa."""

        return bool(self._load()["users"])

    def needs_existing_installation_migration(self) -> bool:
        """Detecta base antiga com usuários, mas sem o marco do primeiro acesso."""

        if not self.has_users():
            return False
        connection = self.connection_factory()
        try:
            row = connection.execute(
                "SELECT valor FROM configuracoes WHERE chave=?", (self.INITIAL_SETUP_KEY,)
            ).fetchone()
            value = row[0] if row and not hasattr(row, "keys") else (row["valor"] if row else "")
            return str(value or "").strip() != "1"
        finally:
            connection.close()

    def complete_existing_installation_migration(
        self, *, username: str, current_password: str, new_password: str
    ) -> SecurityUser:
        """Converte uma base antiga mediante prova da credencial administrativa atual."""

        username = self._normalize_username(username)
        if len(str(new_password or "")) < 8:
            raise ValueError("A nova senha deve ter ao menos 8 caracteres.")
        connection = self.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            marker = connection.execute(
                "SELECT valor FROM configuracoes WHERE chave=?", (self.INITIAL_SETUP_KEY,)
            ).fetchone()
            marker_value = (
                marker[0] if marker and not hasattr(marker, "keys")
                else (marker["valor"] if marker else "")
            )
            if str(marker_value or "").strip() == "1":
                raise PermissionError("A migração de segurança já foi concluída.")
            row = connection.execute(
                "SELECT valor FROM configuracoes WHERE chave=?", (self.CONFIG_KEY,)
            ).fetchone()
            raw = row[0] if row and not hasattr(row, "keys") else (row["valor"] if row else "")
            state = json.loads(raw or "{}")
            users = dict(state.get("users") or {})
            data = users.get(username)
            if not data or not data.get("active") or str(data.get("profile") or "").upper() != "ADMIN":
                raise PermissionError("Informe um administrador ativo da instalação existente.")
            if not self.verify_password(current_password, data.get("password") or {}):
                raise PermissionError("A senha administrativa atual não confere.")
            data["password"] = self.hash_password(new_password)
            for other_username, other_data in users.items():
                if other_username == username:
                    continue
                if (other_data.get("password") or {}).get("algorithm") == "none":
                    other_data["active"] = False
            state["users"] = users
            connection.execute(
                "INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)",
                (self.CONFIG_KEY, json.dumps(state, ensure_ascii=False, sort_keys=True)),
            )
            connection.execute(
                "INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)",
                (self.INITIAL_SETUP_KEY, "1"),
            )
            connection.execute(
                "INSERT INTO auditoria(data,usuario,modulo,acao,objeto,detalhes,resultado) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    datetime.now().strftime("%d/%m/%Y %H:%M:%S"), username,
                    "SEGURANCA", "MIGRACAO_CREDENCIAL_LEGADA", username,
                    "Credencial administrativa substituída; contas antigas sem senha foram desativadas.", "SUCESSO",
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        self.session = None
        return self.get_user(username)

    def complete_initial_setup(
        self,
        *,
        username: str,
        display_name: str,
        password: str,
        store_name: str,
        document: str = "",
        email: str = "",
    ) -> SecurityUser:
        """Consome o primeiro acesso e cria o administrador sem sessão implícita.

        A verificação e a gravação usam a mesma transação para que duas
        instâncias concorrentes não consigam concluir o primeiro acesso.
        """

        username = self._normalize_username(username)
        display_name = str(display_name or "").strip() or username
        store_name = str(store_name or "").strip()
        document = "".join(character for character in str(document or "") if character.isdigit())
        email = str(email or "").strip()
        if not store_name:
            raise ValueError("Informe o nome da empresa ou loja.")
        if len(str(password or "")) < 8:
            raise ValueError("A senha inicial deve ter ao menos 8 caracteres.")
        if document and len(document) != 14:
            raise ValueError("O CNPJ deve possuir 14 dígitos ou ficar vazio.")
        if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
            raise ValueError("Informe um e-mail válido ou deixe o campo vazio.")

        connection = self.connection_factory()
        try:
            row = connection.execute(
                "SELECT valor FROM configuracoes WHERE chave=?", (self.CONFIG_KEY,)
            ).fetchone()
            raw = row[0] if row and not hasattr(row, "keys") else (row["valor"] if row else "")
            loaded = json.loads(raw or "{}")
            state = {
                "users": dict(loaded.get("users") or {}),
                "profiles": dict(loaded.get("profiles") or {}),
            }
            if state["users"]:
                raise PermissionError("A configuração inicial já foi concluída.")
            for name, permissions in DEFAULT_PERMISSIONS.items():
                state["profiles"].setdefault(name, permissions)
            state["users"][username] = {
                "display_name": display_name,
                "profile": "ADMIN",
                "active": True,
                "password": self.hash_password(password),
            }
            values = {
                self.CONFIG_KEY: json.dumps(state, ensure_ascii=False, sort_keys=True),
                "nome_loja": store_name,
                "cnpj": document,
                "email": email,
                "configuracao_inicial_concluida_v1": "1",
            }
            connection.executemany(
                "INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)",
                tuple(values.items()),
            )
            connection.execute(
                "INSERT INTO auditoria(data,usuario,modulo,acao,objeto,detalhes,resultado) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    datetime.now().strftime("%d/%m/%Y %H:%M:%S"), username,
                    "SEGURANCA", "CONFIGURACAO_INICIAL", username,
                    "Primeiro administrador e identificação básica configurados.", "SUCESSO",
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        self.session = None
        return self.get_user(username)

    def create_user(self, username: str, display_name: str, password: str, profile: str, *, active: bool = True) -> SecurityUser:
        username = self._normalize_username(username)
        profile = str(profile).strip().upper()
        if len(str(password or "")) < 8:
            raise ValueError("A senha do usuário deve ter ao menos 8 caracteres.")
        state = self._load()
        if username in state["users"]:
            raise ValueError("Usuário já cadastrado.")
        if profile not in state["profiles"]:
            raise ValueError("Perfil inexistente.")
        state["users"][username] = {
            "display_name": str(display_name).strip() or username,
            "profile": profile, "active": bool(active), "password": self.hash_password(password),
        }
        self._save_critical(state,"CRIAR_USUARIO",username,f"perfil={profile}; ativo={bool(active)}")
        return self.get_user(username)

    def set_password(self, username: str, password: str) -> None:
        if len(str(password or "")) < 8:
            raise ValueError("A nova senha deve ter ao menos 8 caracteres.")
        state = self._load(); username = self._normalize_username(username)
        if username not in state["users"]:
            raise ValueError("Usuário inexistente.")
        state["users"][username]["password"] = self.hash_password(password)
        self._save_critical(state,"ALTERAR_SENHA",username,"Senha alterada.")

    def set_user_active(self, username: str, active: bool) -> None:
        self.update_user(username, active=active)

    def authenticate(self, username: str, password: str) -> SecuritySession | None:
        username = self._normalize_username(username)
        if self._login_is_blocked(username):
            self._log_login(username, False, "LOGIN_BLOQUEADO")
            return None
        state = self._load()
        data = state["users"].get(username)
        success = bool(data and data.get("active") and self.verify_password(password, data.get("password", {})))
        self._log_login(username, success, "LOGIN")
        if not success:
            self._record_login_attempt(username, False)
            return None
        self._record_login_attempt(username, True)
        user = SecurityUser(username, data.get("display_name") or username, data.get("profile") or "OPERADOR", True)
        now = datetime.now(); self.session = SecuritySession(user, now, now)
        return self.session

    def _login_is_blocked(self, username: str, *, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        connection = self.connection_factory()
        try:
            row = connection.execute(
                "SELECT valor FROM configuracoes WHERE chave=?", (self.LOGIN_THROTTLE_KEY,)
            ).fetchone()
            data = json.loads((row[0] if row else "") or "{}")
            blocked_until = str((data.get(username) or {}).get("blocked_until") or "")
            if not blocked_until:
                return False
            return now < datetime.fromisoformat(blocked_until)
        except (ValueError, TypeError, json.JSONDecodeError):
            return True
        finally:
            connection.close()

    def _record_login_attempt(
        self, username: str, success: bool, *, now: datetime | None = None
    ) -> None:
        now = now or datetime.now()
        connection = self.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT valor FROM configuracoes WHERE chave=?", (self.LOGIN_THROTTLE_KEY,)
            ).fetchone()
            data = json.loads((row[0] if row else "") or "{}")
            if success:
                data.pop(username, None)
            else:
                previous = data.get(username) or {}
                failures = int(previous.get("failures") or 0) + 1
                blocked_until = ""
                if failures >= self.MAX_LOGIN_FAILURES:
                    blocked_until = (
                        now + timedelta(seconds=self.LOGIN_COOLDOWN_SECONDS)
                    ).isoformat(timespec="seconds")
                    failures = 0
                data[username] = {
                    "failures": failures, "blocked_until": blocked_until,
                }
            connection.execute(
                "INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)",
                (self.LOGIN_THROTTLE_KEY, json.dumps(data, sort_keys=True)),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


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
        if self.inactivity_minutes is None:
            return False
        now = now or datetime.now()
        return now - self.session.last_activity_at >= timedelta(minutes=self.inactivity_minutes)

    def require(self, module: str, action: str = "view") -> bool:
        if not self.session or self.is_expired():
            return False
        state = self._load()
        persisted = state["users"].get(self.session.user.username)
        if not persisted or not bool(persisted.get("active")):
            self.logout("SESSAO_REVOGADA")
            return False
        current_user = SecurityUser(
            self.session.user.username,
            persisted.get("display_name") or self.session.user.username,
            persisted.get("profile") or "OPERADOR",
            True,
        )
        if current_user != self.session.user:
            self.session.user = current_user
        profile = state["profiles"].get(current_user.profile, {})
        if "*" in profile and "*" in profile["*"]:
            return True
        actions = profile.get(str(module), [])
        return "*" in actions or str(action) in actions

    def require_actor(self, module: str, action: str) -> str:
        """Revalida a sessão persistida e retorna o ator, sem fallback externo."""
        if self.session is None or self.is_expired():
            raise PermissionError("Sessão expirada. Entre novamente para continuar.")
        if not self.require(module, action):
            if self.session is None:
                raise PermissionError("Sessão revogada. Entre novamente para continuar.")
            raise PermissionError("Usuário sem permissão para esta operação.")
        actor = str(self.session.user.username or "").strip()
        if not actor:
            self.session = None
            raise PermissionError("Sessão autenticada inválida.")
        self.touch()
        return actor

    def confirm_manager_password(self, password: str) -> bool:
        throttle_id = self.MANAGER_CONFIRMATION_THROTTLE_ID
        if self._login_is_blocked(throttle_id):
            self._log_login("", False, "CONFIRMACAO_GERENTE_BLOQUEADA")
            return False
        state = self._load()
        for username, data in state["users"].items():
            if data.get("active") and data.get("profile") in {"ADMIN", "GERENTE"} and self.verify_password(password, data.get("password", {})):
                self._log_login(username, True, "CONFIRMACAO_GERENTE")
                self._record_login_attempt(throttle_id, True)
                return True
        self._log_login("", False, "CONFIRMACAO_GERENTE")
        self._record_login_attempt(throttle_id, False)
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
        self._save_critical(state,"SALVAR_PERFIL",profile,"Permissões do perfil atualizadas.")

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
        self._save_critical(state,"EXCLUIR_PERFIL",profile,"Perfil excluído.")

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
        self._save_critical(state,"ATUALIZAR_USUARIO",username,f"perfil={data.get('profile')}; ativo={bool(data.get('active'))}")
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
        manager_fiscal = state["profiles"].get("GERENTE", {}).get("fiscal")
        if isinstance(manager_fiscal, list) and "cancel" not in manager_fiscal:
            manager_fiscal.append("cancel")
            changed = True
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

    def _save_critical(self, state: dict[str, Any], action: str, object_id: str, details: str) -> None:
        connection = self.connection_factory()
        actor = self.session.user.username if self.session is not None else "Sistema"
        occurred_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)",
                (self.CONFIG_KEY,json.dumps(state,ensure_ascii=False,sort_keys=True)),
            )
            record_in_transaction(
                connection,"SEGURANCA",action,user=actor,object_id=object_id,
                details=details,occurred_at=occurred_at,
            )
            connection.commit()
        except Exception:
            connection.rollback(); raise
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
