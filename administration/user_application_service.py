from __future__ import annotations

from dataclasses import dataclass

from services.security_service import SecurityService, SecurityUser


@dataclass(frozen=True, slots=True)
class UserDraft:
    username: str
    display_name: str
    profile: str
    active: bool = True
    password: str = ""

    def __post_init__(self) -> None:
        username = str(self.username or "").strip().lower()
        if not username or any(character.isspace() for character in username):
            raise ValueError("Usuário inválido.")
        profile = str(self.profile or "").strip().upper()
        if not profile:
            raise ValueError("Selecione um perfil.")
        object.__setattr__(self, "username", username)
        object.__setattr__(self, "display_name", str(self.display_name or "").strip() or username)
        object.__setattr__(self, "profile", profile)
        object.__setattr__(self, "password", str(self.password or ""))


class UserAdministrationService:
    """Porta única da GUI; nunca aceita identidade ou permissão fornecida pela tela."""

    MODULE = "technical"
    ACTION = "users"

    def __init__(self, security: SecurityService) -> None:
        self.security = security

    def _require(self) -> str:
        session = self.security.session
        if session is None or self.security.is_expired():
            raise PermissionError("Sessão expirada. Entre novamente.")
        if not self.security.require(self.MODULE, self.ACTION):
            raise PermissionError("Usuário sem permissão para administrar acessos.")
        return session.user.username

    def list_users(self) -> tuple[SecurityUser, ...]:
        self._require(); return tuple(self.security.list_users())

    def list_profiles(self) -> tuple[str, ...]:
        self._require(); return tuple(self.security.list_profiles())

    def get_user(self, username: str) -> SecurityUser:
        self._require(); return self.security.get_user(username)

    def create(self, draft: UserDraft) -> SecurityUser:
        self._require()
        return self.security.create_user(
            draft.username, draft.display_name, draft.password,
            draft.profile, active=draft.active,
        )

    def update(self, original_username: str, draft: UserDraft) -> SecurityUser:
        self._require()
        if draft.username != str(original_username).strip().lower():
            raise ValueError("O identificador do usuário não pode ser alterado.")
        user = self.security.update_user(
            original_username, display_name=draft.display_name,
            profile=draft.profile, active=draft.active,
        )
        if draft.password:
            self.security.set_password(original_username, draft.password)
        return user

    def toggle_active(self, username: str) -> SecurityUser:
        self._require()
        user = self.security.get_user(username)
        self.security.set_user_active(username, not user.active)
        return self.security.get_user(username)
