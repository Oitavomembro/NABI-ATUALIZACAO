from types import SimpleNamespace

import pytest

from helpers.legacy_reduction_helpers import (
    database_report_text,
    format_number_br,
    mysql_migration_report_text,
    parse_nonnegative_number,
)


def test_parse_nonnegative_number_preserves_legacy_formats():
    assert parse_nonnegative_number("1.234,56", "Valor") == pytest.approx(1234.56)
    assert parse_nonnegative_number("1234.56", "Valor") == pytest.approx(1234.56)
    assert parse_nonnegative_number("0", "Valor") == 0.0


def test_parse_nonnegative_number_validation_messages():
    with pytest.raises(ValueError, match="Quantidade deve ser maior que zero"):
        parse_nonnegative_number("0", "Quantidade", greater_than_zero=True)
    with pytest.raises(ValueError, match="Custo não pode ser negativo"):
        parse_nonnegative_number("-1", "Custo")
    with pytest.raises(ValueError, match="Preço inválido"):
        parse_nonnegative_number("abc", "Preço")


def test_format_number_br_matches_legacy_output():
    assert format_number_br(12.5000) == "12,5"
    assert format_number_br(12.3456, 2) == "12,35"
    assert format_number_br(0, 4) == "0"


def test_database_report_text_matches_admin_panel_contract():
    report = SimpleNamespace(
        integrity="ok",
        foreign_key_errors=[("x",)],
        schema_version=12,
        expected_schema_version=12,
        missing_tables=[],
        freelist_count=2,
        page_count=40,
        valid=True,
    )
    text = database_report_text(report)
    assert "Integridade: ok" in text
    assert "Chaves estrangeiras: 1 erro(s)" in text
    assert "Schema: 12 / esperado 12" in text
    assert "Tabelas ausentes: nenhuma" in text
    assert "Status: VÁLIDO" in text


def test_mysql_migration_report_text_preserves_report_fields():
    report = {
        "arquivo": "backup.sql",
        "tamanho": 1024 * 1024,
        "tabelas": ["clientes", "produtos"],
        "contagens": {"clientes": 3, "produtos": 7},
        "clientes": 3,
        "duplicados_cpf": 1,
        "duplicados_ficha": 0,
        "duplicados_codigo": 0,
        "sem_nome": 0,
        "datas_invalidas": 2,
        "telefones_invalidos": 1,
    }
    text = mysql_migration_report_text(report)
    assert "backup.sql" in text
    assert "1.00 MB" in text
    assert "clientes" in text and "3" in text
    assert "produtos" in text and "7" in text
    assert "STATUS: SIMULAÇÃO CONCLUÍDA" in text
