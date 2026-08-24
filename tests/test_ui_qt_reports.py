from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from commercial.application.report_dto import (
    ReportDocument, ReportIndicators, ReportOption, ReportSummary,
)
from ui_qt.commercial.report_dialog import ReportDialog


APP = QApplication.instance() or QApplication([])


class Application:
    def __init__(self): self.generated = 0; self.exports = []
    def available_reports(self): return (ReportOption("vendas", "Vendas"),)
    def generate(self, query, *, actor):
        self.generated += 1
        return ReportDocument(
            "vendas", "Vendas", ("id", "valor_total"), ((1, "5.00"),),
            (), datetime.now().isoformat(),
        )
    def summary(self, document): return ReportSummary(1, Decimal("5"))
    def indicators(self, start, end):
        return ReportIndicators(Decimal("5"), Decimal("2"), Decimal("1"), 3, 4)
    def export(self, document, fmt, destination, *, actor):
        self.exports.append((document, fmt, str(destination), actor)); return str(destination)


def _enter(*, shift=False, repeat=False):
    modifiers = Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier
    return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, modifiers, "\r", repeat, 1)


def test_enter_avanca_uma_etapa_e_botao_gera_uma_vez():
    application = Application(); dialog = ReportDialog(application, "operador")
    dialog.show(); APP.processEvents()
    assert dialog.eventFilter(dialog.report_type, _enter())
    APP.processEvents()
    assert dialog.start_date.hasFocus()
    assert dialog.eventFilter(dialog.generate_button, _enter())
    assert application.generated == 1
    assert dialog.table.rowCount() == 1 and dialog.csv.isEnabled()
    dialog.close()


def test_shift_enter_volta_e_auto_repeat_nao_gera():
    application = Application(); dialog = ReportDialog(application, "operador")
    dialog.show(); dialog.search.setFocus(); APP.processEvents()
    assert dialog.eventFilter(dialog.search, _enter(shift=True))
    APP.processEvents()
    assert dialog.end_date.hasFocus()
    assert dialog.eventFilter(dialog.generate_button, _enter(repeat=True))
    assert application.generated == 0
    dialog.close()


def test_geracao_normal_atualiza_resumo_sem_acao_fiscal():
    application = Application(); dialog = ReportDialog(application, "operador")
    dialog.generate()
    assert application.generated == 1
    assert "R$ 5,00" in dialog.total.text()
    assert "Estoque baixo 3" in dialog.indicators.text()
    dialog.close()


def test_gui_nao_importa_banco_fiscal_sefaz_ou_legacy():
    import ast
    from pathlib import Path
    source = Path(__file__).parents[1].joinpath(
        "ui_qt/commercial/report_dialog.py"
    ).read_text(encoding="utf-8")
    imported = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(str(node.module or "").lower())
    for forbidden in ("sqlite3", "database", "repositories", "fiscal", "sefaz", "nabicode_legacy"):
        assert not any(forbidden in module for module in imported)
