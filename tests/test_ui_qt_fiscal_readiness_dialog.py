import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox

from ui_qt.administration.fiscal_readiness_dialog import (
    FiscalConfigurationDialog, FiscalReadinessDialog,
)


def setup_module():
    global APP
    APP = QApplication.instance() or QApplication([])


def snapshot():
    return SimpleNamespace(
        state="BLOQUEADO", environment="HOMOLOGACAO", enabled=False,
        issuer_document="Não configurado", issuer_state="BA",
        tax_regime="SIMPLES_NACIONAL", certificate_configured=False,
        certificate_name="Não configurado", models=(), notices=(),
    )


def configuration_application():
    application = Mock()
    application._fiscal.STATE_CODES = {"BA": "29"}
    application._fiscal.TAX_REGIME_LABELS = {"SIMPLES_NACIONAL": "Simples Nacional"}
    application.configuration.return_value = {
        "cnpj": "47584215000160", "state": "BA",
        "tax_regime": "SIMPLES_NACIONAL", "enabled_models": ["55", "65"],
        "default_model": "65", "sale_series_55": 1, "sale_series_65": 1,
        "certificate_path": "", "issuer": {"name": "Empresa"},
    }
    return application


def test_clique_configurar_abre_dialogo_exatamente_uma_vez():
    application = Mock(); application.snapshot.return_value = snapshot()
    dialog = FiscalReadinessDialog(application)
    with patch("ui_qt.administration.fiscal_readiness_dialog.FiscalConfigurationDialog") as factory:
        child = factory.return_value; child.exec.return_value = QDialog.DialogCode.Rejected
        QTest.mouseClick(dialog.configure_button, Qt.MouseButton.LeftButton)
        factory.assert_called_once_with(application, dialog)
        child.exec.assert_called_once_with()
    dialog.close()


def test_clique_atualizar_recarrega_e_fechar_encerra():
    application = Mock(); application.snapshot.return_value = snapshot()
    dialog = FiscalReadinessDialog(application)
    QTest.mouseClick(dialog.refresh_button, Qt.MouseButton.LeftButton)
    assert application.snapshot.call_count == 2
    QTest.mouseClick(dialog.close_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_atualizacoes_repetidas_substituem_conteudo_sem_sobrepor_rotulos():
    application = Mock(); application.snapshot.return_value = snapshot()
    dialog = FiscalReadinessDialog(application)
    for _ in range(3):
        assert dialog.reload() is True
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    labels = [label.text() for label in dialog.findChildren(QLabel)]
    assert labels.count("Ambiente") == 1
    assert labels.count("CNPJ emitente") == 1
    assert labels.count("Certificado A1") == 1
    dialog.close()


def test_enter_configura_uma_vez_e_auto_repeat_nao_abre():
    application = Mock(); application.snapshot.return_value = snapshot()
    dialog = FiscalReadinessDialog(application); dialog.configure = Mock(return_value=False)
    enter = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    assert dialog.eventFilter(dialog.configure_button, enter) is True
    dialog.configure.assert_called_once_with()
    repeated = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier,
        "", True, 2,
    )
    assert dialog.eventFilter(dialog.configure_button, repeated) is True
    assert dialog.configure.call_count == 1
    dialog.close()


def test_shift_enter_apenas_move_foco_sem_executar():
    application = Mock(); application.snapshot.return_value = snapshot()
    dialog = FiscalReadinessDialog(application); dialog.configure = Mock()
    dialog.show(); dialog.activateWindow(); APP.processEvents()
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier,
    )
    assert dialog.eventFilter(dialog.refresh_button, event) is True
    APP.processEvents()
    assert dialog.focusWidget() is dialog.configure_button
    dialog.configure.assert_not_called(); dialog.close()


def test_configuracao_seleciona_certificado_por_clique():
    dialog = FiscalConfigurationDialog(configuration_application())
    with patch(
        "ui_qt.administration.fiscal_readiness_dialog.QFileDialog.getOpenFileName",
        return_value=("C:/certificados/empresa.pfx", "Certificado A1"),
    ):
        QTest.mouseClick(dialog.browse_button, Qt.MouseButton.LeftButton)
    assert dialog.certificate.text() == "C:/certificados/empresa.pfx"
    dialog.close()


def test_selecao_de_certificado_cancelada_preserva_caminho():
    application = configuration_application()
    application.configuration.return_value["certificate_path"] = "C:/certificados/anterior.pfx"
    dialog = FiscalConfigurationDialog(application)
    with patch(
        "ui_qt.administration.fiscal_readiness_dialog.QFileDialog.getOpenFileName",
        return_value=("", ""),
    ):
        QTest.mouseClick(dialog.browse_button, Qt.MouseButton.LeftButton)
    assert dialog.certificate.text() == "C:/certificados/anterior.pfx"
    application.configure_homologation.assert_not_called()
    dialog.close()


def test_revisar_salvar_confirma_uma_vez_e_limpa_senha():
    application = configuration_application()
    dialog = FiscalConfigurationDialog(application)
    dialog.certificate.setText("C:/certificados/empresa.pfx")
    dialog.password.setText("segredo")
    with patch(
        "ui_qt.administration.fiscal_readiness_dialog.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ), patch("ui_qt.administration.fiscal_readiness_dialog.QMessageBox.information"):
        QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    application.configure_homologation.assert_called_once()
    assert application.configure_homologation.call_args.kwargs["password"] == "segredo"
    assert dialog.password.text() == ""
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_cancelar_nao_salva_configuracao():
    application = configuration_application()
    dialog = FiscalConfigurationDialog(application)
    QTest.mouseClick(dialog.cancel_button, Qt.MouseButton.LeftButton)
    application.configure_homologation.assert_not_called()
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_revisao_cancelada_preserva_tela_senha_e_nao_salva():
    application = configuration_application()
    dialog = FiscalConfigurationDialog(application)
    dialog.password.setText("segredo-sintetico")
    dialog.show(); APP.processEvents()
    with patch(
        "ui_qt.administration.fiscal_readiness_dialog.QMessageBox.question",
        return_value=QMessageBox.StandardButton.No,
    ):
        QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    application.configure_homologation.assert_not_called()
    assert dialog.password.text() == "segredo-sintetico"
    assert dialog.isVisible()
    dialog.close()


def test_erro_de_certificado_limpa_senha_e_preserva_tela_e_dados():
    application = configuration_application()
    application.configure_homologation.side_effect = ValueError("Certificado inválido")
    dialog = FiscalConfigurationDialog(application)
    dialog.city.setText("Salvador")
    dialog.password.setText("segredo-sintetico")
    dialog.show(); APP.processEvents()
    with patch(
        "ui_qt.administration.fiscal_readiness_dialog.QMessageBox.question",
        return_value=QMessageBox.StandardButton.Yes,
    ), patch("ui_qt.administration.fiscal_readiness_dialog.QMessageBox.warning") as warning:
        QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    warning.assert_called_once()
    assert dialog.password.text() == ""
    assert dialog.city.text() == "Salvador"
    assert dialog.isVisible()
    dialog.close()


def test_configuracao_enter_shift_enter_e_auto_repeat_sao_deterministicos():
    application = configuration_application()
    dialog = FiscalConfigurationDialog(application)
    dialog._browse = Mock(); dialog._save = Mock()
    dialog.show(); dialog.activateWindow(); APP.processEvents()

    for button, action in (
        (dialog.browse_button, dialog._browse),
        (dialog.save_button, dialog._save),
    ):
        button.setFocus()
        enter = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier,
        )
        assert dialog.eventFilter(button, enter) is True
        action.assert_called_once_with()

        shift_enter = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return,
            Qt.KeyboardModifier.ShiftModifier,
        )
        assert dialog.eventFilter(button, shift_enter) is True
        repeated = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier, "", True, 2,
        )
        assert dialog.eventFilter(button, repeated) is True
        action.assert_called_once_with()
    dialog.reject = Mock()
    enter = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier,
    )
    assert dialog.eventFilter(dialog.cancel_button, enter) is True
    dialog.reject.assert_called_once_with()
    repeated = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier, "", True, 2,
    )
    assert dialog.eventFilter(dialog.cancel_button, repeated) is True
    dialog.reject.assert_called_once_with()
    dialog.close()
