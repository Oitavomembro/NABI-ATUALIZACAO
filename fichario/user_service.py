from datetime import datetime

from services.security_service import SecurityService, SecuritySession


class FicharioSecurityService(SecurityService):
    """Login individual: sem acesso automático ou senha universal."""

    DEFAULT_LEGACY_HASH = "c6e9ec8af02a450b41405d7f905d7ce4061bd7559d576d5dd56efd3071b399ef"

    def needs_setup(self):
        users = self._load()["users"]
        if not users:
            return True
        return (
            set(users) == {"admin"}
            and users["admin"].get("password") == {
                "algorithm": "legacy_sha256", "digest": self.DEFAULT_LEGACY_HASH
            }
        )

    def setup_admin(self, username, name, password):
        if not self.needs_setup():
            raise PermissionError("Primeiro acesso já configurado.")
        if len(password) < 6:
            raise ValueError("Informe uma senha com ao menos 6 caracteres.")
        username = self._normalize_username(username)
        state = self._load()
        # Preserva a identidade histórica admin, mesmo quando o novo login difere.
        if "admin" in state["users"] and username != "admin":
            state["users"]["admin"]["active"] = False
        state["users"][username] = {
            "display_name": name.strip() or username, "profile": "ADMIN",
            "active": True, "password": self.hash_password(password),
        }
        self._save(state)
        self._log_login(username, True, "PRIMEIRO_ACESSO_INDIVIDUAL")

    def authenticate(self, username, password):
        self.session = None
        try:
            username = self._normalize_username(username)
        except ValueError:
            return None
        data = self._load()["users"].get(username)
        valid = bool(
            password and data and data.get("active")
            and self.verify_password(password, data.get("password", {}))
        )
        self._log_login(username, valid, "LOGIN")
        if valid:
            now = datetime.now()
            self.session = SecuritySession(self.get_user(username), now, now)
        return self.session

    def start_session_without_password(self, username="admin"):
        raise PermissionError("Login individual obrigatório.")

    def require(self, module, action="view"):
        if self.session is None or self.is_expired():
            return False
        try:
            user = self.get_user(self.session.user.username)
        except ValueError:
            return False
        if not user.active:
            return False
        self.session.user = user
        return super().require(module, action)

    def actor(self, module, action):
        if not self.require(module, action):
            raise PermissionError("Sessão expirada ou permissão insuficiente. Entre novamente.")
        self.touch()
        return self.session.user.username

    def save_account(self, username, name, password, profile, active=True, *, existing=False):
        self.actor("usuarios", "edit")
        if profile not in ("ADMIN", "GERENTE", "OPERADOR"):
            raise ValueError("Perfil inválido.")
        if not existing and len(password) < 6:
            raise ValueError("Informe uma senha com ao menos 6 caracteres.")
        if password and len(password) < 6:
            raise ValueError("A senha deve ter ao menos 6 caracteres.")
        if existing:
            self.update_user(username, display_name=name, profile=profile, active=active)
            if password:
                self.set_password(username, password)
        else:
            self.create_user(username, name, password, profile, active=active)

