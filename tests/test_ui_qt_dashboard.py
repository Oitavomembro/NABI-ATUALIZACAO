from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from repositories.dashboard_repository import DayHistoryPage, DayMovement, DashboardIndicators
from ui_qt.administration.dashboard_dialog import DashboardDialog


class Pool:
    def __init__(self): self.workers = []
    def start(self, worker): self.workers.append(worker)


def snapshot(total=1, offset=0):
    movement = DayMovement(7, "24/08/2026 10:30:00", "MARIA", "COMPRA", "MESA", Decimal("25"))
    return SimpleNamespace(
        indicators=DashboardIndicators(2, Decimal("80"), 15),
        history=DayHistoryPage((movement,) if offset == 0 else (), Decimal("25"), Decimal("10"), total, 50, offset),
    )


def setup_module():
    global APP
    APP = QApplication.instance() or QApplication([])


def test_construcao_nao_consulta_na_thread_da_interface():
    application = Mock(); pool = Pool()
    dialog = DashboardDialog(application, worker_pool=pool)
    application.load.assert_not_called(); assert len(pool.workers) == 1
    dialog.close()


def test_worker_preenche_cartoes_e_historico_legacy():
    application = Mock(); application.load.return_value = snapshot(); pool = Pool()
    dialog = DashboardDialog(application, worker_pool=pool); pool.workers[0].run(); APP.processEvents()
    application.load.assert_called_once_with(limit=50, offset=0)
    assert "R$ 25,00" in dialog.cards["sales"][1].text()
    assert "R$ 10,00" in dialog.cards["receipts"][1].text()
    assert "2 • R$ 80,00" in dialog.cards["overdue"][1].text()
    assert dialog.cards["products"][1].minimumHeight() >= 82
    assert "qlineargradient" in dialog.cards["products"][1].styleSheet()
    assert "border-bottom:5px" in dialog.cards["products"][1].styleSheet()
    assert dialog.table.item(0, 0).text() == "7"
    assert dialog.table.item(0, 4).text() == "MESA"
    dialog.close()


def test_paginacao_dispara_nova_carga_limitada():
    application = Mock(); application.load.return_value = snapshot(total=120); pool = Pool()
    dialog = DashboardDialog(application, worker_pool=pool); pool.workers[0].run(); APP.processEvents()
    assert dialog.next.isEnabled(); dialog.next_page()
    assert dialog.offset == 50 and len(pool.workers) == 2
    pool.workers[1].run(); APP.processEvents()
    assert application.load.call_args.kwargs == {"limit": 50, "offset": 50}
    dialog.close()


def test_resultado_atrasado_nao_sobrescreve_geracao_atual():
    application = Mock(); pool = Pool(); dialog = DashboardDialog(application, worker_pool=pool)
    first = pool.workers[0]; dialog.reload(); second = pool.workers[1]
    application.load.return_value = snapshot(); second.run(); APP.processEvents()
    text = dialog.cards["sales"][1].text(); application.load.return_value = snapshot(total=999)
    first.run(); APP.processEvents(); assert dialog.cards["sales"][1].text() == text
    dialog.close()


def test_enter_na_tabela_e_consumido_sem_acao_ou_auto_repeat():
    dialog = DashboardDialog(Mock(), worker_pool=Pool())
    for repeat in (False, True):
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "", repeat, 1)
        assert dialog.eventFilter(dialog.table, event) is True
    dialog.close()
