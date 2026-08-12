from __future__ import annotations

import json
import sqlite3
import tempfile
import time
import tracemalloc
from decimal import Decimal
from pathlib import Path

from database import DatabaseMaintenanceService
from services.pdv_service import PDVService
from services.pdv_transaction_service import PDVTransactionService


class StressStockService:
    def baixar_itens_venda_na_transacao(self, connection, items, *, venda_id, usuario):
        for item in items:
            product_id = item.get("produto_id")
            if product_id is None:
                continue
            connection.execute(
                "UPDATE produtos SET estoque_atual=estoque_atual-? WHERE id=?",
                (float(item["qtd"]), product_id),
            )
            connection.execute(
                "INSERT INTO estoque_movimentacoes(produto_id,tipo,quantidade,origem,origem_id) VALUES(?,'SAIDA',?,'VENDA',?)",
                (product_id, float(item["qtd"]), venda_id),
            )

    def estornar_venda_na_transacao(self, connection, venda_id, *, usuario):
        rows = connection.execute(
            "SELECT produto_id,quantidade FROM estoque_movimentacoes WHERE origem='VENDA' AND origem_id=?",
            (venda_id,),
        ).fetchall()
        for product_id, quantity in rows:
            connection.execute(
                "UPDATE produtos SET estoque_atual=estoque_atual+? WHERE id=?",
                (quantity, product_id),
            )


class StressFinanceService:
    def registrar_venda_crediario_transacao(self, connection, **data):
        connection.execute(
            "INSERT INTO financeiro_titulos(tipo,origem,origem_id,valor,status) VALUES('RECEBER','VENDA',?,?,'ABERTO')",
            (data["venda_id"], data["valor"]),
        )

    def cancelar_titulos_origem_transacao(self, connection, *, origem_id, **_data):
        connection.execute(
            "UPDATE financeiro_titulos SET status='CANCELADO' WHERE origem='VENDA' AND origem_id=?",
            (origem_id,),
        )


class BrokenAfterStock(StressStockService):
    def baixar_itens_venda_na_transacao(self, connection, items, *, venda_id, usuario):
        super().baixar_itens_venda_na_transacao(
            connection, items, venda_id=venda_id, usuario=usuario
        )
        raise RuntimeError("falha injetada depois do estoque")


def create_schema(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE clientes(id INTEGER PRIMARY KEY,nome TEXT,saldo_devedor REAL DEFAULT 0);
            CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT,cliente_id INTEGER,tipo TEXT,descricao TEXT,valor REAL,data TEXT,vencimento TEXT,status_pagamento TEXT,valor_aberto REAL,forma_pagamento TEXT);
            CREATE TABLE parcelas(id INTEGER PRIMARY KEY AUTOINCREMENT,movimentacao_id INTEGER,numero_parcela INTEGER,valor_parcela REAL,vencimento TEXT,status TEXT,valor_pago REAL,data_pagamento TEXT,atraso_registrado INTEGER,dados_confiaveis INTEGER);
            CREATE TABLE configuracoes(chave TEXT PRIMARY KEY,valor TEXT);
            CREATE TABLE produtos(id INTEGER PRIMARY KEY,estoque_atual REAL);
            CREATE TABLE estoque_movimentacoes(id INTEGER PRIMARY KEY AUTOINCREMENT,produto_id INTEGER,tipo TEXT,quantidade REAL,origem TEXT,origem_id INTEGER);
            CREATE TABLE financeiro_titulos(id INTEGER PRIMARY KEY AUTOINCREMENT,tipo TEXT,origem TEXT,origem_id INTEGER,valor REAL,status TEXT);
            INSERT INTO clientes(id,nome,saldo_devedor) VALUES(1,'CLIENTE STRESS',0);
            INSERT INTO produtos(id,estoque_atual) VALUES(1,10000),(2,10000);
        """)
        connection.commit()
    finally:
        connection.close()


def test_one_thousand_sales_failures_backup_and_restore():
    started = time.perf_counter()
    tracemalloc.start()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        database_path = root / "stress.db"
        create_schema(database_path)
        factory = lambda: sqlite3.connect(database_path)
        pdv = PDVService(factory)
        service = PDVTransactionService(
            factory,
            estoque_service=StressStockService(),
            financeiro_service=StressFinanceService(),
            pdv_service=pdv,
        )
        expected_stock = {1: Decimal("10000"), 2: Decimal("10000")}
        expected_balance = Decimal("0")
        expected_installments = 0
        cancelled = 0
        for index in range(1000):
            quantity = Decimal("2") if index % 3 == 0 else Decimal("1")
            product_id = 1 if index % 2 == 0 else 2
            items = [
                {"produto_id": product_id, "item": "PRODUTO", "qtd": quantity, "preco": 5, "subtotal": quantity * 5},
                {"produto_id": product_id, "item": "PRODUTO REPETIDO", "qtd": 1, "preco": 5, "subtotal": 5},
            ]
            total = quantity * 5 + 5
            if index % 4 == 0:
                payments = [{"forma": "CREDIARIO", "valor": total, "parcelas": 3}]
                credit = total
                installments = 3
            elif index % 5 == 0:
                half = (total / 2).quantize(Decimal("0.01"))
                payments = [{"forma": "PIX", "valor": half}, {"forma": "CREDITO", "valor": total - half}]
                credit = Decimal("0")
                installments = 1
            else:
                method = ("DINHEIRO", "PIX", "CREDITO")[index % 3]
                payments = [{"forma": method, "valor": total}]
                credit = Decimal("0")
                installments = 1
            result = service.finalize_sale(
                customer_id=1,
                customer_name="CLIENTE STRESS",
                items=items,
                payments=payments,
                received=total,
                change=0,
                user="stress",
            )
            expected_installments += installments
            if index % 10 == 0:
                service.cancel_sale(result.sale_id, user="stress")
                cancelled += 1
            else:
                expected_stock[product_id] -= quantity + 1
                expected_balance += credit

        broken = PDVTransactionService(
            factory,
            estoque_service=BrokenAfterStock(),
            financeiro_service=StressFinanceService(),
            pdv_service=pdv,
        )
        for _ in range(100):
            try:
                broken.finalize_sale(
                    customer_id=1,
                    customer_name="CLIENTE STRESS",
                    items=[{"produto_id": 1, "item": "FALHA", "qtd": 1, "preco": 1, "subtotal": 1}],
                    payments=[{"forma": "CREDIARIO", "valor": 1}],
                    received=1,
                    change=0,
                    user="stress",
                )
            except RuntimeError:
                pass
            else:
                raise AssertionError("falha artificial nÃ£o foi propagada")

        connection = sqlite3.connect(database_path)
        try:
            assert connection.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0] == 1000
            assert connection.execute("SELECT COUNT(*) FROM estoque_movimentacoes").fetchone()[0] == 2000
            assert connection.execute("SELECT COUNT(*) FROM parcelas").fetchone()[0] == expected_installments
            assert Decimal(str(connection.execute("SELECT saldo_devedor FROM clientes WHERE id=1").fetchone()[0])).quantize(Decimal("0.01")) == expected_balance.quantize(Decimal("0.01"))
            for product_id, expected in expected_stock.items():
                actual = Decimal(str(connection.execute("SELECT estoque_atual FROM produtos WHERE id=?", (product_id,)).fetchone()[0]))
                assert actual == expected
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            connection.close()

        maintenance = DatabaseMaintenanceService(database_path, root / "backups")
        backup, report = maintenance.create_backup(prefix="stress", validate=True)
        assert report.valid
        connection = sqlite3.connect(database_path)
        connection.execute("DELETE FROM movimentacoes")
        connection.commit()
        connection.close()
        maintenance.restore(backup)
        connection = sqlite3.connect(database_path)
        try:
            assert connection.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0] == 1000
        finally:
            connection.close()

        current_memory, peak_memory = tracemalloc.get_traced_memory()
        metrics = {
            "sales": 1000,
            "stock_movements": 2000,
            "cancelled_sales": cancelled,
            "injected_rollbacks": 100,
            "database_bytes": database_path.stat().st_size,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "memory_current_bytes": current_memory,
            "memory_peak_bytes": peak_memory,
        }
        print("STRESS_METRICS=" + json.dumps(metrics, sort_keys=True))
    tracemalloc.stop()
