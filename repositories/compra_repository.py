from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable

from database import DatabaseManager
from repositories.decimal_storage import DecimalStorage


class CompraRepository:
    """Persistência dos pedidos e recebimentos de compra."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    @staticmethod
    def _decimalize(row: dict[str, Any], *fields: str) -> dict[str, Any]:
        for field in fields:
            if field in row:
                row[field] = DecimalStorage.to_decimal(row[field], field=field)
        return row

    def listar_fornecedores(self, somente_ativos: bool = True) -> list[dict[str, Any]]:
        filtro = "WHERE ativo=1" if somente_ativos else ""
        rows = self.database.fetch_all(
            f"""
            SELECT id,nome_fantasia,razao_social,cnpj,ativo
            FROM fornecedores
            {filtro}
            ORDER BY COALESCE(NULLIF(nome_fantasia,''),razao_social), id
            """
        )
        return [dict(row) for row in rows]

    def listar_produtos_compra(self, fornecedor_id: int | None = None) -> list[dict[str, Any]]:
        parametros: list[Any] = []
        filtro = "WHERE p.ativo=1 AND p.controla_estoque=1 AND COALESCE(p.tipo_produto,'PRODUTO')<>'SERVICO'"
        if fornecedor_id is not None:
            filtro += " AND (p.fornecedor_id=? OR p.fornecedor_id IS NULL)"
            parametros.append(int(fornecedor_id))
        rows = self.database.fetch_all(
            f"""
            SELECT p.id,p.codigo,p.nome,COALESCE(NULLIF(TRIM(p.preco_custo_decimal),''), CAST(COALESCE(p.preco_custo,0) AS TEXT)) AS preco_custo,
                   COALESCE(p.estoque_atual,0) AS estoque_atual,p.fornecedor_id
            FROM produtos p
            {filtro}
            ORDER BY p.nome,p.codigo
            """,
            tuple(parametros),
        )
        return [self._decimalize(dict(row), "preco_custo") for row in rows]

    def buscar_fornecedor(self, fornecedor_id: int, connection=None) -> dict[str, Any] | None:
        sql = "SELECT id,nome_fantasia,razao_social,ativo FROM fornecedores WHERE id=?"
        row = (connection.execute(sql, (int(fornecedor_id),)).fetchone()
               if connection is not None else self.database.fetch_one(sql, (int(fornecedor_id),)))
        return dict(row) if row else None

    def buscar_produto(self, produto_id: int, connection=None) -> dict[str, Any] | None:
        sql = """
            SELECT id,codigo,nome,tipo_produto,controla_estoque,ativo,
                   COALESCE(estoque_atual,0) AS estoque_atual,
                   preco_custo_decimal AS preco_custo_canonico, COALESCE(preco_custo,0) AS preco_custo_legado,
                   fator_conversao_decimal AS fator_conversao_canonico, COALESCE(fator_conversao,1) AS fator_conversao_legado,
                   fornecedor_id
            FROM produtos WHERE id=?
        """
        row = (connection.execute(sql, (int(produto_id),)).fetchone()
               if connection is not None else self.database.fetch_one(sql, (int(produto_id),)))
        
        if not row:
            return None
        result=dict(row)
        result["preco_custo"]=DecimalStorage.read(result.pop("preco_custo_canonico",None),result.pop("preco_custo_legado",0),field="preco_custo")
        result["fator_conversao"]=DecimalStorage.read(result.pop("fator_conversao_canonico",None),result.pop("fator_conversao_legado",1),field="fator_conversao")
        return result

    def criar_pedido(
        self,
        *,
        fornecedor_id: int,
        observacao: str,
        usuario: str,
        itens: Iterable[dict[str, Any]],
        connection,
    ) -> int:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = connection.execute(
            """
            INSERT INTO pedidos_compra
                (fornecedor_id,status,observacao,usuario,criado_em,atualizado_em)
            VALUES(?, 'ABERTO', ?, ?, ?, ?)
            """,
            (int(fornecedor_id), str(observacao or ""), str(usuario or "Sistema"), agora, agora),
        )
        pedido_id = int(cursor.lastrowid)
        for item in itens:
            connection.execute(
                """
                INSERT INTO pedido_compra_itens
                    (pedido_id,produto_id,quantidade_pedida,quantidade_recebida,
                     custo_unitario,valor_total,custo_unitario_decimal,valor_total_decimal,observacao)
                VALUES(?,?,?,0,?,?,?,?,?)
                """,
                (
                    pedido_id,
                    int(item["produto_id"]),
                    float(item["quantidade"]),
                    DecimalStorage.legacy_real(item["custo_unitario"], field="custo unitário do pedido"),
                    DecimalStorage.legacy_real(item["valor_total"], field="valor total do pedido"),
                    DecimalStorage.canonical(item["custo_unitario"], field="custo unitário do pedido"),
                    DecimalStorage.canonical(item["valor_total"], field="valor total do pedido"),
                    str(item.get("observacao") or ""),
                ),
            )
        return pedido_id

    def obter_pedido(self, pedido_id: int, connection=None) -> dict[str, Any] | None:
        sql = """
            SELECT p.*, f.nome_fantasia AS fornecedor_nome, f.cnpj AS fornecedor_cnpj
            FROM pedidos_compra p
            JOIN fornecedores f ON f.id=p.fornecedor_id
            WHERE p.id=?
        """
        row = (connection.execute(sql, (int(pedido_id),)).fetchone()
               if connection is not None else self.database.fetch_one(sql, (int(pedido_id),)))
        if not row:
            return None
        pedido = dict(row)
        pedido["itens"] = self.listar_itens(int(pedido_id), connection)
        return pedido

    def listar_itens(self, pedido_id: int, connection=None) -> list[dict[str, Any]]:
        sql = """
            SELECT i.*,
                   COALESCE(NULLIF(TRIM(i.custo_unitario_decimal),''), CAST(i.custo_unitario AS TEXT)) AS custo_unitario_canonico,
                   COALESCE(NULLIF(TRIM(i.valor_total_decimal),''), CAST(i.valor_total AS TEXT)) AS valor_total_canonico,
                   p.codigo, p.nome,
                   (i.quantidade_pedida-i.quantidade_recebida) AS quantidade_pendente
            FROM pedido_compra_itens i
            JOIN produtos p ON p.id=i.produto_id
            WHERE i.pedido_id=? ORDER BY i.id
        """
        rows = (connection.execute(sql, (int(pedido_id),)).fetchall()
                if connection is not None else self.database.fetch_all(sql, (int(pedido_id),)))
        result = []
        for row in rows:
            item = dict(row)
            item["custo_unitario"] = DecimalStorage.read(
                item.get("custo_unitario_canonico"), item.get("custo_unitario", 0), field="custo_unitario"
            )
            item["valor_total"] = DecimalStorage.read(
                item.get("valor_total_canonico"), item.get("valor_total", 0), field="valor_total"
            )
            result.append(item)
        return result

    def listar_pedidos(self, status: str | None = None, limite: int = 200) -> list[dict[str, Any]]:
        parametros: list[Any] = []
        filtro = ""
        if status:
            filtro = "WHERE p.status=?"
            parametros.append(str(status).upper())
        parametros.append(max(1, int(limite)))
        rows = self.database.fetch_all(
            f"""
            SELECT p.id,p.status,p.observacao,p.usuario,p.criado_em,p.atualizado_em,
                   f.nome_fantasia AS fornecedor_nome,
                   COALESCE(SUM(i.quantidade_pedida-i.quantidade_recebida),0) AS quantidade_pendente
            FROM pedidos_compra p
            JOIN fornecedores f ON f.id=p.fornecedor_id
            LEFT JOIN pedido_compra_itens i ON i.pedido_id=p.id
            {filtro}
            GROUP BY p.id
            ORDER BY p.id DESC LIMIT ?
            """,
            tuple(parametros),
        )
        result=[]
        for row in rows:
            pedido=dict(row)
            itens=self.listar_itens(int(pedido["id"]))
            pedido["valor_total"]=sum((item["valor_total"] for item in itens), Decimal("0"))
            result.append(pedido)
        return result

    def registrar_recebimento(
        self,
        *,
        pedido_id: int,
        documento: str,
        observacao: str,
        usuario: str,
        itens: Iterable[dict[str, Any]],
        connection,
    ) -> int:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = connection.execute(
            """
            INSERT INTO recebimentos_compra
                (pedido_id,documento,observacao,usuario,data_recebimento)
            VALUES(?,?,?,?,?)
            """,
            (int(pedido_id), str(documento or ""), str(observacao or ""), str(usuario or "Sistema"), agora),
        )
        recebimento_id = int(cursor.lastrowid)
        for item in itens:
            connection.execute(
                """
                INSERT INTO recebimento_compra_itens
                    (recebimento_id,pedido_item_id,produto_id,quantidade,custo_unitario,valor_total,
                     custo_unitario_decimal,valor_total_decimal)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    recebimento_id,
                    int(item["pedido_item_id"]),
                    int(item["produto_id"]),
                    float(item["quantidade"]),
                    DecimalStorage.legacy_real(item["custo_unitario"], field="custo unitário do recebimento"),
                    DecimalStorage.legacy_real(item["valor_total"], field="valor total do recebimento"),
                    DecimalStorage.canonical(item["custo_unitario"], field="custo unitário do recebimento"),
                    DecimalStorage.canonical(item["valor_total"], field="valor total do recebimento"),
                ),
            )
            connection.execute(
                """
                UPDATE pedido_compra_itens
                SET quantidade_recebida=quantidade_recebida+?
                WHERE id=?
                """,
                (float(item["quantidade"]), int(item["pedido_item_id"])),
            )
        return recebimento_id

    def atualizar_status_pedido(self, pedido_id: int, connection) -> str:
        row = connection.execute(
            """
            SELECT
                SUM(quantidade_pedida) AS pedida,
                SUM(quantidade_recebida) AS recebida
            FROM pedido_compra_itens WHERE pedido_id=?
            """,
            (int(pedido_id),),
        ).fetchone()
        pedida = float(row["pedida"] or 0)
        recebida = float(row["recebida"] or 0)
        if recebida <= 0:
            status = "ABERTO"
        elif recebida + 1e-9 >= pedida:
            status = "RECEBIDO"
        else:
            status = "PARCIAL"
        connection.execute(
            "UPDATE pedidos_compra SET status=?, atualizado_em=? WHERE id=?",
            (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(pedido_id)),
        )
        return status

    def atualizar_custo_produto(self, produto_id: int, custo_unitario_estoque, fornecedor_id: int, connection) -> None:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        custo_real, custo_decimal = DecimalStorage.pair(custo_unitario_estoque, field="custo unitário da compra")
        connection.execute(
            """
            UPDATE produtos
            SET preco_custo=?, preco_custo_decimal=?, fornecedor_id=COALESCE(fornecedor_id,?), atualizado_em=?
            WHERE id=?
            """,
            (custo_real, custo_decimal, int(fornecedor_id), agora, int(produto_id)),
        )
        connection.execute(
            """
            INSERT INTO produto_fornecedores
                (produto_id,fornecedor_id,codigo_fornecedor,unidade_fornecedor,
                 fator_conversao,ultimo_custo,fator_conversao_decimal,ultimo_custo_decimal,ultima_compra,ativo)
            VALUES(?,?, '', 'UN', 1, ?, '1', ?, ?, 1)
            ON CONFLICT(produto_id,fornecedor_id,codigo_fornecedor)
            DO UPDATE SET ultimo_custo=excluded.ultimo_custo,
                          ultimo_custo_decimal=excluded.ultimo_custo_decimal,
                          fator_conversao_decimal=excluded.fator_conversao_decimal,
                          ultima_compra=excluded.ultima_compra,
                          ativo=1
            """,
            (int(produto_id), int(fornecedor_id), custo_real, custo_decimal, agora),
        )
