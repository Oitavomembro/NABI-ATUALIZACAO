from __future__ import annotations

import uuid
from threading import Lock


class AuthenticatedAssistantActivation:
    """Ativa o runtime local somente depois de autenticação real do operador."""

    def __init__(
        self, *, security_service, runtime_factory, assistant_factory,
        logout_on_stop: bool = True,
    ) -> None:
        if security_service is None or runtime_factory is None or assistant_factory is None:
            raise ValueError("Dependências de ativação da Nabi são obrigatórias.")
        self._security = security_service
        self._runtime_factory = runtime_factory
        self._assistant_factory = assistant_factory
        self._logout_on_stop = bool(logout_on_stop)
        self._runtime = None
        self._service = None
        self._lock = Lock()
        self._activating = False
        self._cancel_requested = False

    @property
    def active(self) -> bool:
        with self._lock:
            return self._service is not None

    def activate(self, username: str, password: str):
        with self._lock:
            if self._service is not None or self._activating:
                raise RuntimeError("A Nabi já está ativa ou em ativação nesta sessão.")
            self._activating = True
            self._cancel_requested = False
        username = str(username or "").strip()
        if not username:
            with self._lock:
                self._activating = False
            raise PermissionError("Informe o usuário para ativar a Nabi.")
        session = self._security.authenticate(username, str(password or ""))
        if session is None:
            with self._lock:
                self._activating = False
            raise PermissionError("Usuário ou senha inválidos.")

        runtime = None
        try:
            runtime = self._runtime_factory()
            runtime.start()
            model = runtime.create_model_adapter()
            session_id = uuid.uuid4().hex
            service = self._assistant_factory(model, session_id)
            with self._lock:
                if self._cancel_requested:
                    raise RuntimeError("A ativação da Nabi foi cancelada pelo operador.")
                self._runtime = runtime
                self._service = service
                self._activating = False
        except Exception:
            if runtime is not None:
                runtime.stop()
            if self._logout_on_stop:
                self._security.logout("IA_NABI_ATIVACAO_FALHOU")
            with self._lock:
                self._activating = False
            raise
        return service

    def stop(self) -> None:
        with self._lock:
            self._cancel_requested = True
            runtime, self._runtime = self._runtime, None
            had_service = self._service is not None
            self._service = None
        if runtime is None and not had_service:
            return
        if runtime is not None:
            runtime.stop()
        if self._logout_on_stop:
            self._security.logout("IA_NABI_ENCERRADA")
