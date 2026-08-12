from __future__ import annotations

from datetime import datetime
from typing import Any

from database import DatabaseManager


class EstoqueRepository:
    """Persistência de saldos e movimentações de estoque."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def buscar_produto(self, produto_id: int, connection=None) -> dict[str, Any] | None:
        sql = """
            SELECT id, codigo, nome, tipo_produto, controla_estoque,
                   COALESCE(estoque_atual, 0) AS estoque_atual,
                   COALESCE(estoque_minimo, 0) AS estoque_minimo,
                   COALESCE(permite_estoque_negativo, 0) AS permite_estoque_negativo
            FROM produtos
            WHERE id=?
        """
        if connection is not None:
            row = connection.execute(sql, (int(produto_id),)).fetchone()
        else:
            row = self.database.fetch_one(sql, (int(produto_id),))
        return dict(row) if row else None

    def atualizar_saldo(self, produto_id: int, novo_saldo: float, connection) -> None:
        connection.execute(
            "UPDATE produtos SET estoque_atual=?, atualizado_em=? WHERE id=?",
            (float(novo_saldo), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(produto_id)),
        )

    def registrar_movimentacao(
        self,
        *,
        produto_id: int,
        tipo: str,
        quantidade: float,
        saldo_anterior: float,
        saldo_atual: float,
        origem: str,
        origem_id: str = "",
        motivo: str = "",
        usuario: str = "Sistema",
        connection,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO estoque_movimentacoes
                (produto_id,tipo,quantidade,saldo_anterior,saldo_atual,origem,origem_id,motivo,usuario,data)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                int(produto_id), str(tipo), float(quantidade), float(saldo_anterior),
                float(saldo_atual), str(origem), str(origem_id or ""), str(motivo or ""),
                str(usuario or "Sistema"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        return int(cursor.lastrowid)

    def buscar_movimentacao_por_origem(self, origem: str, origem_id: str, produto_id: int, connection=None):
        sql = """
            SELECT * FROM estoque_movimentacoes
            WHERE origem=? AND origem_id=? AND produto_id=?
            ORDER BY id DESC LIMIT 1
        """
        parametros = (str(origem), str(origem_id), int(produto_id))
        if connection is not None:
            row = connection.execute(sql, parametros).fetchone()
        else:
            row = self.database.fetch_one(sql, parametros)
        return dict(row) if row else None

    def listar_movimentacoes(self, produto_id: int, limite: int = 200) -> list[dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT id,produto_id,tipo,quantidade,saldo_anterior,saldo_atual,
                   origem,origem_id,motivo,usuario,data
            FROM estoque_movimentacoes
            WHERE produto_id=?
            ORDER BY id DESC LIMIT ?
            """,
            (int(produto_id), max(1, int(limite))),
        )
        return [dict(row) for row in rows]


    def listar_produtos_estoque(self, connection=None) -> list[dict[str, Any]]:
        sql = """
            SELECT id,codigo,nome,COALESCE(estoque_atual,0) AS estoque_atual,
                   COALESCE(estoque_minimo,0) AS estoque_minimo,
                   COALESCE(permite_estoque_negativo,0) AS permite_estoque_negativo
            FROM produtos
            WHERE ativo=1 AND controla_estoque=1 AND tipo_produto<>'SERVICO'
            ORDER BY nome COLLATE NOCASE, id
        """
        rows = connection.execute(sql).fetchall() if connection is not None else self.database.fetch_all(sql)
        return [dict(row) for row in rows]

    def buscar_movimentacao(self, movimentacao_id: int, connection=None) -> dict[str, Any] | None:
        sql = """
            SELECT id,produto_id,tipo,quantidade,saldo_anterior,saldo_atual,
                   origem,origem_id,motivo,usuario,data
            FROM estoque_movimentacoes WHERE id=?
        """
        row = (connection.execute(sql, (int(movimentacao_id),)).fetchone()
               if connection is not None else self.database.fetch_one(sql, (int(movimentacao_id),)))
        return dict(row) if row else None

    def ultima_movimentacao(self, produto_id: int, connection=None) -> dict[str, Any] | None:
        sql = """
            SELECT id,produto_id,tipo,quantidade,saldo_anterior,saldo_atual,
                   origem,origem_id,motivo,usuario,data
            FROM estoque_movimentacoes WHERE produto_id=? ORDER BY id DESC LIMIT 1
        """
        row = (connection.execute(sql, (int(produto_id),)).fetchone()
               if connection is not None else self.database.fetch_one(sql, (int(produto_id),)))
        return dict(row) if row else None

    def listar_abaixo_minimo(self) -> list[dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT id,codigo,nome,COALESCE(estoque_atual,0) AS estoque_atual,
                   COALESCE(estoque_minimo,0) AS estoque_minimo
            FROM produtos
            WHERE ativo=1 AND controla_estoque=1
              AND COALESCE(estoque_atual,0) <= COALESCE(estoque_minimo,0)
            ORDER BY (COALESCE(estoque_minimo,0)-COALESCE(estoque_atual,0)) DESC,
                     nome COLLATE NOCASE
            """
        )
        return [dict(row) for row in rows]
