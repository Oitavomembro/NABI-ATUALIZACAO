from __future__ import annotations

import sqlite3
from decimal import Decimal

from commercial.application.financial_dto import FinancialSummary, FinancialTitlePage
from commercial.application.report_dto import ReportQuery
from commercial.infrastructure.report_gateway import NabiCodeReportGateway
from database import DatabaseManager
from repositories.financeiro_repository import FinanceiroRepository
from services.report_service import ReportService


def _connect(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def test_relatorio_20_mil_materializa_so_uma_pagina_e_totaliza_tudo(tmp_path):
    path = tmp_path / "reports.db"
    connection = _connect(path)
    connection.executescript(
        "CREATE TABLE configuracoes(chave TEXT PRIMARY KEY,valor TEXT);"
        "CREATE TABLE movimentacoes(id INTEGER PRIMARY KEY,data TEXT,tipo TEXT,descricao TEXT,valor_total REAL,status TEXT,usuario TEXT);"
    )
    connection.executemany(
        "INSERT INTO movimentacoes VALUES(?,?,?,?,?,?,?)",
        ((index, "2026-08-24", "VENDA", f"ITEM {index}", 1.25, "PAGO", "operador") for index in range(1, 20_001)),
    )
    connection.commit(); connection.close()
    gateway = NabiCodeReportGateway(ReportService(lambda: _connect(path), output_dir=tmp_path / "out"))
    page = gateway.load_page(ReportQuery("vendas"), limit=100, offset=10_000, actor="operador")
    assert len(page.document.rows) == 100
    assert page.total_records == page.summary.quantity == 20_000
    assert page.summary.value_total == Decimal("25000.0")
    assert page.document.rows[0][0] == 10_000


def test_financeiro_20_mil_usa_limit_offset_e_total_completo(tmp_path):
    path = tmp_path / "finance.db"
    database = DatabaseManager(path)
    with database.session(write=True) as connection:
        connection.executescript("""
        CREATE TABLE titulos_financeiros(
          id INTEGER PRIMARY KEY,tipo TEXT,origem TEXT,origem_id TEXT,pessoa_id INTEGER,
          pessoa_nome TEXT,documento TEXT,descricao TEXT,data_emissao TEXT,data_vencimento TEXT,
          valor_original REAL,valor_original_decimal TEXT,valor_pago REAL,valor_pago_decimal TEXT,
          status TEXT,observacao TEXT,criado_em TEXT,atualizado_em TEXT);
        CREATE TABLE pagamentos_titulos(id INTEGER PRIMARY KEY,titulo_id INTEGER,valor REAL,
          valor_decimal TEXT,forma_pagamento TEXT,observacao TEXT,usuario TEXT,data_pagamento TEXT);
        """)
        connection.executemany(
            "INSERT INTO titulos_financeiros VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ((index, "RECEBER", "MANUAL", "", None, f"CLIENTE {index}", "", "TESTE",
              "2026-08-24", "2026-08-24", 2.5, "2.50", 0, "0.00", "ABERTO", "",
              "2026-08-24", "2026-08-24") for index in range(1, 20_001)),
        )
    repository = FinanceiroRepository(database)
    rows, total = repository.listar_titulos_pagina(tipo="RECEBER", limite=125, offset=10_000)
    assert len(rows) == 125 and total == 20_000
    assert rows[0]["id"] == 10_001
    assert repository.resumo_titulos_abertos()["receber"] == Decimal("50000.0")


def test_paginas_vazias_mantem_total_honesto(tmp_path):
    path = tmp_path / "empty-page.db"
    connection = _connect(path)
    connection.executescript(
        "CREATE TABLE configuracoes(chave TEXT PRIMARY KEY,valor TEXT);"
        "CREATE TABLE clientes(id INTEGER PRIMARY KEY,nome TEXT,saldo_devedor REAL);"
        "INSERT INTO clientes VALUES(1,'ANA',10);"
    )
    connection.commit(); connection.close()
    gateway = NabiCodeReportGateway(ReportService(lambda: _connect(path), output_dir=tmp_path / "out"))
    page = gateway.load_page(ReportQuery("clientes"), limit=25, offset=100, actor="operador")
    assert page.document.rows == () and page.total_records == 1


def test_exportacao_refaz_filtro_completo_e_autorizacao_antecede_contagem(tmp_path):
    path = tmp_path / "export.db"
    connection = _connect(path)
    connection.executescript(
        "CREATE TABLE configuracoes(chave TEXT PRIMARY KEY,valor TEXT);"
        "CREATE TABLE clientes(id INTEGER PRIMARY KEY,nome TEXT,saldo_devedor REAL);"
        "INSERT INTO clientes VALUES(1,'ANA',10); INSERT INTO clientes VALUES(2,'BIA',20);"
    )
    connection.commit(); connection.close()
    allowed = {"value": True}
    service = ReportService(
        lambda: _connect(path), output_dir=tmp_path / "out",
        authorize=lambda _actor, _report: allowed["value"],
    )
    gateway = NabiCodeReportGateway(service)
    destination = tmp_path / "clientes.csv"
    gateway.export_query(ReportQuery("clientes"), "CSV", str(destination), actor="operador")
    assert len(destination.read_text(encoding="utf-8-sig").splitlines()) == 3
    allowed["value"] = False
    import pytest
    with pytest.raises(PermissionError):
        gateway.export_query(ReportQuery("clientes"), "CSV", str(destination), actor="bloqueado")
