import hashlib
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from services.security_service import SecurityService


class SecurityServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.db = Path(self.tmp.name) / "test.db"
        con = sqlite3.connect(self.db)
        con.executescript("""
        CREATE TABLE configuracoes(id INTEGER PRIMARY KEY, chave TEXT UNIQUE, valor TEXT);
        CREATE TABLE log_acesso_admin(id INTEGER PRIMARY KEY, data TEXT, sucesso INTEGER, detalhes TEXT);
        CREATE TABLE auditoria(id INTEGER PRIMARY KEY, data TEXT, usuario TEXT, modulo TEXT, acao TEXT, objeto TEXT, detalhes TEXT, resultado TEXT);
        """); con.close()
        self.factory = lambda: sqlite3.connect(self.db)
        self.service = SecurityService(self.factory, inactivity_minutes=1)
        self.service.bootstrap_admin(hashlib.sha256(b"segredo").hexdigest())

    def tearDown(self): self.tmp.cleanup()

    def test_bootstrap_e_login_legacy(self):
        session = self.service.authenticate("admin", "segredo")
        self.assertIsNotNone(session); self.assertTrue(self.service.require("qualquer", "acao"))

    def test_usuario_operador_respeita_permissoes(self):
        self.service.create_user("caixa", "Operador", "senha123", "OPERADOR")
        self.assertIsNotNone(self.service.authenticate("caixa", "senha123"))
        self.assertTrue(self.service.require("vendas", "create"))
        self.assertFalse(self.service.require("technical", "view"))

    def test_bloqueio_por_inatividade(self):
        session = self.service.authenticate("admin", "segredo")
        session.last_activity_at = datetime.now() - timedelta(minutes=2)
        self.assertTrue(self.service.is_expired()); self.assertFalse(self.service.require("dashboard"))

    def test_confirmacao_de_gerente(self):
        self.service.create_user("gerente", "Gerente", "senha456", "GERENTE")
        self.assertTrue(self.service.confirm_manager_password("senha456"))
        self.assertFalse(self.service.confirm_manager_password("errada"))

    def test_desativacao_bloqueia_login(self):
        self.service.create_user("caixa", "Operador", "senha123", "OPERADOR")
        self.service.set_user_active("caixa", False)
        self.assertIsNone(self.service.authenticate("caixa", "senha123"))

    def test_outra_instancia_revoga_sessao_imediatamente(self):
        self.service.create_user("caixa", "Operador", "senha123", "OPERADOR")
        self.assertIsNotNone(self.service.authenticate("caixa", "senha123"))
        administrator = SecurityService(self.factory)
        administrator.set_user_active("caixa", False)
        self.assertFalse(self.service.require("vendas", "view"))
        self.assertIsNone(self.service.session)

    def test_outra_instancia_atualiza_perfil_da_sessao(self):
        self.service.create_user("caixa", "Operador", "senha123", "OPERADOR")
        self.assertIsNotNone(self.service.authenticate("caixa", "senha123"))
        administrator = SecurityService(self.factory)
        administrator.update_user("caixa", profile="GERENTE")
        self.assertTrue(self.service.require("financeiro", "pay"))
        self.assertEqual(self.service.session.user.profile, "GERENTE")

    def test_perfil_personalizado_e_atualizacao_usuario(self):
        self.service.save_profile("VENDEDOR", {"vendas": ["view", "create"]})
        self.service.create_user("maria", "Maria", "senha789", "VENDEDOR")
        self.service.update_user("maria", display_name="Maria Silva", active=True)
        self.assertEqual(self.service.get_user("maria").display_name, "Maria Silva")
        self.assertIsNotNone(self.service.authenticate("maria", "senha789"))
        self.assertTrue(self.service.require("vendas", "create"))
        self.assertFalse(self.service.require("technical", "view"))

    def test_nao_permite_desativar_ultimo_admin(self):
        with self.assertRaises(ValueError):
            self.service.set_user_active("admin", False)

    def test_perfil_em_uso_nao_pode_ser_excluido(self):
        self.service.save_profile("VENDEDOR", {"vendas": ["view"]})
        self.service.create_user("maria", "Maria", "senha789", "VENDEDOR")
        with self.assertRaises(ValueError):
            self.service.delete_profile("VENDEDOR")



    def test_usuario_sem_senha_pode_autenticar_com_campo_vazio(self):
        self.service.create_user("caixa", "Caixa", "", "OPERADOR")
        self.assertIsNotNone(self.service.authenticate("caixa", ""))
        self.service.logout()
        self.assertIsNone(self.service.authenticate("caixa", "qualquer"))

    def test_sessao_automatica_sem_senha(self):
        sessao = self.service.start_session_without_password("admin")
        self.assertEqual(sessao.user.username, "admin")
        self.assertTrue(self.service.require("qualquer_modulo", "qualquer_acao"))


class InitialSecuritySetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.db = Path(self.tmp.name) / "initial.db"
        connection = sqlite3.connect(self.db)
        connection.executescript("""
        CREATE TABLE configuracoes(id INTEGER PRIMARY KEY, chave TEXT UNIQUE, valor TEXT);
        CREATE TABLE log_acesso_admin(id INTEGER PRIMARY KEY, data TEXT, sucesso INTEGER, detalhes TEXT);
        CREATE TABLE auditoria(id INTEGER PRIMARY KEY, data TEXT, usuario TEXT, modulo TEXT, acao TEXT, objeto TEXT, detalhes TEXT, resultado TEXT);
        """)
        connection.close()
        self.service = SecurityService(lambda: sqlite3.connect(self.db))

    def tearDown(self): self.tmp.cleanup()

    def test_primeiro_acesso_cria_admin_sem_abrir_sessao(self):
        self.assertFalse(self.service.has_users())
        user = self.service.complete_initial_setup(
            username="dono", display_name="Dono da Loja", password="segura123",
            store_name="Loja Nabi", document="12.345.678/0001-90",
            email="dono@example.test",
        )
        self.assertEqual((user.username, user.profile), ("dono", "ADMIN"))
        self.assertIsNone(self.service.session)
        self.assertIsNotNone(self.service.authenticate("dono", "segura123"))
        connection = sqlite3.connect(self.db)
        values = dict(connection.execute(
            "SELECT chave,valor FROM configuracoes WHERE chave IN "
            "('nome_loja','cnpj','email','configuracao_inicial_concluida_v1')"
        ))
        audit = connection.execute(
            "SELECT acao,usuario FROM auditoria WHERE acao='CONFIGURACAO_INICIAL'"
        ).fetchone()
        connection.close()
        self.assertEqual(values["nome_loja"], "Loja Nabi")
        self.assertEqual(values["cnpj"], "12345678000190")
        self.assertEqual(values["configuracao_inicial_concluida_v1"], "1")
        self.assertEqual(audit, ("CONFIGURACAO_INICIAL", "dono"))

    def test_primeiro_acesso_e_consumido_uma_unica_vez(self):
        arguments = dict(
            username="dono", display_name="Dono", password="segura123",
            store_name="Loja Nabi",
        )
        self.service.complete_initial_setup(**arguments)
        with self.assertRaises(PermissionError):
            self.service.complete_initial_setup(**arguments)

    def test_falha_de_validacao_nao_cria_usuario_parcial(self):
        with self.assertRaises(ValueError):
            self.service.complete_initial_setup(
                username="dono", display_name="Dono", password="curta",
                store_name="Loja Nabi",
            )
        self.assertFalse(self.service.has_users())

if __name__ == "__main__": unittest.main()
