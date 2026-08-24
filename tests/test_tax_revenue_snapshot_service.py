import sqlite3
from datetime import date
from decimal import Decimal

import pytest

from services.tax_revenue_snapshot_service import TaxRevenueSnapshotService


def database(tmp_path):
    path = tmp_path / "tax.db"
    connection = sqlite3.connect(path)
    connection.execute("""
        CREATE TABLE movimentacoes(
            tipo TEXT, data TEXT, valor REAL, valor_decimal TEXT,
            status_pagamento TEXT, origem_sistema TEXT
        )
    """)
    connection.executemany("INSERT INTO movimentacoes VALUES(?,?,?,?,?,?)", [
        ("COMPRA", "2026-08-02 10:00:00", 999, "100.10", "PAGO", ""),
        ("VENDA", "03/08/2026 11:00:00", 20, "20.02", "PENDENTE", ""),
        ("VENDA", "2026-08-04", 30, "30", "CANCELADO", ""),
        ("VENDA", "2026-08-05", 400, "400", "PAGO", "FINANCEIRO"),
        ("PAGAMENTO", "2026-08-05", 1000, "1000", "PAGO", ""),
        ("VENDA_HISTORICA", "2025-08-01", 50, "50", "PAGO", "MIGRACAO"),
        ("VENDA", "2026-07-31", 75, "75", "PAGO", ""),
        ("VENDA", "data ruim", 90, "90", "PAGO", ""),
    ])
    connection.commit()
    connection.close()
    return lambda: _connect(path)


def _connect(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def test_snapshot_separa_faturamento_recebimento_cancelamento_e_espelho(tmp_path):
    result = TaxRevenueSnapshotService(database(tmp_path)).read_competence_month(
        period_start=date(2026, 8, 1), calculated_through=date(2026, 8, 10)
    )
    assert result.revenue_to_date == Decimal("120.12")
    assert result.rbt12_revenue == Decimal("125")
    assert result.included_sales == 2
    assert result.cancelled_sales == 1
    assert result.mirrored_rows == 1
    assert result.invalid_date_rows == 1
    assert any("data inválida" in warning for warning in result.warnings)


def test_exige_mes_e_data_da_consulta_coerentes(tmp_path):
    service = TaxRevenueSnapshotService(database(tmp_path))
    with pytest.raises(ValueError, match="primeiro dia"):
        service.read_competence_month(
            period_start=date(2026, 8, 2), calculated_through=date(2026, 8, 10)
        )
    with pytest.raises(ValueError, match="pertencer ao mês"):
        service.read_competence_month(
            period_start=date(2026, 8, 1), calculated_through=date(2026, 9, 1)
        )


def test_bloqueia_valor_negativo_em_vez_de_mascarar(tmp_path):
    factory = database(tmp_path)
    connection = factory()
    connection.execute(
        "INSERT INTO movimentacoes VALUES('VENDA','2026-08-06',-1,'-1','PAGO','')"
    )
    connection.commit()
    connection.close()
    with pytest.raises(ValueError, match="valor negativo"):
        TaxRevenueSnapshotService(factory).read_competence_month(
            period_start=date(2026, 8, 1), calculated_through=date(2026, 8, 10)
        )
