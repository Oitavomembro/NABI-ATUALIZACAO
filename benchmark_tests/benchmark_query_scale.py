from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import time
import tracemalloc
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import DatabaseManager
from repositories.cliente_repository import ClienteRepository
from repositories.dashboard_repository import DashboardRepository
from repositories.produto_repository import ProdutoRepository


SCHEMA = """
CREATE TABLE clientes(
 id INTEGER PRIMARY KEY,codigo TEXT,numero_ficha INTEGER,nome TEXT,cpf TEXT,rg TEXT,
 telefone TEXT,endereco TEXT,observacoes TEXT,favorito INTEGER DEFAULT 0,
 saldo_devedor REAL DEFAULT 0,limite REAL DEFAULT 0);
CREATE TABLE movimentacoes(
 id INTEGER PRIMARY KEY,cliente_id INTEGER,tipo TEXT,descricao TEXT,valor REAL,data TEXT,
 vencimento TEXT,status_pagamento TEXT,valor_aberto REAL DEFAULT 0);
CREATE TABLE categorias_produtos(id INTEGER PRIMARY KEY,nome TEXT);
CREATE TABLE marcas_produtos(id INTEGER PRIMARY KEY,nome TEXT);
CREATE TABLE fornecedores(id INTEGER PRIMARY KEY,nome_fantasia TEXT);
CREATE TABLE unidades_medida(id INTEGER PRIMARY KEY,sigla TEXT);
CREATE TABLE produtos(
 id INTEGER PRIMARY KEY,codigo TEXT,nome TEXT,descricao TEXT,categoria_id INTEGER,
 marca_id INTEGER,fornecedor_id INTEGER,unidade_id INTEGER,unidade_compra_id INTEGER,
 preco_venda REAL,preco_venda_decimal TEXT,preco_custo REAL,preco_custo_decimal TEXT,
 despesas_percentual REAL,despesas_percentual_decimal TEXT,margem_lucro REAL,
 margem_lucro_decimal TEXT,fator_conversao REAL,fator_conversao_decimal TEXT,
 codigo_barras TEXT,ncm TEXT,cest TEXT,cfop TEXT,estoque_atual REAL,estoque_minimo REAL,
 permite_estoque_negativo INTEGER,controla_estoque INTEGER,tipo_produto TEXT,ativo INTEGER);
CREATE INDEX idx_produtos_nome ON produtos(nome COLLATE NOCASE);
CREATE INDEX idx_produtos_ativo_nome ON produtos(ativo DESC,nome COLLATE NOCASE,id);
CREATE INDEX idx_clientes_ficha_ordem ON clientes((numero_ficha IS NULL),numero_ficha,nome COLLATE NOCASE,id);
CREATE INDEX idx_mov_pendente_cliente_vencimento ON movimentacoes(status_pagamento,cliente_id,vencimento);
"""


def _measure(operation):
    tracemalloc.start()
    started = time.perf_counter()
    result = operation()
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, round(elapsed * 1000, 3), peak


def run(rows: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="nabicode-query-scale-") as folder:
        path = Path(folder) / "scale.db"
        connection = sqlite3.connect(path)
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO clientes VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            ((index, f"C{index:06d}", index, f"CLIENTE COMUM {index:06d}", "", "", "", "", "", 0,
              100 if index % 3 else 0, 1000) for index in range(1, rows + 1)),
        )
        # A ficha exata é inserida por último, depois de centenas de parciais.
        connection.execute("UPDATE clientes SET numero_ficha=-123 WHERE id=123")
        connection.execute(
            "UPDATE clientes SET numero_ficha=123,nome='CLIENTE ALVO',codigo='C000001 ALVO' WHERE id=?",
            (rows,),
        )
        connection.executemany(
            "INSERT INTO movimentacoes VALUES(?,?,?,?,?,?,?,?,?)",
            ((index, index, "COMPRA", "VOLUME", 100, "25/08/2026 10:00:00",
              "2026-01-01" if index % 5 == 0 else "2027-01-01", "PENDENTE", 100)
             for index in range(1, rows + 1)),
        )
        connection.executemany(
            "INSERT INTO produtos VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ((index, f"P{index:06d}", f"PRODUTO COMUM {index:06d}", "", None, None, None,
              None, None, 10, "10", 5, "5", 0, "0", 0, "0", 1, "1",
              f"789{index:010d}", "", "", "", 10, 1, 0, 1, "MERCADORIA", 1)
             for index in range(1, rows + 1)),
        )
        connection.commit()

        database = DatabaseManager(path)
        customers = ClienteRepository(database)
        dashboard = DashboardRepository(database)
        products = ProdutoRepository(database)
        suggestions, customer_ms, customer_peak = _measure(
            lambda: customers.search_sales_suggestions("123", limit=30)
        )
        page, page_ms, page_peak = _measure(
            lambda: customers.list_page(page=0, per_page=50)
        )
        summary, summary_ms, summary_peak = _measure(
            lambda: dashboard.client_summary()
        )
        product_rows, product_ms, product_peak = _measure(
            lambda: products.listar("PRODUTO", limit=30)
        )
        plans = {
            "customer_page": [tuple(row) for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT id FROM clientes ORDER BY (numero_ficha IS NULL),numero_ficha,nome COLLATE NOCASE,id LIMIT 50"
            )],
            "pending_due": [tuple(row) for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT cliente_id,MIN(NULLIF(vencimento,'')) FROM movimentacoes WHERE status_pagamento='PENDENTE' GROUP BY cliente_id"
            )],
            "product_name": [tuple(row) for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT id FROM produtos WHERE nome LIKE '%PRODUTO%' COLLATE NOCASE ORDER BY ativo DESC,nome COLLATE NOCASE LIMIT 30"
            )],
        }
        connection.close()
        return {
            "rows": rows,
            "customer_suggestion": {"ms": customer_ms, "peak_bytes": customer_peak,
                                    "ids": [item.id for item in suggestions]},
            "customer_page": {"ms": page_ms, "peak_bytes": page_peak,
                              "materialized": len(page.rows), "total": page.total},
            "client_summary": {"ms": summary_ms, "peak_bytes": summary_peak,
                               "total": summary.total_records},
            "product_search": {"ms": product_ms, "peak_bytes": product_peak,
                               "materialized": len(product_rows)},
            "plans": plans,
        }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=20_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = run(max(1, args.rows))
    raw = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(raw + "\n", encoding="utf-8")
    print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
