from __future__ import annotations

import json
import re
from decimal import Decimal

from commercial.application.product_dto import (
    ProductCreateCommand, StockAdjustmentCommand, StockMovementCommand,
)


class AssistedProductStockService:
    """Muta produto/estoque e diário da Nabi na mesma transação SQLite."""

    OPERATIONS = frozenset({"PRODUCT_CREATE", "STOCK_RECEIVE", "STOCK_REMOVE", "STOCK_ADJUST"})

    def __init__(self, product_service, stock_service) -> None:
        if product_service is None or stock_service is None:
            raise ValueError("Serviços oficiais de produto e estoque são obrigatórios.")
        self.products = product_service
        self.stock = stock_service
        product_database = product_service.produtos.database
        if product_database is not stock_service.database:
            raise ValueError("Produto, estoque e diário devem usar o mesmo banco.")
        self.database = product_database

    @staticmethod
    def _identity(key: str, fingerprint: str, username: str) -> tuple[str, str, str]:
        key = str(key or "").strip()
        fingerprint = str(fingerprint or "").strip().lower()
        username = str(username or "").strip()
        if not key or len(key) > 160:
            raise ValueError("Chave idempotente inválida.")
        if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise ValueError("Impressão digital da operação inválida.")
        if not username:
            raise PermissionError("Usuário autenticado é obrigatório.")
        return key, fingerprint, username

    @staticmethod
    def _begin(connection, *, key: str, kind: str, fingerprint: str, username: str):
        row = connection.execute(
            "SELECT operation_kind,fingerprint,status,result_json FROM assistant_operation_journal "
            "WHERE idempotency_key=?", (key,),
        ).fetchone()
        if row is not None:
            if str(row[0]) != kind or str(row[1]).lower() != fingerprint:
                raise ValueError("A chave idempotente já pertence a outro conteúdo.")
            if str(row[2]) != "COMMITTED":
                raise RuntimeError("A operação assistida possui estado persistente desconhecido.")
            return json.loads(str(row[3] or "{}"))
        connection.execute(
            """INSERT INTO assistant_operation_journal
               (idempotency_key,operation_kind,fingerprint,status,result_json,username,created_at)
               VALUES(?,?,?,'PENDING','',?,datetime('now','localtime'))""",
            (key, kind, fingerprint, username),
        )
        return None

    @staticmethod
    def _commit(connection, *, key: str, payload: dict) -> None:
        result = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        updated = connection.execute(
            """UPDATE assistant_operation_journal
               SET status='COMMITTED',result_json=?,committed_at=datetime('now','localtime')
               WHERE idempotency_key=? AND status='PENDING'""", (result, key),
        )
        if updated.rowcount != 1:
            raise RuntimeError("Não foi possível confirmar o diário idempotente.")

    def create_product(self, command: ProductCreateCommand, *, username: str,
                       idempotency_key: str, operation_fingerprint: str) -> int:
        key, fingerprint, actor = self._identity(idempotency_key, operation_fingerprint, username)
        if command.current_stock != 0 or command.allow_negative_stock:
            raise ValueError("Cadastro assistido cria produto com estoque zero e sem saldo negativo.")
        if str(command.product_type).upper() != "MERCADORIA":
            raise ValueError("Cadastro assistido aceita somente mercadoria comercial.")
        with self.database.session(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            replay = self._begin(connection, key=key, kind="PRODUCT_CREATE",
                                 fingerprint=fingerprint, username=actor)
            if replay is not None:
                return int(replay["product_id"])
            product_id = self.products.salvar(
                codigo=command.code, nome=command.description,
                preco_venda=command.sale_price, categoria_id=command.category_id,
                tipo_produto="MERCADORIA", preco_custo=command.cost_price,
                codigo_barras=command.barcode, estoque_atual=Decimal("0"),
                estoque_minimo=command.minimum_stock,
                permite_estoque_negativo=False, connection=connection,
            )
            self._commit(connection, key=key, payload={"product_id": int(product_id)})
            return int(product_id)

    def move_stock(self, kind: str, command, *, username: str,
                   idempotency_key: str, operation_fingerprint: str):
        kind = str(kind or "").upper()
        if kind not in self.OPERATIONS - {"PRODUCT_CREATE"}:
            raise ValueError("Operação de estoque assistida inválida.")
        key, fingerprint, actor = self._identity(idempotency_key, operation_fingerprint, username)
        with self.database.session(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            replay = self._begin(connection, key=key, kind=kind,
                                 fingerprint=fingerprint, username=actor)
            if replay is not None:
                return replay
            if kind == "STOCK_ADJUST":
                if not isinstance(command, StockAdjustmentCommand) or command.new_balance < 0:
                    raise ValueError("Ajuste assistido não permite saldo negativo.")
                result = self.stock.ajustar_na_transacao(
                    connection, command.product_id, command.new_balance,
                    motivo=command.reason, usuario=actor,
                )
            else:
                if not isinstance(command, StockMovementCommand):
                    raise TypeError("Comando de estoque inválido.")
                result = self.stock.movimentar_na_transacao(
                    connection, command.product_id, command.amount,
                    entrada=kind == "STOCK_RECEIVE", origem="NABI_ASSISTED",
                    origem_id=key, motivo=command.reason, usuario=actor,
                )
                if Decimal(str(result.saldo_atual)) < 0:
                    raise ValueError("A Nabi não pode produzir estoque negativo.")
            payload = {
                "movement_id": int(result.movimentacao_id),
                "product_id": int(result.produto_id), "movement_type": result.tipo,
                "quantity": str(result.quantidade),
                "previous_balance": str(result.saldo_anterior),
                "resulting_balance": str(result.saldo_atual),
            }
            self._commit(connection, key=key, payload=payload)
            return payload
