from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from database import DatabaseManager
from repositories import FinanceiroRepository


SCHEMA = """
CREATE TABLE titulos_financeiros (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, origem TEXT, origem_id TEXT,
 pessoa_id INTEGER, pessoa_nome TEXT, documento TEXT, descricao TEXT,
 data_emissao TEXT, data_vencimento TEXT, valor_original REAL, valor_pago REAL,
 status TEXT, observacao TEXT, criado_em TEXT, atualizado_em TEXT
);
CREATE TABLE pagamentos_titulos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, titulo_id INTEGER, valor REAL,
 forma_pagamento TEXT, observacao TEXT, usuario TEXT, data_pagamento TEXT
);
"""


class FinanceiroDecimalRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = DatabaseManager(str(Path(self.tmp.name) / "financeiro_decimal.db"))
        with self.db.session(write=True) as conn:
            conn.executescript(SCHEMA)
        self.repo = FinanceiroRepository(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_repositorio_aceita_decimal_e_retorna_decimal(self):
        with self.db.session(write=True) as conn:
            titulo_id = self.repo.criar_titulo(
                tipo="RECEBER", origem="MANUAL", origem_id="", pessoa_id=None,
                pessoa_nome="Cliente", documento="", descricao="Teste",
                data_emissao="2026-08-05", data_vencimento="2026-08-10",
                valor_original=Decimal("123.45"), observacao="", connection=conn,
            )
            self.repo.registrar_pagamento(
                titulo_id=titulo_id, valor=Decimal("23.45"), forma_pagamento="PIX",
                observacao="", usuario="Teste", data_pagamento="2026-08-05", connection=conn,
            )
            self.repo.atualizar_pagamento_titulo(titulo_id, Decimal("23.45"), "PARCIAL", conn)
        titulo = self.repo.obter_titulo(titulo_id)
        self.assertIsInstance(titulo["valor_original"], Decimal)
        self.assertIsInstance(titulo["valor_pago"], Decimal)
        self.assertEqual(titulo["saldo_aberto"], Decimal("100.0"))
        pagamento = self.repo.listar_pagamentos(titulo_id)[0]
        self.assertIsInstance(pagamento["valor"], Decimal)
        self.assertEqual(pagamento["valor"], Decimal("23.45"))

    def test_overflow_financeiro_e_rejeitado(self):
        with self.db.session(write=True) as conn:
            with self.assertRaises(Exception):
                self.repo.criar_titulo(
                    tipo="RECEBER", origem="MANUAL", origem_id="", pessoa_id=None,
                    pessoa_nome="Cliente", documento="", descricao="Teste",
                    data_emissao="2026-08-05", data_vencimento="2026-08-10",
                    valor_original=Decimal("1E+10000"), observacao="", connection=conn,
                )


if __name__ == "__main__":
    unittest.main()
