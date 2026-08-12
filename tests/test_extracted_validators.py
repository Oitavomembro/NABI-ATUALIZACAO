from decimal import Decimal

import pytest

from validators import MovementValidator, NFeImportValidator, ReceiptValidator, StockValidator


def test_movement_validator_normalizes_update_values():
    assert MovementValidator.movement_id("7") == 7
    assert MovementValidator.update_values("  Ajuste  ", "12.50") == ("Ajuste", 12.5)


@pytest.mark.parametrize("value", [0, -1])
def test_movement_validator_rejects_non_positive_id(value):
    with pytest.raises(ValueError, match="maior que zero"):
        MovementValidator.movement_id(value)


@pytest.mark.parametrize(
    ("action", "product_id", "expected"),
    [("vincular", 1, "VINCULAR"), ("ATUALIZAR", 2, "ATUALIZAR"), ("criar", None, "CRIAR")],
)
def test_nfe_import_validator_normalizes_valid_decisions(action, product_id, expected):
    assert NFeImportValidator.decision(action, product_id) == expected


def test_receipt_validator_preserves_aliases_and_values():
    items = [{"item": "Mesa", "qtd": 2, "preco": 10, "subtotal": 20}]
    assert ReceiptValidator.sale_header("cupom", items, "20") == ("VENDA", 20.0)
    assert ReceiptValidator.sale_item(items[0]) == ("Mesa", 2.0, 10.0, 20.0)
    ReceiptValidator.matching_total(20.01, 20.0)


def test_stock_validator_quantizes_and_enforces_positive_quantity():
    assert StockValidator.quantity("1.23456") == Decimal("1.2346")
    assert StockValidator.quantity(0, allow_zero=True) == Decimal("0.0000")
    with pytest.raises(ValueError, match="maior que zero"):
        StockValidator.quantity(0)
