import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from services.activity_service import ActivityService


class ActivityServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "test.db"
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY, data TEXT, tipo TEXT, descricao TEXT, valor REAL, status_pagamento TEXT);
            CREATE TABLE clientes(id INTEGER PRIMARY KEY, nome TEXT);
            CREATE TABLE produtos(id INTEGER PRIMARY KEY, nome TEXT, criado_em TEXT, atualizado_em TEXT, ativo INTEGER, controla_estoque INTEGER, estoque_atual REAL, estoque_minimo REAL);
            CREATE TABLE nfe_importacoes(id INTEGER PRIMARY KEY, numero TEXT, fornecedor_nome TEXT, status TEXT, data_importacao TEXT);
            CREATE TABLE titulos_financeiros(id INTEGER PRIMARY KEY, pessoa_nome TEXT, descricao TEXT, data_vencimento TEXT, valor_original REAL, atualizado_em TEXT, status TEXT);
        """)
        conn.execute("INSERT INTO movimentacoes VALUES(1,'02/08/2026 10:00:00','COMPRA','Venda balcão',100,'PAGO')")
        conn.execute("INSERT INTO clientes VALUES(1,'CLIENTE TESTE')")
        conn.execute("INSERT INTO produtos VALUES(1,'PRODUTO TESTE','2026-08-02 09:00:00','2026-08-02 09:00:00',1,1,2,5)")
        conn.execute("INSERT INTO nfe_importacoes VALUES(1,'123','FORNECEDOR','IMPORTADA','2026-08-02 08:00:00')")
        conn.execute("INSERT INTO titulos_financeiros VALUES(1,'PESSOA','Conta','2026-07-01',50,'2026-08-01 12:00:00','ABERTO')")
        conn.commit(); conn.close()

    def tearDown(self):
        self.temp.cleanup()

    def factory(self):
        return sqlite3.connect(self.db_path)

    def test_collects_supported_sources_without_schema_change(self):
        service = ActivityService(self.factory)
        activities = service.list_activities(days=0, now=datetime(2026, 8, 2, 13, 0))
        modules = {item.module for item in activities}
        self.assertTrue({'Vendas', 'Clientes', 'Produtos', 'Estoque', 'XML', 'Financeiro'}.issubset(modules))

    def test_filters_by_module(self):
        service = ActivityService(self.factory)
        activities = service.list_activities(days=0, module='Estoque', now=datetime(2026, 8, 2, 13, 0))
        self.assertTrue(activities)
        self.assertTrue(all(item.module == 'Estoque' for item in activities))

    def test_reads_backup_files(self):
        backup = Path(self.temp.name) / 'backups'; backup.mkdir()
        (backup / 'backup_001.db').write_bytes(b'ok')
        service = ActivityService(self.factory, backup_directory=backup)
        activities = service.list_activities(days=0)
        self.assertTrue(any(item.module == 'Backup' and item.description == 'backup_001.db' for item in activities))


if __name__ == '__main__':
    unittest.main()

class ActivityServicePermissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "permissions.db"
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE auditoria(id INTEGER PRIMARY KEY, data TEXT, acao TEXT, detalhes TEXT, usuario TEXT);
            INSERT INTO auditoria VALUES(1,'2026-08-02 11:00:00','LOGIN','Sessão iniciada','admin');
            INSERT INTO auditoria VALUES(2,'2026-08-02 12:00:00','LOGIN','Sessão iniciada','administrador');
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp.cleanup()

    def factory(self):
        return sqlite3.connect(self.db_path)

    def test_user_filter_is_exact(self):
        activities = ActivityService(self.factory).list_activities(days=0, user="admin")
        self.assertEqual([item.user for item in activities], ["admin"])

    def test_allowed_modules_removes_unauthorized_activity(self):
        activities = ActivityService(self.factory).list_activities(days=0, allowed_modules={"Vendas"})
        self.assertEqual(activities, [])
