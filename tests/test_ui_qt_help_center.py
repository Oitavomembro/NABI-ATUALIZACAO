from __future__ import annotations

import ast
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog

from services.help_center_service import HelpCenterDiagnosticService
from ui_qt.administration.help_center_dialog import HelpCenterDialog


APP = QApplication.instance() or QApplication([])


class Pool:
    def __init__(self): self.workers = []
    def start(self, worker): self.workers.append(worker)


def service(tmp_path, *, secret="ok"):
    return HelpCenterDiagnosticService(
        persistent_dirs=[tmp_path],
        database_probe=lambda: {"state":"SAUDAVEL", "message":secret},
        backup_probe=lambda: {"state":"ALERTA", "message":"backup pendente"},
        printer_probe=lambda: {"state":"FALHA", "message":"impressora ausente"},
        nabi_probe=None,
    )


def enter(*, shift=False, repeat=False):
    return QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,
        "\r", repeat, 1,
    )


def complete(pool):
    pool.workers[-1].run(); APP.processEvents()


def test_carrega_fora_da_ui_renderiza_quatro_estados_e_detalhes(tmp_path):
    pool = Pool(); dialog = HelpCenterDialog(service(tmp_path), worker_pool=pool)
    assert dialog.reload() is True and dialog.run_button.isEnabled() is False
    complete(pool)
    states = " ".join(card.text() for card in dialog.cards)
    for state in ("SAUDAVEL", "ALERTA", "FALHA", "INCONCLUSIVO"): assert state in states
    assert dialog.report_button.isEnabled() and "não executou reparo" in dialog.details.toPlainText()
    dialog.close()


def test_reentrada_bloqueada_e_resposta_atrasada_descartada(tmp_path):
    pool = Pool(); dialog = HelpCenterDialog(service(tmp_path), worker_pool=pool)
    assert dialog.reload() is True and dialog.reload() is False and len(pool.workers) == 1
    old = dialog._generation; dialog._generation += 1
    dialog._loaded(old, service(tmp_path).run(), None)
    assert dialog.results == () and dialog.progress.text() == "Verificando..."
    dialog.close()


def test_nova_execucao_apos_conclusao_nao_reutiliza_resultado(tmp_path):
    pool = Pool(); dialog = HelpCenterDialog(service(tmp_path), worker_pool=pool)
    assert dialog.reload(); complete(pool); first = dialog.results
    assert dialog.reload() and len(pool.workers) == 2
    assert not dialog.report_button.isEnabled()
    complete(pool)
    assert dialog.results == first and dialog.report_button.isEnabled()
    dialog.close()


def test_detalhe_e_relatorio_redigem_segredos_e_exportam_atomicamente(tmp_path):
    secret = "senha=segredo 123.456.789-09 pessoa@empresa.com C:\\Users\\pessoa\\dados"
    pool = Pool(); messages=[]
    dialog = HelpCenterDialog(service(tmp_path, secret=secret), worker_pool=pool,
                              notifier=lambda kind, text: messages.append((kind,text)))
    dialog.reload(); complete(pool); dialog.show_detail(2)
    report = dialog.export_report(tmp_path / "socorro.json")
    rendered = dialog.details.toPlainText() + report.read_text(encoding="utf-8")
    assert "segredo" not in rendered and "123.456.789-09" not in rendered
    assert "pessoa@empresa.com" not in rendered and "C:\\Users\\pessoa" not in rendered
    assert json.loads(report.read_text(encoding="utf-8"))["scope"] == "DIAGNOSTICO_SOMENTE_LEITURA"
    assert messages[-1][0] == "info"
    dialog.close()


def test_enter_shift_enter_escape_e_auto_repeat(tmp_path):
    pool = Pool(); dialog = HelpCenterDialog(service(tmp_path), worker_pool=pool)
    dialog.show(); dialog.run_button.setFocus(); APP.processEvents()
    APP.sendEvent(dialog.run_button, enter(repeat=True)); assert len(pool.workers) == 0
    APP.sendEvent(dialog.run_button, enter()); assert len(pool.workers) == 1
    complete(pool); dialog.cards[0].setFocus(); APP.processEvents()
    APP.sendEvent(dialog.cards[0], enter(repeat=True)); assert dialog.cards[0].hasFocus()
    APP.sendEvent(dialog.cards[0], enter()); assert dialog.cards[1].hasFocus()
    APP.sendEvent(dialog.cards[1], enter(shift=True)); assert dialog.cards[0].hasFocus()
    APP.sendEvent(dialog.cards[0], QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_falha_do_worker_e_sanitizada_sem_resultado_reutilizavel(tmp_path):
    class Broken:
        def run(self): raise RuntimeError("senha=segredo")
    pool = Pool(); messages=[]
    dialog = HelpCenterDialog(Broken(), worker_pool=pool,
                              notifier=lambda kind,text: messages.append((kind,text)))
    dialog.reload(); complete(pool)
    assert dialog.results == () and not dialog.report_button.isEnabled()
    assert "segredo" not in repr(messages) and "RuntimeError" in repr(messages)
    dialog.close()


def test_ui_nao_importa_camadas_operacionais_ou_shell():
    source = Path(__file__).parents[1].joinpath("ui_qt/administration/help_center_dialog.py").read_text(encoding="utf-8")
    modules=[]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import): modules.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom): modules.append(str(node.module or "").lower())
    for forbidden in ("main_qt", "ui_qt.app", "shell", "database", "sqlite", "fiscal", "caixa", "estoque", "venda", "licensing", "subprocess"):
        assert not any(forbidden in module for module in modules)
