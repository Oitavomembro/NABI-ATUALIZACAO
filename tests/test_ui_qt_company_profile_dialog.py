from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QDate, QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog

from services.company_profile_service import CompanyProfileService
from services.security_service import SecurityService
from ui_qt.administration.company_profile_dialog import CompanyProfileDialog


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def environment(tmp_path, app):
    database = tmp_path / "profile-ui.db"
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE configuracoes(chave TEXT PRIMARY KEY, valor TEXT);
        CREATE TABLE auditoria(id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT,usuario TEXT,
          modulo TEXT,acao TEXT,objeto TEXT,detalhes TEXT,resultado TEXT);
        CREATE TABLE log_acesso_admin(id INTEGER PRIMARY KEY AUTOINCREMENT,data TEXT,sucesso INTEGER,detalhes TEXT);
    """)
    connection.commit(); connection.close()
    connect = lambda: sqlite3.connect(database)
    security = SecurityService(connect)
    security.complete_initial_setup(
        username="admin", display_name="Administrador", password="SenhaForte123",
        store_name="Empresa", document="12345678000195",
    )
    assert security.authenticate("admin", "SenhaForte123") is not None
    service = CompanyProfileService(
        connect, security_service=security,
        clock=lambda: datetime(2026, 8, 24, 12, 0, 0),
    )
    messages = []
    dialog = CompanyProfileDialog(service, notifier=lambda kind, text: messages.append((kind, text)))
    return database, security, service, dialog, messages


def fill_valid(dialog):
    dialog.cnpj.setText("12.345.678/0001-95")
    dialog.legal_name.setText("EMPRESA TESTE LTDA")
    dialog.tax_regime.setCurrentIndex(dialog.tax_regime.findData("SIMPLES_NACIONAL"))
    dialog.classification.setCurrentIndex(dialog.classification.findData("ME"))
    dialog.activities.setPlainText("4711302 | Comércio varejista | PRINCIPAL")
    dialog.state.setCurrentIndex(dialog.state.findData("BA"))
    dialog.city.setText("JUAZEIRO")
    dialog.state_registration.setText("ISENTO")
    dialog.municipal_registration.setText("12345")
    dialog.operation_types.setText("VAREJO")
    dialog.document_types.setText("NFE, NFCE")
    dialog.source.setText("DOCUMENTO CONFERIDO PELO RESPONSAVEL")
    dialog.source_date.setDate(QDate.fromString("2026-08-20", "yyyy-MM-dd"))
    dialog.effective_from.setDate(QDate.fromString("2026-08-24", "yyyy-MM-dd"))
    dialog.change_reason.setText("Cadastro inicial confirmado pelo responsável")


def key(widget, *, shift=False, auto_repeat=False):
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,
        "\r", auto_repeat, 1,
    )
    QApplication.sendEvent(widget, event)


def test_revisao_obrigatoria_e_confirmacao_persiste_uma_vez(environment):
    _, _, service, dialog, messages = environment
    fill_valid(dialog)
    assert dialog.confirm_button.isEnabled() is False
    assert dialog.review() is True
    assert service.history() == ()
    assert dialog._reviewed.confirmed is False
    dialog.review_ack.setChecked(True)
    assert dialog.confirm_button.isEnabled() is True
    assert dialog.confirm() is True
    assert dialog.result() == QDialog.DialogCode.Accepted
    history = service.history()
    assert len(history) == 1 and history[0].confirmed_by == "admin"
    assert messages[-1][0] == "info"


def test_reentrada_de_confirmacao_e_consumida_sem_segunda_gravacao(environment):
    _, _, service, dialog, _ = environment
    fill_valid(dialog); assert dialog.review(); dialog.review_ack.setChecked(True)
    dialog._confirming = True
    assert dialog.confirm() is False
    dialog._confirming = False
    assert service.history() == ()


def test_edicao_invalida_revisao_e_impede_persistencia(environment):
    _, _, service, dialog, _ = environment
    fill_valid(dialog); assert dialog.review()
    dialog._back_to_form(); dialog.legal_name.setText("NOME ALTERADO")
    assert dialog._reviewed is None and not dialog.confirm_button.isEnabled()
    assert dialog.confirm() is False and service.history() == ()


def test_migracao_legada_e_rascunho_sem_autoconfirmacao(environment):
    database, _, service, dialog, messages = environment
    legacy = {"cnpj":"12345678000195", "tax_regime":"SIMPLES_NACIONAL", "state":"BA",
              "issuer":{"name":"EMPRESA LEGADA", "city":"JUAZEIRO"}}
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO configuracoes VALUES('fiscal.config.v1',?)", (json.dumps(legacy),))
    connection.commit(); connection.close()
    dialog.load_legacy_draft()
    assert dialog.legal_name.text() == "EMPRESA LEGADA"
    assert dialog._reviewed is None and not dialog.confirm_button.isEnabled()
    assert service.history() == ()
    assert "somente como rascunho" in messages[-1][1]


def test_texto_separa_licenca_permissao_perfil_e_readiness_nao_habilita_fiscal(environment):
    _, _, _, dialog, _ = environment
    visible = " ".join(label.text() for label in dialog.findChildren(type(dialog.readiness_label)))
    assert "Licença" in visible and "permissões" in visible
    assert "enables_fiscal=false" in visible


def test_enter_shift_enter_e_auto_repeat_sao_deterministicos(environment):
    _, _, _, dialog, _ = environment
    dialog.show(); dialog.cnpj.setFocus(); QApplication.processEvents()
    key(dialog.cnpj, auto_repeat=True)
    assert dialog.cnpj.hasFocus()
    key(dialog.cnpj)
    assert dialog.legal_name.hasFocus()
    key(dialog.legal_name, shift=True)
    assert dialog.cnpj.hasFocus()
    fill_valid(dialog); dialog.review_button.setFocus(); QApplication.processEvents()
    key(dialog.review_button, auto_repeat=True)
    assert dialog._reviewed is None
    key(dialog.review_button)
    assert dialog._reviewed is not None


def test_escape_fecha_sem_persistir(environment):
    _, _, service, dialog, _ = environment
    dialog.show(); fill_valid(dialog); dialog.cnpj.setFocus(); QApplication.processEvents()
    escape = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(dialog.cnpj, escape)
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert service.history() == ()


def test_conflito_otimista_preserva_rascunho_e_nao_sobrescreve(environment):
    _, _, service, dialog, messages = environment
    fill_valid(dialog); assert dialog.review(); dialog.review_ack.setChecked(True)
    competing = dialog._draft()
    service.confirm(
        competing.__class__(**{**competing.__dict__, "confirmed": True}),
        change_reason="Alteração concorrente confirmada externamente", expected_current_version=0,
    )
    assert dialog.confirm() is False
    assert len(service.history()) == 1
    assert any("mudou desde a revisão" in text for _, text in messages)


def test_sem_permissao_real_nao_confirma(environment):
    database, security, service, dialog, messages = environment
    fill_valid(dialog); assert dialog.review()
    dialog.review_ack.setChecked(True)
    security.logout()
    assert dialog.confirm() is False
    connection = sqlite3.connect(database)
    assert connection.execute(
        "SELECT 1 FROM configuracoes WHERE chave=?", (service.CONFIG_KEY,)
    ).fetchone() is None
    connection.close()
    assert any("Sessão ativa" in text for _, text in messages)


def test_modulo_nao_importa_shell_ou_ativacao_fiscal():
    import inspect
    import ui_qt.administration.company_profile_dialog as module
    source = inspect.getsource(module)
    assert "main_qt" not in source and "ui_qt.app" not in source
    assert "fiscal.enabled" not in source and "enables_fiscal=True" not in source
