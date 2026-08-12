from __future__ import annotations

import json
import sqlite3
import statistics
import tempfile
import time
from pathlib import Path

from database import DatabaseManager
from repositories.cliente_repository import ClienteRepository


def measure(operation, repetitions: int = 9) -> dict[str, float]:
    durations = []
    for _ in range(repetitions):
        started = time.perf_counter()
        operation()
        durations.append((time.perf_counter() - started) * 1000)
    return {
        "p50_ms": round(statistics.median(durations), 3),
        "mean_ms": round(statistics.fmean(durations), 3),
        "max_ms": round(max(durations), 3),
    }


def create_dataset(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript("""
            CREATE TABLE clientes(id INTEGER PRIMARY KEY,codigo TEXT,nome TEXT,numero_ficha INTEGER,cpf TEXT,rg TEXT,telefone TEXT,endereco TEXT,observacoes TEXT,favorito INTEGER DEFAULT 0);
            CREATE INDEX idx_clientes_nome ON clientes(nome COLLATE NOCASE);
            CREATE INDEX idx_clientes_codigo ON clientes(codigo);
            CREATE TABLE produtos(id INTEGER PRIMARY KEY,codigo TEXT,nome TEXT,codigo_barras TEXT,ativo INTEGER DEFAULT 1,estoque_atual REAL);
            CREATE INDEX idx_produtos_nome ON produtos(nome COLLATE NOCASE);
            CREATE INDEX idx_produtos_codigo ON produtos(codigo);
            CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY,cliente_id INTEGER,tipo TEXT,valor REAL,data TEXT,status_pagamento TEXT);
            CREATE INDEX idx_movimentacoes_cliente ON movimentacoes(cliente_id);
            CREATE INDEX idx_movimentacoes_data ON movimentacoes(data);
            CREATE TABLE financeiro_titulos(id INTEGER PRIMARY KEY,tipo TEXT,status TEXT,valor REAL,data_vencimento TEXT,cliente_id INTEGER);
            CREATE INDEX idx_financeiro_tipo_status ON financeiro_titulos(tipo,status);
        """)
        connection.executemany(
            "INSERT INTO clientes VALUES(?,?,?,?,?,?,?,?,?,?)",
            ((index, f"C{index:05d}", f"CLIENTE {index:05d}", index, f"CPF{index:05d}", "", f"TEL{index:05d}", "RUA", "", index % 10 == 0) for index in range(1, 10001)),
        )
        connection.executemany(
            "INSERT INTO produtos VALUES(?,?,?,?,?,?)",
            ((index, f"P{index:05d}", f"PRODUTO {index:05d}", f"789{index:010d}", 1, index % 100) for index in range(1, 10001)),
        )
        connection.executemany(
            "INSERT INTO movimentacoes VALUES(?,?,?,?,?,?)",
            ((index, (index % 10000) + 1, "COMPRA", (index % 500) / 10, f"{(index % 28)+1:02d}/08/2026 10:00:00", "PAGO" if index % 3 else "PENDENTE") for index in range(1, 50001)),
        )
        connection.executemany(
            "INSERT INTO financeiro_titulos VALUES(?,?,?,?,?,?)",
            ((index, "RECEBER" if index % 2 else "PAGAR", "ABERTO" if index % 3 else "PAGO", (index % 900) / 10, "2026-08-31", (index % 10000) + 1) for index in range(1, 20001)),
        )
        connection.commit()
    finally:
        connection.close()


def test_large_dataset_query_baseline():
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "benchmark.db"
        create_dataset(path)
        database = DatabaseManager(path)
        clients = ClienteRepository(database)

        def product_search():
            with database.session() as connection:
                rows = connection.execute(
                    "SELECT id,codigo,nome,estoque_atual FROM produtos WHERE codigo LIKE ? OR nome LIKE ? COLLATE NOCASE LIMIT 200",
                    ("%P09999%", "%PRODUTO 09999%"),
                ).fetchall()
                assert len(rows) == 1

        def client_search():
            result = clients.search_sales_suggestions("CLIENTE 09999", limit=30)
            assert len(result) == 1

        def history():
            with database.session() as connection:
                rows = connection.execute(
                    "SELECT id,tipo,valor,data FROM movimentacoes WHERE cliente_id=? ORDER BY id DESC LIMIT 200",
                    (5000,),
                ).fetchall()
                assert len(rows) == 5

        def dashboard():
            with database.session() as connection:
                row = connection.execute(
                    "SELECT COUNT(*),COALESCE(SUM(valor),0) FROM movimentacoes WHERE data LIKE '01/08/2026%'"
                ).fetchone()
                assert row[0] > 0

        def financial():
            with database.session() as connection:
                row = connection.execute(
                    "SELECT COUNT(*),COALESCE(SUM(valor),0) FROM financeiro_titulos WHERE tipo='RECEBER' AND status='ABERTO'"
                ).fetchone()
                assert row[0] > 0

        metrics = {
            "product_search_10000": measure(product_search),
            "client_suggestions_10000": measure(client_search),
            "client_history_50000": measure(history),
            "dashboard_50000": measure(dashboard),
            "financial_20000": measure(financial),
        }
        for result in metrics.values():
            assert result["max_ms"] < 1000
        print("BENCHMARK_METRICS=" + json.dumps(metrics, sort_keys=True))
