from datetime import datetime

from helpers.value_parsing import parse_flexible_number, parse_system_date


def test_parse_flexible_number_preserves_legacy_formats():
    assert parse_flexible_number("") == 0.0
    assert parse_flexible_number("1.234,56") == 1234.56
    assert parse_flexible_number("12,5") == 12.5
    assert parse_flexible_number("12.5") == 12.5


def test_parse_system_date_preserves_legacy_formats():
    assert parse_system_date("2026-08-07") == datetime(2026, 8, 7)
    assert parse_system_date("07/08/2026 12:30:15") == datetime(2026, 8, 7, 12, 30, 15)
    assert parse_system_date("07/08/2026") == datetime(2026, 8, 7)
    assert parse_system_date("inválida") is None
