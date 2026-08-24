from __future__ import annotations

import sqlite3
from decimal import Decimal

from commercial.application.report_dto import ReportQuery
from commercial.infrastructure.report_gateway import NabiCodeReportGateway
from services.report_service import ReportService


def _connection(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def test_gateway_reutiliza_servico_oficial_sem_expor_nfe(tmp_path):
    database = tmp_path / "reports.db"
    connection = _connection(database)
    connection.executescript("""
        CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE movimentacoes(
            id INTEGER PRIMARY KEY, data TEXT, tipo TEXT, descricao TEXT,
            valor_total TEXT, status TEXT, usuario TEXT
        );
        INSERT INTO movimentacoes VALUES
            (1,'2026-08-23','VENDA','Mesa','10.50','PAGO','operador'),
            (2,'2026-08-23','PAGAMENTO','Ficha','10.50','PAGO','operador');
    """)
    connection.commit(); connection.close()
    service = ReportService(lambda: _connection(database), output_dir=tmp_path / "out")
    gateway = NabiCodeReportGateway(service)

    assert "nfe" not in {option.report_id for option in gateway.available_reports()}
    document = gateway.generate(ReportQuery("vendas"), actor="operador")
    assert document.row_count == 1
    assert gateway.summary(document).value_total == Decimal("10.50")


def test_gateway_exporta_csv_atomico_pelo_servico_existente(tmp_path):
    database = tmp_path / "reports.db"
    connection = _connection(database)
    connection.executescript("""
        CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE clientes(id INTEGER PRIMARY KEY, nome TEXT, saldo_devedor TEXT);
        INSERT INTO clientes VALUES(1,'Ana','20.00');
    """)
    connection.commit(); connection.close()
    gateway = NabiCodeReportGateway(
        ReportService(lambda: _connection(database), output_dir=tmp_path / "out")
    )
    document = gateway.generate(ReportQuery("clientes"), actor="operador")
    destination = tmp_path / "clientes.csv"
    assert gateway.export(document, "CSV", str(destination), actor="operador") == str(destination)
    assert destination.read_text(encoding="utf-8-sig").startswith("id;nome;saldo_devedor")


def test_gateway_nao_importa_fiscal_sefaz_ou_interface():
    source = __import__("pathlib").Path(
        __file__
    ).parents[1].joinpath("commercial/infrastructure/report_gateway.py").read_text(encoding="utf-8").lower()
    for forbidden in ("fiscal_service", "sefaz", "ui_qt", "sqlite3"):
        assert forbidden not in source
