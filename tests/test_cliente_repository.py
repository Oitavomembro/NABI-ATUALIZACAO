from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from database import DatabaseManager
from repositories.cliente_repository import ClienteRepository


class ClienteRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "clientes.db"
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE historico_clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id INTEGER NOT NULL,
                    evento TEXT NOT NULL,
                    detalhes TEXT,
                    data TEXT NOT NULL
                );
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
                """
            )
            conn.executemany(
                """INSERT INTO clientes
                   (numero_ficha,codigo,nome,saldo_devedor,limite,telefone,cpf,rg,endereco,observacoes,favorito)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    (20, "C20", "MARIA SILVA", 10, 100, "222", "222.222.222-22", "RG2", "RUA B", "", 1),
                    (10, "C10", "JOAO SOUZA", 0, 50, "111", "111.111.111-11", "RG1", "RUA A", "VIP", 0),
                    (30, "C30", "MARIA JOSE", 5, 70, "333", "333.333.333-33", "RG3", "RUA C", "", 1),
                ],
            )
            conn.commit()
        finally:
            conn.close()
        self.repo = ClienteRepository(DatabaseManager(str(self.db_path)))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_paginacao_limita_e_calcula_totais(self) -> None:
        pagina = self.repo.list_page(page=0, per_page=2)
        self.assertEqual(pagina.total, 3)
        self.assertEqual(pagina.total_pages, 2)
        self.assertEqual(pagina.page, 0)
        self.assertEqual([row[1] for row in pagina.rows], [10, 20])

    def test_pagina_fora_do_limite_e_ajustada(self) -> None:
        pagina = self.repo.list_page(page=99, per_page=2)
        self.assertEqual(pagina.page, 1)
        self.assertEqual(pagina.offset, 2)
        self.assertEqual([row[1] for row in pagina.rows], [30])

    def test_busca_prioriza_ficha_exata(self) -> None:
        pagina = self.repo.list_page("20")
        self.assertEqual(pagina.total, 1)
        self.assertEqual(pagina.rows[0][1], 20)

    def test_filtro_favoritos_e_busca_por_nome(self) -> None:
        pagina = self.repo.list_page("maria", favorites_only=True)
        self.assertEqual(pagina.total, 2)
        self.assertEqual([row[2] for row in pagina.rows], ["MARIA JOSE", "MARIA SILVA"])

    def test_busca_ordena_por_relevancia_e_nome(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(
                """INSERT INTO clientes
                   (numero_ficha,codigo,nome,saldo_devedor,limite,telefone,cpf,rg,endereco,observacoes,favorito)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    (40, "C40", "GUSTAVO SILVA", 0, 0, "", "", "", "", "", 0),
                    (41, "C41", "GUSTAVO ARAUJO", 0, 0, "", "", "", "", "", 0),
                    (42, "C42", "MARIA GUSMAO", 0, 0, "", "", "", "", "", 0),
                    (43, "C43", "AUGUSTO BRAGA", 0, 0, "", "", "", "", "", 0),
                    (44, "C44", "ANA GUSTAVO", 0, 0, "", "", "", "", "", 0),
                    (45, "C45", "ZELIA GUSMAO", 0, 0, "", "", "", "", "", 0),
                ],
            )
            conn.commit()
        finally:
            conn.close()
        pagina = self.repo.list_page("gus")
        nomes = [row[2] for row in pagina.rows]
        self.assertLess(nomes.index("GUSTAVO ARAUJO"), nomes.index("MARIA GUSMAO"))
        self.assertLess(nomes.index("GUSTAVO SILVA"), nomes.index("MARIA GUSMAO"))
        self.assertLess(nomes.index("ANA GUSTAVO"), nomes.index("MARIA GUSMAO"))
        self.assertLess(nomes.index("MARIA GUSMAO"), nomes.index("ZELIA GUSMAO"))
        self.assertLess(nomes.index("MARIA GUSMAO"), nomes.index("AUGUSTO BRAGA"))

    def test_sugestoes_de_venda_priorizam_posicao_no_nome(self) -> None:
        sugestoes = self.repo.search_sales_suggestions("jose")
        self.assertEqual([item.nome for item in sugestoes], ["MARIA JOSE"])
        self.assertEqual(sugestoes[0].numero_ficha, 30)

    def test_sugestoes_de_venda_encontram_codigo_ficha_cpf_e_telefone(self) -> None:
        self.assertEqual(self.repo.search_sales_suggestions("C10")[0].id, 2)
        self.assertEqual(self.repo.search_sales_suggestions("20")[0].id, 1)
        self.assertEqual(self.repo.search_sales_suggestions("333.333")[0].id, 3)
        self.assertEqual(self.repo.search_sales_suggestions("222")[0].id, 1)

    def test_sugestoes_de_venda_validam_limite_e_termo_vazio(self) -> None:
        self.assertEqual(self.repo.search_sales_suggestions(""), [])
        self.assertEqual(len(self.repo.search_sales_suggestions("maria", limit=1)), 1)

    def test_sugestao_exata_nao_e_perdida_apos_centenas_de_parciais(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(
                """INSERT INTO clientes
                   (numero_ficha,codigo,nome,saldo_devedor,limite,telefone,cpf,rg,endereco,observacoes,favorito)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                ((1000 + index, f"P123-{index:03d}", f"PARCIAL 123 {index:03d}", 0, 0,
                  "", "", "", "", "", 0) for index in range(250)),
            )
            conn.execute(
                """INSERT INTO clientes
                   (numero_ficha,codigo,nome,saldo_devedor,limite,telefone,cpf,rg,endereco,observacoes,favorito)
                   VALUES(123,'EXATO','NOME REPETIDO',0,0,'','','','','',0)"""
            )
            conn.execute(
                """INSERT INTO clientes
                   (numero_ficha,codigo,nome,saldo_devedor,limite,telefone,cpf,rg,endereco,observacoes,favorito)
                   VALUES(9999,'DUP','NOME REPETIDO',0,0,'','','','','',0)"""
            )
            conn.commit()
        finally:
            conn.close()
        suggestions = self.repo.search_sales_suggestions("123", limit=30)
        self.assertEqual(suggestions[0].numero_ficha, 123)
        self.assertLessEqual(len(suggestions), 30)
        self.assertEqual(len({item.id for item in suggestions}), len(suggestions))

    def test_resolve_referencia_de_venda_com_travessao(self) -> None:
        cliente = self.repo.resolve_sales_reference("20 — MARIA SILVA")
        self.assertIsNotNone(cliente)
        self.assertEqual(cliente.id, 1)

    def test_resolve_referencia_de_venda_por_codigo_ou_ficha(self) -> None:
        self.assertEqual(self.repo.resolve_sales_reference("C10").id, 2)
        self.assertEqual(self.repo.resolve_sales_reference("10").id, 2)

    def test_resolve_referencia_inexistente_sem_fallback_perigoso(self) -> None:
        self.assertIsNone(self.repo.resolve_sales_reference("999 — NINGUEM"))

    def test_alternar_favorito_atualiza_cliente_e_historico_na_mesma_transacao(self) -> None:
        self.assertTrue(self.repo.toggle_favorite(2, event_date="02/08/2026 21:30:00"))
        with closing(sqlite3.connect(self.db_path)) as conn:
            favorito = conn.execute("SELECT favorito FROM clientes WHERE id=2").fetchone()[0]
            historico = conn.execute(
                "SELECT evento, detalhes, data FROM historico_clientes WHERE cliente_id=2"
            ).fetchone()
        self.assertEqual(favorito, 1)
        self.assertEqual(historico, ("FAVORITO", "Cliente marcado como favorito.", "02/08/2026 21:30:00"))

        self.assertFalse(self.repo.toggle_favorite(2, event_date="02/08/2026 21:31:00"))
        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(conn.execute("SELECT favorito FROM clientes WHERE id=2").fetchone()[0], 0)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM historico_clientes WHERE cliente_id=2").fetchone()[0],
                2,
            )

    def test_alternar_favorito_rejeita_cliente_inexistente_sem_gravar_historico(self) -> None:
        with self.assertRaisesRegex(ValueError, "Cliente não encontrado"):
            self.repo.toggle_favorite(999)
        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM historico_clientes").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
