from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import DatabaseManager
from repositories.client_history_repository import ClientHistoryRepository
from repositories.cliente_repository import ClienteRepository


class CadastroSaldoReconciliadoRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "cadastros_saldo.db"
        connection = sqlite3.connect(self.db_path)
        try:
            connection.executescript(
                """
                CREATE TABLE clientes (
                    id INTEGER PRIMARY KEY,
                    numero_ficha INTEGER,
                    codigo TEXT,
                    nome TEXT NOT NULL,
                    saldo_devedor REAL DEFAULT 0,
                    limite REAL DEFAULT 0,
                    telefone TEXT,
                    cpf TEXT,
                    rg TEXT,
                    endereco TEXT,
                    observacoes TEXT,
                    favorito INTEGER DEFAULT 0
                );
                CREATE TABLE movimentacoes (
                    id INTEGER PRIMARY KEY,
                    cliente_id INTEGER,
                    tipo TEXT,
                    descricao TEXT,
                    valor REAL,
                    data TEXT,
                    total_parcelas INTEGER,
                    valor_aberto REAL
                );
                CREATE TABLE parcelas (
                    id INTEGER PRIMARY KEY,
                    movimentacao_id INTEGER,
                    numero_parcela INTEGER,
                    valor_parcela REAL,
                    vencimento TEXT,
                    status TEXT,
                    valor_pago REAL,
                    data_pagamento TEXT,
                    atraso_registrado INTEGER DEFAULT 0,
                    dados_confiaveis INTEGER DEFAULT 1
                );
                CREATE TABLE historico_clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id INTEGER,
                    evento TEXT,
                    detalhes TEXT,
                    data TEXT
                );
                INSERT INTO clientes VALUES
                    (1, 5501, 'C1', 'MARIA SILVA', 220, 500, '', '', '', '', '', 0),
                    (2, 5502, 'C2', 'MARIA JOSE', 0, 500, '', '', '', '', '', 0),
                    (3, 5503, 'C3', 'AUGUSTO MARIA', 0, 500, '', '', '', '', '', 0);
                INSERT INTO movimentacoes VALUES
                    (10, 1, 'COMPRA', 'COMPRA ANTIGA', 1000, '01/08/2026', 1, 900);
                INSERT INTO parcelas VALUES
                    (20, 10, 1, 1000, '01/09/2026', 'PARCIAL', 100, '', 0, 1);
                INSERT INTO historico_clientes(cliente_id, evento, detalhes, data)
                    VALUES (1, 'CADASTRO', 'Cadastro criado.', '01/08/2026');
                """
            )
            connection.commit()
        finally:
            connection.close()

        database = DatabaseManager(str(self.db_path))
        self.clientes = ClienteRepository(database)
        self.historico = ClientHistoryRepository(database)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _commit_financeiro_simulado(self, saldo: float, *, evento: str = "PAGAMENTO") -> None:
        """Simula somente o resultado já reconciliado e commitado pelo Financeiro."""
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("UPDATE clientes SET saldo_devedor=? WHERE id=1", (saldo,))
            connection.execute(
                "INSERT INTO historico_clientes(cliente_id,evento,detalhes,data) VALUES(1,?,?,?)",
                (evento, f"Saldo reconciliado: {saldo:.2f}", "07/08/2026 08:00:00"),
            )
            connection.commit()
        finally:
            connection.close()

    def test_tabela_reflete_saldo_reconciliado_apos_pagamento_sem_cache(self) -> None:
        antes = self.clientes.list_page("5501")
        self.assertEqual(float(antes.rows[0][3]), 220.0)

        self._commit_financeiro_simulado(200.0)

        depois = self.clientes.list_page("5501")
        self.assertEqual(float(depois.rows[0][3]), 200.0)

    def test_tabela_nao_recalcula_saldo_a_partir_de_compras_ou_parcelas(self) -> None:
        self._commit_financeiro_simulado(200.0)

        pagina = self.clientes.list_page("5501")

        # A compra ainda possui 900 em aberto; Cadastros deve consumir exclusivamente
        # clientes.saldo_devedor, já reconciliado pelo Financeiro.
        self.assertEqual(float(pagina.rows[0][3]), 200.0)

    def test_historico_reflete_saldo_e_evento_apos_pagamento(self) -> None:
        self._commit_financeiro_simulado(200.0)

        dados = self.historico.load(1)

        self.assertIsNotNone(dados)
        assert dados is not None
        self.assertEqual(float(dados.client[3]), 200.0)
        self.assertEqual(dados.events[0][0], "PAGAMENTO")
        self.assertIn("200.00", dados.events[0][1])

    def test_historico_nao_deriva_saldo_de_movimentacoes(self) -> None:
        self._commit_financeiro_simulado(200.0)

        dados = self.historico.load(1)

        assert dados is not None
        self.assertEqual(float(dados.client[3]), 200.0)
        self.assertEqual(float(dados.transactions[0][3]), 1000.0)

    def test_busca_textual_preserva_ordenacao_por_relevancia(self) -> None:
        pagina = self.clientes.list_page("maria")
        nomes = [row[2] for row in pagina.rows]

        self.assertEqual(nomes[:2], ["MARIA SILVA", "MARIA JOSE"])
        self.assertEqual(nomes[-1], "AUGUSTO MARIA")

    def test_busca_numerica_prioriza_ficha_exata_sem_campos_vazios(self) -> None:
        pagina = self.clientes.list_page("5501")

        self.assertEqual(pagina.rows[0][0], 1)
        self.assertEqual(pagina.rows[0][1], 5501)

    def test_refresh_reconsulta_banco_em_chamadas_sucessivas(self) -> None:
        primeira = self.clientes.list_page("5501")
        self.assertEqual(float(primeira.rows[0][3]), 220.0)

        self._commit_financeiro_simulado(180.0, evento="AJUSTE_RECONCILIADO")
        segunda = self.clientes.list_page("5501")
        self.assertEqual(float(segunda.rows[0][3]), 180.0)

        self._commit_financeiro_simulado(160.0, evento="AJUSTE_RECONCILIADO")
        terceira = self.clientes.list_page("5501")
        self.assertEqual(float(terceira.rows[0][3]), 160.0)


if __name__ == "__main__":
    unittest.main()
