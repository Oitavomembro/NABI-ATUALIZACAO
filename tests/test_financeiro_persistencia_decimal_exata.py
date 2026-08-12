from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from decimal import Decimal
from pathlib import Path

from database import DatabaseManager
from database.product_decimal_migration import ProductDecimalMigration
from repositories.financeiro_repository import FinanceiroRepository


class FinanceiroPersistenciaDecimalExataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "financeiro_decimal.db"
        self.db = DatabaseManager(str(self.db_path))
        with self.db.session(write=True) as conn:
            conn.executescript("""
                CREATE TABLE produtos(id INTEGER PRIMARY KEY);
                CREATE TABLE titulos_financeiros(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo TEXT NOT NULL, origem TEXT NOT NULL, origem_id TEXT NOT NULL,
                    pessoa_id INTEGER, pessoa_nome TEXT NOT NULL, documento TEXT NOT NULL,
                    descricao TEXT NOT NULL, data_emissao TEXT NOT NULL, data_vencimento TEXT NOT NULL,
                    valor_original REAL NOT NULL DEFAULT 0, valor_pago REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL, observacao TEXT NOT NULL, criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL
                );
                CREATE TABLE pagamentos_titulos(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, titulo_id INTEGER NOT NULL,
                    valor REAL NOT NULL, forma_pagamento TEXT NOT NULL, observacao TEXT NOT NULL,
                    usuario TEXT NOT NULL, data_pagamento TEXT NOT NULL
                );
            """)
            ProductDecimalMigration.migrate_connection(conn)
        self.repo = FinanceiroRepository(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_titulo_e_pagamento_preservam_texto_decimal_canonico(self):
        valor = Decimal("123.456789012345678901")
        pagamento = Decimal("0.100000000000000001")
        with self.db.session(write=True) as conn:
            titulo_id = self.repo.criar_titulo(
                tipo="RECEBER", origem="MANUAL", origem_id="", pessoa_id=None,
                pessoa_nome="", documento="", descricao="", data_emissao="2026-08-05",
                data_vencimento="2026-08-05", valor_original=valor, observacao="", connection=conn,
            )
            self.repo.registrar_pagamento(
                titulo_id=titulo_id, valor=pagamento, forma_pagamento="PIX", observacao="",
                usuario="teste", data_pagamento="2026-08-05", connection=conn,
            )
        with closing(sqlite3.connect(self.db_path)) as conn:
            titulo = conn.execute(
                "SELECT valor_original_decimal, typeof(valor_original_decimal) FROM titulos_financeiros WHERE id=?",
                (titulo_id,),
            ).fetchone()
            pgto = conn.execute(
                "SELECT valor_decimal, typeof(valor_decimal) FROM pagamentos_titulos WHERE titulo_id=?",
                (titulo_id,),
            ).fetchone()
        self.assertEqual(titulo, (str(valor), "text"))
        self.assertEqual(pgto, (str(pagamento), "text"))
        self.assertEqual(self.repo.obter_titulo(titulo_id)["valor_original"], valor)
        self.assertEqual(self.repo.listar_pagamentos(titulo_id)[0]["valor"], pagamento)

    def test_leitura_canonica_invalida_retorna_valor_legado(self):
        with self.db.session(write=True) as conn:
            conn.execute("""INSERT INTO titulos_financeiros
                (tipo,origem,origem_id,pessoa_nome,documento,descricao,data_emissao,data_vencimento,
                 valor_original,valor_original_decimal,valor_pago,valor_pago_decimal,status,observacao,criado_em,atualizado_em)
                VALUES('PAGAR','MANUAL','','','','','2026-08-05','2026-08-05',20,'abc',5,'','PARCIAL','','','')""")
            titulo_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        titulo = self.repo.obter_titulo(titulo_id)
        self.assertEqual(titulo["valor_original"], Decimal("20.0"))
        self.assertEqual(titulo["valor_pago"], Decimal("5.0"))
        self.assertEqual(titulo["saldo_aberto"], Decimal("15.0"))


if __name__ == "__main__":
    unittest.main()
