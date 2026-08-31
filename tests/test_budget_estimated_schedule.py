from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest

from commercial.application.dto import BudgetDocument
from commercial.domain.cart import CartItem
from commercial.infrastructure.budget_gateway import NabiCodeBudgetGateway


def proposal(**kwargs):
    values = dict(budget_id="B1", created_at="2026-08-30", customer_id=1,
                  customer_name="TESTE", items=(CartItem("ITEM", 1, "100"),),
                  total="100", installments=3, first_due_date="2028-01-31")
    values.update(kwargs)
    return BudgetDocument(**values)


def test_month_end_leap_year_and_exact_cents():
    rows = proposal().estimated_schedule()
    assert [row.due_date for row in rows] == [date(2028, 1, 31), date(2028, 2, 29), date(2028, 3, 31)]
    assert [row.amount for row in rows] == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]
    assert sum(row.amount for row in rows) == Decimal("100")


def test_old_budget_has_no_invented_dates_and_full_entry_no_installments():
    assert proposal(first_due_date=None).estimated_schedule() == ()
    assert proposal(entry_amount="100").estimated_schedule() == ()


def test_stress_all_installment_counts_preserve_money():
    for count in range(1, 121):
        rows = proposal(installments=count, entry_amount="13.17").estimated_schedule()
        assert len(rows) == count
        assert sum(row.amount for row in rows) == Decimal("86.83")
        assert all(row.amount > 0 for row in rows)
        assert all(a.due_date < b.due_date for a, b in zip(rows, rows[1:]))


def test_bad_terms_never_reach_storage():
    pdv = Mock()
    gateway = NabiCodeBudgetGateway(pdv=pdv, receipts=Mock(), printing=Mock(), pdf=Mock(), final_consumer_id=1)
    for extra in ({"first_due_date": "not-a-date"}, {"entry_amount": "101"},
                  {"entry_amount": "99.99", "installments": 2, "first_due_date": "2028-01-31"}):
        with pytest.raises(ValueError):
            gateway.save(customer_id=1, customer_name="TESTE", items=proposal().items, **extra)
    pdv.salvar_documento.assert_not_called()


def test_preview_schedule_is_explicitly_not_collection():
    text = NabiCodeBudgetGateway._terms_text(proposal())
    assert "NÃO SÃO COBRANÇAS" in text
    assert "02/03  29/02/2028  R$ 33,33" in text


def test_dialog_date_is_opt_in_and_exported_without_confirmation_bypass():
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication, QDialog
    from ui_qt.commercial.budget_dialog import BudgetTermsDialog

    app = QApplication.instance() or QApplication([])
    dialog = BudgetTermsDialog("100")
    try:
        assert dialog.terms["first_due_date"] is None
        assert not dialog.first_due.isEnabled()
        assert dialog.result() == QDialog.DialogCode.Rejected
        dialog.schedule_enabled.setChecked(True)
        dialog.first_due.setDate(QDate(2028, 1, 31))
        assert dialog.terms["first_due_date"] == date(2028, 1, 31)
        dialog.schedule_enabled.setChecked(False)
        assert dialog.terms["first_due_date"] is None
    finally:
        dialog.close()
