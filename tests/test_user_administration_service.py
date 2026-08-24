from __future__ import annotations

import hashlib
import sqlite3

import pytest

from administration.user_application_service import UserAdministrationService, UserDraft
from services.security_service import SecurityService


def _security(tmp_path):
    database = tmp_path / "security.db"
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE configuracoes(id INTEGER PRIMARY KEY, chave TEXT UNIQUE, valor TEXT);
        CREATE TABLE log_acesso_admin(id INTEGER PRIMARY KEY, data TEXT, sucesso INTEGER, detalhes TEXT);
        CREATE TABLE auditoria(id INTEGER PRIMARY KEY, data TEXT, usuario TEXT, modulo TEXT, acao TEXT, objeto TEXT, detalhes TEXT, resultado TEXT);
    """)
    connection.close()
    service = SecurityService(lambda: sqlite3.connect(database))
    service.bootstrap_admin(hashlib.sha256(b"segredo").hexdigest())
    return service


def test_sessao_admin_cria_edita_senha_e_desativa_usuario(tmp_path):
    security = _security(tmp_path); security.authenticate("admin", "segredo")
    application = UserAdministrationService(security)
    created = application.create(UserDraft(" Maria ", "Maria", "OPERADOR", True, "senha123"))
    assert created.username == "maria"
    updated = application.update("maria", UserDraft("maria", "Maria Silva", "GERENTE", True, "nova456"))
    assert updated.display_name == "Maria Silva" and updated.profile == "GERENTE"
    application.toggle_active("maria")
    assert not application.get_user("maria").active
    security.logout(); assert security.authenticate("maria", "nova456") is None


def test_operador_nao_administra_usuarios_mesmo_informando_dados_validos(tmp_path):
    security = _security(tmp_path); security.authenticate("admin", "segredo")
    security.create_user("caixa", "Caixa", "senha123", "OPERADOR")
    security.authenticate("caixa", "senha123")
    application = UserAdministrationService(security)
    with pytest.raises(PermissionError): application.list_users()
    with pytest.raises(PermissionError):
        application.create(UserDraft("intruso", "Intruso", "ADMIN", True, "senha123"))


def test_sessao_expirada_falha_fechada(tmp_path):
    security = _security(tmp_path); security.authenticate("admin", "segredo"); security.logout()
    with pytest.raises(PermissionError): UserAdministrationService(security).list_profiles()


def test_fachada_preserva_protecao_do_ultimo_administrador(tmp_path):
    security = _security(tmp_path); security.authenticate("admin", "segredo")
    application = UserAdministrationService(security)
    with pytest.raises(ValueError, match="último administrador"):
        application.toggle_active("admin")


def test_identificador_nao_pode_ser_trocado_durante_edicao(tmp_path):
    security = _security(tmp_path); security.authenticate("admin", "segredo")
    application = UserAdministrationService(security)
    application.create(UserDraft("maria", "Maria", "OPERADOR", True, "senha123"))
    with pytest.raises(ValueError, match="não pode ser alterado"):
        application.update("maria", UserDraft("outra", "Maria", "OPERADOR"))
