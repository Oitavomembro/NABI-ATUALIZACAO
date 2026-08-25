from __future__ import annotations

from datetime import datetime
import json
from decimal import Decimal
from typing import Any

from database import DatabaseManager
from repositories.decimal_storage import DecimalStorage


class FinanceiroRepository:
    """Persistência de títulos a pagar/receber e seus pagamentos."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    @staticmethod
    def _has_columns(connection, table: str, *columns: str) -> bool:
        existing = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        return all(column in existing for column in columns)

    @staticmethod
    def _decimalizar(registro: dict[str, Any] | None) -> dict[str, Any] | None:
        if registro is None:
            return None
        convertido = dict(registro)
        pares = (
            ("valor_original", "valor_original_decimal"),
            ("valor_pago", "valor_pago_decimal"),
            ("valor", "valor_decimal"),
        )
        for campo, canonico in pares:
            if campo in convertido:
                convertido[campo] = DecimalStorage.read(
                    convertido.get(canonico), convertido[campo], field=campo.replace("_", " ")
                )
        if "valor_original" in convertido and "valor_pago" in convertido:
            convertido["saldo_aberto"] = convertido["valor_original"] - convertido["valor_pago"]
        elif "saldo_aberto" in convertido:
            convertido["saldo_aberto"] = DecimalStorage.to_decimal(
                convertido["saldo_aberto"], field="saldo aberto"
            )
        return convertido

    @classmethod
    def _decimalizar_lista(cls, rows) -> list[dict[str, Any]]:
        return [cls._decimalizar(dict(row)) for row in rows]

    def criar_titulo(
        self,
        *,
        tipo: str,
        origem: str,
        origem_id: str,
        pessoa_id: int | None,
        pessoa_nome: str,
        documento: str,
        descricao: str,
        data_emissao: str,
        data_vencimento: str,
        valor_original: Decimal,
        observacao: str,
        connection,
    ) -> int:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        legacy, canonical = DecimalStorage.pair(valor_original, field="valor original")
        if self._has_columns(connection, "titulos_financeiros", "valor_original_decimal", "valor_pago_decimal"):
            cursor = connection.execute(
                """
                INSERT INTO titulos_financeiros
                    (tipo,origem,origem_id,pessoa_id,pessoa_nome,documento,descricao,
                     data_emissao,data_vencimento,valor_original,valor_original_decimal,
                     valor_pago,valor_pago_decimal,status,observacao,criado_em,atualizado_em)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,0,'0','ABERTO',?,?,?)
                """,
                (tipo, origem, origem_id, pessoa_id, pessoa_nome, documento, descricao,
                 data_emissao, data_vencimento, legacy, canonical, observacao, agora, agora),
            )
        else:
            cursor = connection.execute(
                """
                INSERT INTO titulos_financeiros
                    (tipo,origem,origem_id,pessoa_id,pessoa_nome,documento,descricao,
                     data_emissao,data_vencimento,valor_original,valor_pago,status,
                     observacao,criado_em,atualizado_em)
                VALUES(?,?,?,?,?,?,?,?,?,?,0,'ABERTO',?,?,?)
                """,
                (tipo, origem, origem_id, pessoa_id, pessoa_nome, documento, descricao,
                 data_emissao, data_vencimento, legacy, observacao, agora, agora),
            )
        return int(cursor.lastrowid)

    def obter_titulo(self, titulo_id: int, connection=None) -> dict[str, Any] | None:
        sql = """
            SELECT *, (valor_original-valor_pago) AS saldo_aberto
            FROM titulos_financeiros WHERE id=?
        """
        row = (connection.execute(sql, (int(titulo_id),)).fetchone()
               if connection is not None else self.database.fetch_one(sql, (int(titulo_id),)))
        return self._decimalizar(dict(row)) if row else None

    def buscar_por_origem(
        self, tipo: str, origem: str, origem_id: str, documento: str = "", connection=None
    ) -> dict[str, Any] | None:
        sql = """
            SELECT *, (valor_original-valor_pago) AS saldo_aberto
            FROM titulos_financeiros
            WHERE tipo=? AND origem=? AND origem_id=? AND documento=? AND status<>'CANCELADO'
            ORDER BY id DESC LIMIT 1
        """
        params = (tipo, origem, origem_id, documento)
        row = (connection.execute(sql, params).fetchone()
               if connection is not None else self.database.fetch_one(sql, params))
        return self._decimalizar(dict(row)) if row else None

    def listar_titulos(
        self,
        *,
        tipo: str | None = None,
        status: str | None = None,
        vencidos: bool = False,
        limite: int = 500,
    ) -> list[dict[str, Any]]:
        filtros: list[str] = []
        parametros: list[Any] = []
        if tipo:
            filtros.append("tipo=?")
            parametros.append(tipo)
        if status:
            filtros.append("status=?")
            parametros.append(status)
        if vencidos:
            filtros.append("data_vencimento<date('now','localtime')")
            filtros.append("status IN ('ABERTO','PARCIAL')")
        where = "WHERE " + " AND ".join(filtros) if filtros else ""
        parametros.append(max(1, int(limite)))
        rows = self.database.fetch_all(
            f"""
            SELECT *, (valor_original-valor_pago) AS saldo_aberto,
                   CASE WHEN data_vencimento<date('now','localtime')
                             AND status IN ('ABERTO','PARCIAL') THEN 1 ELSE 0 END AS vencido
            FROM titulos_financeiros
            {where}
            ORDER BY data_vencimento,id LIMIT ?
            """,
            tuple(parametros),
        )
        return self._decimalizar_lista(rows)

    def listar_titulos_pagina(
        self, *, tipo: str, limite: int, offset: int = 0,
        status: str | None = None, vencidos: bool = False,
        abertos: bool = False, pessoa_id: int | None = None,
        vencimento_de: str | None = None, vencimento_ate: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Lê exatamente uma página, com total completo na mesma consulta SQL."""

        safe_limit = min(max(int(limite), 1), 500)
        safe_offset = max(int(offset), 0)
        filtros = ["tipo=?"]
        parametros: list[Any] = [str(tipo).strip().upper()]
        if status:
            filtros.append("status=?"); parametros.append(str(status).strip().upper())
        if abertos:
            filtros.append("status IN ('ABERTO','PARCIAL')")
        if vencidos:
            filtros.extend(("data_vencimento<date('now','localtime')", "status IN ('ABERTO','PARCIAL')"))
        if pessoa_id is not None:
            filtros.append("pessoa_id=?"); parametros.append(int(pessoa_id))
        if vencimento_de:
            filtros.append("data_vencimento>=?"); parametros.append(str(vencimento_de)[:10])
        if vencimento_ate:
            filtros.append("data_vencimento<=?"); parametros.append(str(vencimento_ate)[:10])
        parametros.extend((safe_limit, safe_offset))
        rows = self.database.fetch_all(
            f"""
            SELECT *, (valor_original-valor_pago) AS saldo_aberto,
                   CASE WHEN data_vencimento<date('now','localtime')
                             AND status IN ('ABERTO','PARCIAL') THEN 1 ELSE 0 END AS vencido,
                   COUNT(*) OVER() AS __total_records
            FROM titulos_financeiros
            WHERE {' AND '.join(filtros)}
            ORDER BY data_vencimento,id LIMIT ? OFFSET ?
            """,
            tuple(parametros),
        )
        converted = self._decimalizar_lista(rows)
        total = int(converted[0].pop("__total_records", 0)) if converted else 0
        for row in converted[1:]:
            row.pop("__total_records", None)
        return converted, total

    def resumo_titulos_abertos(self) -> dict[str, Decimal]:
        row = self.database.fetch_one(
            """
            SELECT
              COALESCE(SUM(CASE WHEN tipo='RECEBER' AND status IN ('ABERTO','PARCIAL') THEN valor_original-valor_pago ELSE 0 END),0) receber,
              COALESCE(SUM(CASE WHEN tipo='RECEBER' AND status IN ('ABERTO','PARCIAL') AND data_vencimento<date('now','localtime') THEN valor_original-valor_pago ELSE 0 END),0) receber_vencido,
              COALESCE(SUM(CASE WHEN tipo='PAGAR' AND status IN ('ABERTO','PARCIAL') THEN valor_original-valor_pago ELSE 0 END),0) pagar,
              COALESCE(SUM(CASE WHEN tipo='PAGAR' AND status IN ('ABERTO','PARCIAL') AND data_vencimento=date('now','localtime') THEN valor_original-valor_pago ELSE 0 END),0) pagar_hoje
            FROM titulos_financeiros
            """
        )
        return {
            "receber": DecimalStorage.to_decimal(row["receber"] if row else 0, field="a receber"),
            "receber_vencido": DecimalStorage.to_decimal(row["receber_vencido"] if row else 0, field="a receber vencido"),
            "pagar": DecimalStorage.to_decimal(row["pagar"] if row else 0, field="a pagar"),
            "pagar_hoje": DecimalStorage.to_decimal(row["pagar_hoje"] if row else 0, field="a pagar hoje"),
        }

    def registrar_pagamento(
        self,
        *,
        titulo_id: int,
        valor: Decimal,
        forma_pagamento: str,
        observacao: str,
        usuario: str,
        data_pagamento: str,
        connection,
    ) -> int:
        legacy, canonical = DecimalStorage.pair(valor, field="valor do pagamento")
        if self._has_columns(connection, "pagamentos_titulos", "valor_decimal"):
            cursor = connection.execute(
                """INSERT INTO pagamentos_titulos
                   (titulo_id,valor,valor_decimal,forma_pagamento,observacao,usuario,data_pagamento)
                   VALUES(?,?,?,?,?,?,?)""",
                (int(titulo_id), legacy, canonical, forma_pagamento, observacao, usuario, data_pagamento),
            )
        else:
            cursor = connection.execute(
                """INSERT INTO pagamentos_titulos
                   (titulo_id,valor,forma_pagamento,observacao,usuario,data_pagamento)
                   VALUES(?,?,?,?,?,?)""",
                (int(titulo_id), legacy, forma_pagamento, observacao, usuario, data_pagamento),
            )
        return int(cursor.lastrowid)

    def atualizar_pagamento_titulo(self, titulo_id: int, novo_valor_pago: Decimal, status: str, connection) -> None:
        legacy, canonical = DecimalStorage.pair(novo_valor_pago, field="valor pago")
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self._has_columns(connection, "titulos_financeiros", "valor_pago_decimal"):
            connection.execute(
                "UPDATE titulos_financeiros SET valor_pago=?, valor_pago_decimal=?, status=?, atualizado_em=? WHERE id=?",
                (legacy, canonical, status, agora, int(titulo_id)),
            )
        else:
            connection.execute(
                "UPDATE titulos_financeiros SET valor_pago=?, status=?, atualizado_em=? WHERE id=?",
                (legacy, status, agora, int(titulo_id)),
            )

    def cancelar_titulo(self, titulo_id: int, connection) -> None:
        connection.execute(
            """
            UPDATE titulos_financeiros
            SET status='CANCELADO', atualizado_em=? WHERE id=?
            """,
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(titulo_id)),
        )

    def listar_pagamentos(self, titulo_id: int) -> list[dict[str, Any]]:
        rows = self.database.fetch_all(
            "SELECT * FROM pagamentos_titulos WHERE titulo_id=? ORDER BY id",
            (int(titulo_id),),
        )
        return self._decimalizar_lista(rows)


    def obter_pagamento(self, pagamento_id: int, connection=None) -> dict[str, Any] | None:
        sql = "SELECT * FROM pagamentos_titulos WHERE id=?"
        row = (connection.execute(sql, (int(pagamento_id),)).fetchone()
               if connection is not None else self.database.fetch_one(sql, (int(pagamento_id),)))
        return self._decimalizar(dict(row)) if row else None

    def excluir_pagamento(self, pagamento_id: int, connection) -> None:
        connection.execute("DELETE FROM pagamentos_titulos WHERE id=?", (int(pagamento_id),))

    def atualizar_valor_original(self, titulo_id: int, valor_original: Decimal, connection) -> None:
        legacy, canonical = DecimalStorage.pair(valor_original, field="valor original")
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self._has_columns(connection, "titulos_financeiros", "valor_original_decimal"):
            connection.execute(
                "UPDATE titulos_financeiros SET valor_original=?, valor_original_decimal=?, atualizado_em=? WHERE id=?",
                (legacy, canonical, agora, int(titulo_id)),
            )
        else:
            connection.execute(
                "UPDATE titulos_financeiros SET valor_original=?, atualizado_em=? WHERE id=?",
                (legacy, agora, int(titulo_id)),
            )

    def listar_todos_pagamentos(self) -> list[dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT p.*, t.tipo, t.descricao, t.pessoa_nome, t.documento, t.status AS titulo_status
            FROM pagamentos_titulos p
            JOIN titulos_financeiros t ON t.id=p.titulo_id
            ORDER BY p.data_pagamento DESC,p.id DESC
            """
        )
        return self._decimalizar_lista(rows)

    def listar_pagamentos_periodo(self, data_inicial: str, data_final: str) -> list[dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT p.*, t.tipo, t.descricao, t.origem, t.origem_id, t.documento, t.pessoa_nome
            FROM pagamentos_titulos p
            JOIN titulos_financeiros t ON t.id=p.titulo_id
            WHERE p.data_pagamento BETWEEN ? AND ? AND t.status<>'CANCELADO'
            ORDER BY p.data_pagamento,p.id
            """,
            (data_inicial, data_final),
        )
        return self._decimalizar_lista(rows)

    def resumo_pagamentos_periodo(self, data_inicial: str, data_final: str) -> dict[str, Decimal]:
        row = self.database.fetch_one(
            """
            SELECT
              COALESCE(SUM(CASE WHEN t.tipo='RECEBER' THEN p.valor ELSE 0 END),0) AS recebido,
              COALESCE(SUM(CASE WHEN t.tipo='PAGAR' THEN p.valor ELSE 0 END),0) AS pago
            FROM pagamentos_titulos p
            JOIN titulos_financeiros t ON t.id=p.titulo_id
            WHERE p.data_pagamento BETWEEN ? AND ? AND t.status<>'CANCELADO'
            """,
            (data_inicial, data_final),
        )
        return {
            "recebido": DecimalStorage.to_decimal(row["recebido"] if row else 0, field="recebido"),
            "pago": DecimalStorage.to_decimal(row["pago"] if row else 0, field="pago"),
        }

    def listar_titulos_periodo(self, data_inicial: str, data_final: str) -> list[dict[str, Any]]:
        rows = self.database.fetch_all(
            """
            SELECT *, (valor_original-valor_pago) AS saldo_aberto
            FROM titulos_financeiros
            WHERE data_emissao BETWEEN ? AND ? AND status<>'CANCELADO'
            ORDER BY data_emissao,id
            """,
            (data_inicial, data_final),
        )
        return self._decimalizar_lista(rows)


    def listar_movimentacoes_legadas_periodo(self, data_inicial: str, data_final: str) -> list[dict[str, Any]]:
        """Retorna movimentos do módulo legado que ainda não possuem título financeiro."""
        tabelas = {row["name"] for row in self.database.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")}
        if "movimentacoes" not in tabelas:
            return []
        colunas = {row["name"] for row in self.database.fetch_all("PRAGMA table_info(movimentacoes)")}
        obrigatorias = {"id", "tipo", "descricao", "valor", "data", "status_pagamento"}
        if not obrigatorias.issubset(colunas):
            return []
        origem = "COALESCE(origem_sistema,'') AS origem_sistema, COALESCE(origem_id,'') AS origem_id," if {"origem_sistema", "origem_id"}.issubset(colunas) else "'' AS origem_sistema, '' AS origem_id,"
        forma = "COALESCE(forma_pagamento,'') AS forma_pagamento," if "forma_pagamento" in colunas else "'' AS forma_pagamento,"
        rows = self.database.fetch_all(
            f"""
            SELECT id, UPPER(COALESCE(tipo,'')) AS tipo, COALESCE(descricao,'') AS descricao,
                   COALESCE(valor,0) AS valor, substr(COALESCE(data,''),1,10) AS data_movimento,
                   UPPER(COALESCE(status_pagamento,'')) AS status_pagamento,
                   {origem} {forma}
                   COALESCE(cliente_id,0) AS cliente_id
            FROM movimentacoes
            WHERE substr(COALESCE(data,''),1,10) BETWEEN ? AND ?
              AND UPPER(COALESCE(status_pagamento,'')) <> 'CANCELADO'
              AND NOT (
                    UPPER(COALESCE(tipo,''))='COMPRA'
                    AND EXISTS (
                        SELECT 1 FROM titulos_financeiros tf
                        WHERE tf.origem='VENDA' AND tf.origem_id=CAST(movimentacoes.id AS TEXT)
                          AND tf.status<>'CANCELADO'
                    )
              )
            ORDER BY data_movimento,id
            """,
            (data_inicial, data_final),
        )
        return [dict(row) for row in rows]


    def tabela_existe(self, nome: str, connection) -> bool:
        return connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (str(nome),)
        ).fetchone() is not None

    def colunas_tabela(self, nome: str, connection) -> set[str]:
        return {
            str(row[1]).casefold()
            for row in connection.execute(f"PRAGMA table_info({nome})").fetchall()
        }

    def carregar_estado_venda_legada(self, movimentacao_id: int, connection) -> dict[str, Any] | None:
        tabelas = ("movimentacoes", "parcelas", "clientes", "configuracoes")
        if not all(self.tabela_existe(tabela, connection) for tabela in tabelas):
            return None
        movement_columns = self.colunas_tabela("movimentacoes", connection)
        row = connection.execute(
            "SELECT id,cliente_id,status_pagamento,COALESCE(valor_aberto,valor,0) AS valor_aberto, "
            + ("valor_aberto_decimal" if "valor_aberto_decimal" in movement_columns else "NULL")
            + " AS valor_aberto_decimal FROM movimentacoes WHERE id=?",
            (int(movimentacao_id),),
        ).fetchone()
        if not row:
            return None
        movimento = dict(row)
        parcel_columns = self.colunas_tabela("parcelas", connection)
        parcelas = [dict(item) for item in connection.execute(
            "SELECT id,status,COALESCE(valor_pago,0) AS valor_pago,"
            + ("valor_pago_decimal" if "valor_pago_decimal" in parcel_columns else "NULL")
            + " AS valor_pago_decimal,COALESCE(data_pagamento,'') AS data_pagamento,"
              "COALESCE(atraso_registrado,0) AS atraso_registrado,"
              "COALESCE(valor_parcela,0) AS valor_parcela,"
            + ("valor_parcela_decimal" if "valor_parcela_decimal" in parcel_columns else "NULL")
            + " AS valor_parcela_decimal,vencimento FROM parcelas "
              "WHERE movimentacao_id=? ORDER BY numero_parcela,id",
            (int(movimentacao_id),),
        ).fetchall()]
        cliente = None
        customer_columns: set[str] = set()
        if movimento.get("cliente_id") is not None:
            customer_columns = self.colunas_tabela("clientes", connection)
            cliente_row = connection.execute(
                "SELECT id,COALESCE(saldo_devedor,0) AS saldo_devedor, "
                + ("saldo_devedor_decimal" if "saldo_devedor_decimal" in customer_columns else "NULL")
                + " AS saldo_devedor_decimal FROM clientes WHERE id=?",
                (int(movimento["cliente_id"]),),
            ).fetchone()
            cliente = dict(cliente_row) if cliente_row else None
        return {
            "movimento": movimento, "parcelas": parcelas, "cliente": cliente,
            "movement_columns": movement_columns, "parcel_columns": parcel_columns,
            "customer_columns": customer_columns,
        }

    def atualizar_parcela_legada(
        self, parcela_id: int, *, valor_pago: Decimal, status: str, data_pagamento: str,
        atraso: int, possui_decimal: bool, connection
    ) -> None:
        legacy, canonical = DecimalStorage.pair(valor_pago, field="valor pago da parcela")
        if possui_decimal:
            connection.execute(
                "UPDATE parcelas SET valor_pago=?,valor_pago_decimal=?,status=?,data_pagamento=?,atraso_registrado=? WHERE id=?",
                (legacy, canonical, status, data_pagamento, int(atraso), int(parcela_id)),
            )
        else:
            connection.execute(
                "UPDATE parcelas SET valor_pago=?,status=?,data_pagamento=?,atraso_registrado=? WHERE id=?",
                (legacy, status, data_pagamento, int(atraso), int(parcela_id)),
            )

    def atualizar_movimento_legado(
        self, movimentacao_id: int, *, valor_aberto: Decimal, status: str,
        possui_decimal: bool, connection
    ) -> None:
        legacy, canonical = DecimalStorage.pair(valor_aberto, field="valor em aberto")
        if possui_decimal:
            connection.execute(
                "UPDATE movimentacoes SET valor_aberto=?,valor_aberto_decimal=?,status_pagamento=? WHERE id=?",
                (legacy, canonical, status, int(movimentacao_id)),
            )
        else:
            connection.execute(
                "UPDATE movimentacoes SET valor_aberto=?,status_pagamento=? WHERE id=?",
                (legacy, status, int(movimentacao_id)),
            )

    def atualizar_cliente_legado(
        self, cliente_id: int, *, saldo_devedor: Decimal, possui_decimal: bool, connection
    ) -> None:
        legacy, canonical = DecimalStorage.pair(saldo_devedor, field="saldo devedor")
        if possui_decimal:
            connection.execute(
                "UPDATE clientes SET saldo_devedor=?,saldo_devedor_decimal=? WHERE id=?",
                (legacy, canonical, int(cliente_id)),
            )
        else:
            connection.execute(
                "UPDATE clientes SET saldo_devedor=? WHERE id=?",
                (legacy, int(cliente_id)),
            )

    def existe_pagamento_posterior(self, titulo_id: int, pagamento_id: int, connection) -> bool:
        return connection.execute(
            "SELECT 1 FROM pagamentos_titulos WHERE titulo_id=? AND id>? LIMIT 1",
            (int(titulo_id), int(pagamento_id)),
        ).fetchone() is not None

    def excluir_configuracao(self, chave: str, connection) -> None:
        connection.execute("DELETE FROM configuracoes WHERE chave=?", (str(chave),))

    def buscar_titulo_venda_aberto(self, venda_id: int, connection) -> dict[str, Any] | None:
        row = connection.execute(
            """SELECT *, (valor_original-valor_pago) AS saldo_aberto
               FROM titulos_financeiros
               WHERE tipo='RECEBER' AND origem='VENDA' AND origem_id=?
                 AND status<>'CANCELADO' ORDER BY id DESC LIMIT 1""",
            (str(int(venda_id)),),
        ).fetchone()
        return self._decimalizar(dict(row)) if row else None

    def listar_titulos_origem_ativos(
        self, *, tipo: str, origem: str, origem_id: str | int, connection
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            """SELECT id,valor_pago,status FROM titulos_financeiros
               WHERE tipo=? AND origem=? AND origem_id=? AND status<>'CANCELADO'
               ORDER BY id""",
            (str(tipo).strip().upper(), str(origem).strip().upper(), str(origem_id).strip()),
        ).fetchall()
        return self._decimalizar_lista([dict(row) for row in rows])

    def obter_configuracao(self, chave: str, connection=None) -> str | None:
        sql = "SELECT valor FROM configuracoes WHERE chave=?"
        row = connection.execute(sql, (chave,)).fetchone() if connection is not None else self.database.fetch_one(sql, (chave,))
        return str(row["valor"]) if row and row["valor"] is not None else None

    def salvar_configuracao(self, chave: str, valor: str, connection) -> None:
        connection.execute(
            "INSERT INTO configuracoes(chave,valor) VALUES(?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (chave, valor),
        )

    def obter_configuracao_json(self, chave: str, connection=None) -> dict[str, Any]:
        bruto = self.obter_configuracao(chave, connection)
        if not bruto:
            return {}
        try:
            dados = json.loads(bruto)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return dados if isinstance(dados, dict) else {}

    def salvar_configuracao_json(self, chave: str, dados: dict[str, Any], connection) -> None:
        self.salvar_configuracao(
            chave,
            json.dumps(dados, ensure_ascii=False, sort_keys=True),
            connection,
        )

    def registrar_auditoria(
        self, *, usuario: str, acao: str, objeto: str, detalhes: str = "", connection
    ) -> None:
        connection.execute(
            """INSERT INTO auditoria
               (data,usuario,modulo,acao,objeto,detalhes,resultado)
               VALUES(datetime('now','localtime'),?,'Financeiro',?,?,?,'SUCESSO')""",
            (str(usuario or "Sistema"), str(acao), str(objeto), str(detalhes or "")),
        )

    def pagamento_existe(self, pagamento_id: int, connection=None) -> bool:
        sql = "SELECT 1 FROM pagamentos_titulos WHERE id=?"
        row = (
            connection.execute(sql, (int(pagamento_id),)).fetchone()
            if connection is not None
            else self.database.fetch_one(sql, (int(pagamento_id),))
        )
        return bool(row)

    # Compatibilidade do crediário legado: todo SQL financeiro fica no repositório.
    def obter_cliente_crediario(self, cliente_id: int, connection=None) -> dict[str, Any] | None:
        def executar(conn):
            colunas = self.colunas_tabela("clientes", conn)
            canonical = "saldo_devedor_decimal" if "saldo_devedor_decimal" in colunas else "NULL"
            row = conn.execute(
                f"SELECT id,nome,COALESCE(saldo_devedor,0) AS saldo_devedor,{canonical} AS saldo_devedor_decimal "
                "FROM clientes WHERE id=?",
                (int(cliente_id),),
            ).fetchone()
            if not row:
                return None
            item = dict(row)
            item["saldo_devedor"] = DecimalStorage.read(
                item.get("saldo_devedor_decimal"), item.get("saldo_devedor", 0), field="saldo devedor"
            )
            return item

        if connection is not None:
            return executar(connection)
        with self.database.session() as conn:
            return executar(conn)

    def listar_compras_abertas_cliente(self, cliente_id: int, connection=None) -> list[dict[str, Any]]:
        def executar(conn):
            colunas = self.colunas_tabela("movimentacoes", conn)
            canonical = "m.valor_aberto_decimal" if "valor_aberto_decimal" in colunas else "NULL"
            rows = conn.execute(
                f"""
                SELECT m.id,COALESCE(m.descricao,'Compra') AS descricao,COALESCE(m.valor,0) AS valor,
                       COALESCE(m.valor_aberto,m.valor,0) AS valor_aberto,{canonical} AS valor_aberto_decimal,
                       COALESCE(m.data,'') AS data
                FROM movimentacoes m
                WHERE m.cliente_id=? AND m.tipo='COMPRA'
                  AND UPPER(COALESCE(m.status_pagamento,''))<>'CANCELADO'
                ORDER BY m.id DESC
                """,
                (int(cliente_id),),
            ).fetchall()
            resultado = []
            for row in rows:
                item = dict(row)
                item["valor"] = DecimalStorage.to_decimal(item["valor"], field="valor da compra")
                item["valor_aberto"] = DecimalStorage.read(
                    item.get("valor_aberto_decimal"), item.get("valor_aberto", 0), field="valor em aberto"
                )
                if item["valor_aberto"] > Decimal("0.001"):
                    resultado.append(item)
            return resultado

        if connection is not None:
            return executar(connection)
        with self.database.session() as conn:
            return executar(conn)

    def listar_parcelas_abertas_cliente(self, cliente_id: int, connection=None) -> list[dict[str, Any]]:
        def executar(conn):
            colunas = self.colunas_tabela("parcelas", conn)
            valor_canonical = "p.valor_parcela_decimal" if "valor_parcela_decimal" in colunas else "NULL"
            pago_canonical = "p.valor_pago_decimal" if "valor_pago_decimal" in colunas else "NULL"
            rows = conn.execute(
                f"""
                SELECT p.id,p.movimentacao_id,p.numero_parcela,p.valor_parcela,{valor_canonical} AS valor_parcela_decimal,
                       COALESCE(p.valor_pago,0) AS valor_pago,{pago_canonical} AS valor_pago_decimal,
                       COALESCE(p.vencimento,'') AS vencimento,COALESCE(p.status,'PENDENTE') AS status,
                       COALESCE(p.dados_confiaveis,1) AS dados_confiaveis
                FROM parcelas p JOIN movimentacoes m ON m.id=p.movimentacao_id
                WHERE m.cliente_id=? AND m.tipo='COMPRA'
                  AND UPPER(COALESCE(m.status_pagamento,''))<>'CANCELADO'
                  AND p.status<>'PAGO'
                ORDER BY m.id DESC,p.numero_parcela,p.id
                """,
                (int(cliente_id),),
            ).fetchall()
            resultado = []
            for row in rows:
                item = dict(row)
                item["valor_parcela"] = DecimalStorage.read(
                    item.get("valor_parcela_decimal"), item.get("valor_parcela", 0), field="valor da parcela"
                )
                item["valor_pago"] = DecimalStorage.read(
                    item.get("valor_pago_decimal"), item.get("valor_pago", 0), field="valor pago"
                )
                resultado.append(item)
            return resultado

        if connection is not None:
            return executar(connection)
        with self.database.session() as conn:
            return executar(conn)

    def carregar_estado_reconciliacao_cliente(self, cliente_id: int, connection) -> dict[str, Any] | None:
        cliente = self.obter_cliente_crediario(int(cliente_id), connection)
        if not cliente:
            return None

        movement_columns = self.colunas_tabela("movimentacoes", connection)
        movement_canonical = (
            "m.valor_aberto_decimal" if "valor_aberto_decimal" in movement_columns else "NULL"
        )
        rows = connection.execute(
            f"""
            SELECT m.id,COALESCE(m.descricao,'Compra') AS descricao,COALESCE(m.valor,0) AS valor,
                   COALESCE(m.valor_aberto,m.valor,0) AS valor_aberto,
                   {movement_canonical} AS valor_aberto_decimal,
                   COALESCE(m.data,'') AS data,COALESCE(m.vencimento,'') AS vencimento,
                   COALESCE(m.status_pagamento,'') AS status_pagamento
            FROM movimentacoes m
            WHERE m.cliente_id=? AND m.tipo='COMPRA'
              AND UPPER(COALESCE(m.status_pagamento,''))<>'CANCELADO'
            ORDER BY m.id
            """,
            (int(cliente_id),),
        ).fetchall()
        compras: list[dict[str, Any]] = []
        for row in rows:
            compra = dict(row)
            compra["valor"] = DecimalStorage.to_decimal(compra["valor"], field="valor da compra")
            compra["valor_aberto"] = DecimalStorage.read(
                compra.get("valor_aberto_decimal"), compra.get("valor_aberto", 0), field="valor em aberto"
            )
            compras.append(compra)

        parcel_columns = self.colunas_tabela("parcelas", connection)
        valor_canonical = "p.valor_parcela_decimal" if "valor_parcela_decimal" in parcel_columns else "NULL"
        pago_canonical = "p.valor_pago_decimal" if "valor_pago_decimal" in parcel_columns else "NULL"
        dados_confiaveis = "COALESCE(p.dados_confiaveis,1)" if "dados_confiaveis" in parcel_columns else "1"
        parcelas_rows = connection.execute(
            f"""
            SELECT p.id,p.movimentacao_id,p.numero_parcela,p.valor_parcela,
                   {valor_canonical} AS valor_parcela_decimal,
                   COALESCE(p.valor_pago,0) AS valor_pago,{pago_canonical} AS valor_pago_decimal,
                   COALESCE(p.vencimento,'') AS vencimento,COALESCE(p.status,'PENDENTE') AS status,
                   {dados_confiaveis} AS dados_confiaveis
            FROM parcelas p
            JOIN movimentacoes m ON m.id=p.movimentacao_id
            WHERE m.cliente_id=? AND m.tipo='COMPRA'
              AND UPPER(COALESCE(m.status_pagamento,''))<>'CANCELADO'
            ORDER BY p.movimentacao_id,p.numero_parcela,p.id
            """,
            (int(cliente_id),),
        ).fetchall()
        parcelas_por_compra: dict[int, list[dict[str, Any]]] = {}
        for row in parcelas_rows:
            parcela = dict(row)
            parcela["valor_parcela"] = DecimalStorage.read(
                parcela.get("valor_parcela_decimal"), parcela.get("valor_parcela", 0), field="valor da parcela"
            )
            parcela["valor_pago"] = DecimalStorage.read(
                parcela.get("valor_pago_decimal"), parcela.get("valor_pago", 0), field="valor pago"
            )
            parcelas_por_compra.setdefault(int(parcela["movimentacao_id"]), []).append(parcela)

        for compra in compras:
            compra["parcelas"] = parcelas_por_compra.get(int(compra["id"]), [])
        return {"cliente": cliente, "compras": compras}

    def atualizar_saldo_cliente(self, cliente_id: int, novo_saldo: Decimal, connection) -> None:
        colunas = self.colunas_tabela("clientes", connection)
        legacy, canonical = DecimalStorage.pair(novo_saldo, field="saldo devedor")
        if "saldo_devedor_decimal" in colunas:
            connection.execute(
                "UPDATE clientes SET saldo_devedor=?,saldo_devedor_decimal=? WHERE id=?",
                (legacy, canonical, int(cliente_id)),
            )
        else:
            connection.execute(
                "UPDATE clientes SET saldo_devedor=? WHERE id=?",
                (legacy, int(cliente_id)),
            )

    def atualizar_saldo_compra_reconciliado(
        self, movimentacao_id: int, saldo: Decimal, connection
    ) -> None:
        status = "PAGO" if saldo == Decimal("0.00") else "PARCIAL"
        self.atualizar_compra_aberta(int(movimentacao_id), saldo, status, connection)

    def inserir_movimento_pagamento_cliente(
        self, *, cliente_id: int, descricao: str, valor: Decimal, data: str,
        forma_pagamento: str, connection,
    ) -> int:
        cursor = connection.execute(
            """INSERT INTO movimentacoes
               (cliente_id,tipo,descricao,valor,data,vencimento,status_pagamento,valor_aberto,forma_pagamento)
               VALUES (?,'PAGAMENTO',?,?,?,NULL,'PAGO',0,?)""",
            (int(cliente_id), descricao, DecimalStorage.legacy_real(valor, field="valor recebido"), data, forma_pagamento),
        )
        return int(cursor.lastrowid)

    def listar_compras_para_alocacao(
        self, cliente_id: int, *, movimentacao_id: int | None = None, connection,
    ) -> list[dict[str, Any]]:
        filtro = " AND id=?" if movimentacao_id is not None else ""
        ordem = "" if movimentacao_id is not None else " ORDER BY CASE WHEN vencimento IS NULL OR vencimento='' THEN 1 ELSE 0 END,vencimento,id"
        params = (int(cliente_id), int(movimentacao_id)) if movimentacao_id is not None else (int(cliente_id),)
        colunas = self.colunas_tabela("movimentacoes", connection)
        canonical = "valor_aberto_decimal" if "valor_aberto_decimal" in colunas else "NULL"
        rows = connection.execute(
            f"""SELECT id,COALESCE(valor_aberto,valor,0) AS valor_aberto,{canonical} AS valor_aberto_decimal
                FROM movimentacoes WHERE cliente_id=? AND tipo='COMPRA'
                  AND UPPER(COALESCE(status_pagamento,''))<>'CANCELADO'{filtro}{ordem}""",
            params,
        ).fetchall()
        resultado = []
        for row in rows:
            saldo = DecimalStorage.read(row[2], row[1], field="valor em aberto")
            if saldo > Decimal("0.001"):
                resultado.append({"id": int(row[0]), "valor_aberto": saldo})
        return resultado

    def atualizar_compra_aberta(self, movimentacao_id: int, saldo: Decimal, status: str, connection) -> None:
        colunas = self.colunas_tabela("movimentacoes", connection)
        legacy, canonical = DecimalStorage.pair(saldo, field="valor em aberto")
        if "valor_aberto_decimal" in colunas:
            connection.execute(
                "UPDATE movimentacoes SET valor_aberto=?,valor_aberto_decimal=?,status_pagamento=? WHERE id=?",
                (legacy, canonical, status, int(movimentacao_id)),
            )
        else:
            connection.execute(
                "UPDATE movimentacoes SET valor_aberto=?,status_pagamento=? WHERE id=?",
                (legacy, status, int(movimentacao_id)),
            )

    def listar_parcelas_para_alocacao(
        self, movimentacao_id: int, *, parcela_id: int | None = None, connection,
    ) -> list[dict[str, Any]]:
        colunas = self.colunas_tabela("parcelas", connection)
        valor_canonical = "valor_parcela_decimal" if "valor_parcela_decimal" in colunas else "NULL"
        pago_canonical = "valor_pago_decimal" if "valor_pago_decimal" in colunas else "NULL"
        filtro = " AND id=?" if parcela_id is not None else ""
        ordem = "" if parcela_id is not None else " ORDER BY numero_parcela,id"
        params = (int(movimentacao_id), int(parcela_id)) if parcela_id is not None else (int(movimentacao_id),)
        rows = connection.execute(
            f"""SELECT id,valor_parcela,{valor_canonical} AS valor_parcela_decimal,
                       COALESCE(valor_pago,0) AS valor_pago,{pago_canonical} AS valor_pago_decimal,
                       vencimento,status
                FROM parcelas WHERE movimentacao_id=? AND status<>'PAGO'{filtro}{ordem}""",
            params,
        ).fetchall()
        return [{
            "id": int(row[0]),
            "valor_parcela": DecimalStorage.read(row[2], row[1], field="valor da parcela"),
            "valor_pago": DecimalStorage.read(row[4], row[3], field="valor pago"),
            "vencimento": str(row[5] or ""), "status": str(row[6] or "PENDENTE"),
        } for row in rows]

    def criar_parcela_unica_se_ausente(self, movimentacao_id: int, connection) -> None:
        connection.execute(
            """INSERT INTO parcelas
               (movimentacao_id,numero_parcela,valor_parcela,vencimento,status,valor_pago,data_pagamento,atraso_registrado,dados_confiaveis)
               SELECT id,1,COALESCE(valor,0),COALESCE(vencimento,''),'PENDENTE',0,'',0,1
               FROM movimentacoes WHERE id=? AND NOT EXISTS(
                   SELECT 1 FROM parcelas WHERE movimentacao_id=?
               )""", (int(movimentacao_id), int(movimentacao_id)),
        )

    def _atualizar_parcela_financeira(
        self, parcela_id: int, *, valor_pago: Decimal, status: str, connection,
        data_pagamento: str | None = None, registrar_data: bool = False, atraso: int = 0,
    ) -> None:
        colunas = self.colunas_tabela("parcelas", connection)
        legacy, canonical = DecimalStorage.pair(valor_pago, field="valor pago")
        possui_decimal = "valor_pago_decimal" in colunas
        if data_pagamento is None:
            campos = "valor_pago=?,valor_pago_decimal=?,status=?" if possui_decimal else "valor_pago=?,status=?"
            params = (legacy, canonical, status, int(parcela_id)) if possui_decimal else (legacy, status, int(parcela_id))
        else:
            prefixo = "valor_pago=?,valor_pago_decimal=?,status=?" if possui_decimal else "valor_pago=?,status=?"
            campos = prefixo + ",data_pagamento=CASE WHEN ? THEN ? ELSE data_pagamento END,atraso_registrado=MAX(COALESCE(atraso_registrado,0),?)"
            base = (legacy, canonical, status) if possui_decimal else (legacy, status)
            params = base + (1 if registrar_data else 0, data_pagamento, int(atraso), int(parcela_id))
        connection.execute(f"UPDATE parcelas SET {campos} WHERE id=?", params)

    def reconciliar_valor_pago_parcela(
        self, parcela_id: int, *, valor_pago: Decimal, status: str, connection
    ) -> None:
        self._atualizar_parcela_financeira(
            int(parcela_id), valor_pago=valor_pago, status=status, connection=connection
        )

    def atualizar_parcela_pagamento(
        self, parcela_id: int, *, valor_pago: Decimal, status: str,
        data_pagamento: str, registrar_data: bool, atraso: int, connection,
    ) -> None:
        self._atualizar_parcela_financeira(
            int(parcela_id), valor_pago=valor_pago, status=status, connection=connection,
            data_pagamento=data_pagamento, registrar_data=registrar_data, atraso=atraso,
        )
