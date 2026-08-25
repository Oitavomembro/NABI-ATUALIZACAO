from __future__ import annotations

import hashlib
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from commercial.application.accountant_delivery_dto import AccountantDeliveryStatus
from ui_qt.commercial.accountant_delivery_dialog import AccountantDeliveryDialog


APP = QApplication.instance() or QApplication([])


class Pool:
    def __init__(self): self.workers = []
    def start(self, worker): self.workers.append(worker); worker.run()


class Application:
    def __init__(self): self.calls = []
    def review(self, **kwargs):
        self.calls.append("review")
        return SimpleNamespace(idempotency_key="acct-12345678")
    def _result(self, operation, status):
        self.calls.append(operation)
        return AccountantDeliveryStatus("acct-12345678", status, 1)
    def prepare(self, plan): return self._result("prepare", "PREPARADO")
    def enqueue(self, plan): return self._result("enqueue", "ENFILEIRADO")
    def dispatch(self, plan): return self._result("dispatch", "ENVIADO_AO_TRANSPORTE")
    def check_receipt(self, plan): return self._result("check_receipt", "RECEBIDO_CONFIRMADO")


def package(tmp_path):
    path = tmp_path / "pacote.zip"
    path.write_bytes(b"pacote")
    return SimpleNamespace(
        path=str(path), cnpj="12345678000195", competence="2026-08",
        profile="ESSENCIAL", package_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def ready(dialog, tmp_path):
    destination = tmp_path / "destino"
    destination.mkdir()
    dialog.recipient.setText("Contador")
    dialog.destination.setText(str(destination))
    dialog.cnpj_confirmed.setChecked(True)
    dialog.consent.setChecked(True)
    dialog._review()


def test_fluxo_exige_cinco_acoes_e_envio_nao_e_recebimento(tmp_path):
    application = Application()
    dialog = AccountantDeliveryDialog(application, package(tmp_path), worker_pool=Pool())
    ready(dialog, tmp_path)
    assert application.calls == ["review"] and dialog.prepare.isEnabled()
    dialog._run("prepare"); assert dialog.enqueue.isEnabled()
    dialog._run("enqueue"); assert dialog.dispatch.isEnabled()
    dialog._run("dispatch")
    assert "não está confirmado" in dialog.status.text() and dialog.check.isEnabled()
    assert not dialog.dispatch.isEnabled()
    dialog._run("check_receipt")
    assert "não significa" in dialog.status.text() and "aprovou" in dialog.status.text()
    assert application.calls == ["review", "prepare", "enqueue", "dispatch", "check_receipt"]
    dialog.close()


def test_resultado_desconhecido_so_permite_consulta_e_enter_repetido_nao_age(tmp_path):
    application = Application()
    dialog = AccountantDeliveryDialog(application, package(tmp_path), worker_pool=Pool())
    ready(dialog, tmp_path)
    result = AccountantDeliveryStatus("acct-12345678", "DESCONHECIDO", 1)
    dialog._completed(dialog._generation, "dispatch", result, None)
    assert dialog.check.isEnabled() and not dialog.dispatch.isEnabled() and not dialog.enqueue.isEnabled()
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "", True, 1
    )
    before = list(application.calls)
    assert dialog.eventFilter(dialog.check, event) is True
    assert application.calls == before
    dialog.close()
