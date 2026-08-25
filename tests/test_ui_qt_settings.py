from __future__ import annotations

import ast
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from services.ui_preferences import UIPreferencesService
from ui_qt.administration.settings_dialog import SettingsDialog


APP = QApplication.instance() or QApplication([])


class Application:
    def __init__(self, *, editable=True):
        self.editable = editable; self.backups = 0; self.diagnostics = 0; self.saved = []
    def load(self):
        return SimpleNamespace(
            username="maria",
            preferences=UIPreferencesService.normalize({}),
            backup_directories=("C:\\Teste\\backups",),
            daily_backup_enabled=True,
        )
    def can(self, action): return self.editable
    def save_preferences(self, values): self.saved.append(dict(values)); return self.load()
    def configure_backup(self, **values): self.saved.append(values); return self.load()
    def create_backup(self):
        self.backups += 1; return SimpleNamespace(created=("C:\\Teste\\backup.db",))
    def run_diagnostics(self):
        self.diagnostics += 1; return {"aprovado": True}, "SISTEMA APROVADO"
    def load_store_identity(self): return SimpleNamespace(name="LOJA TESTE",receipt_footer="OBRIGADO")
    def save_store_identity(self,**values): self.saved.append(values); return SimpleNamespace(name=values["name"],receipt_footer=values["receipt_footer"])
    def load_printing(self):
        values={"modelo_cupom_visual":"Clássico","impressao_fonte":"Helvetica","impressao_fonte_tamanho":"10","impressao_corte_automatico":"1","impressao_tipo_corte":"PARCIAL","impressao_linhas_antes_corte":"4"}
        for category, default in {"recibo":"Cupom 80 mm","entrega":"Cupom 80 mm","ficha":"A4","historico":"A4","fechamento":"A4"}.items():
            values[f"formato_impressao_{category}"]=default
        for key in ("impressora_recibo","impressora_entrega","impressora_ficha","impressora_historico"):
            values[key]="Padrão do Sistema"
        return SimpleNamespace(printers=("Padrão do Sistema",), values=values)
    def preview_receipt(self, model): return f"PRÉVIA {model}"
    def save_printing(self, values): self.saved.append(dict(values)); return self.load_printing()


def _enter(*, repeat=False, shift=False):
    return QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,
        "\r", repeat, 1,
    )


def test_carrega_preferencias_e_respeita_permissao_somente_leitura():
    dialog = SettingsDialog(Application(editable=False))
    assert dialog.mode.currentText() == "Intermediário"
    assert not dialog.save_interface.isEnabled()
    assert not dialog.backup_now.isEnabled()
    dialog.close()


def test_auto_repeat_e_consumido_sem_disparar_backup():
    application = Application(); dialog = SettingsDialog(application)
    assert dialog.eventFilter(dialog.backup_now, _enter(repeat=True)) is True
    assert application.backups == 0
    dialog.close()


def test_diagnostico_exibe_resultado_sem_persistencia_na_gui():
    application = Application(); dialog = SettingsDialog(application)
    dialog._run_diagnostics()
    assert application.diagnostics == 1
    assert "SISTEMA APROVADO" in dialog.diagnostic_text.toPlainText()
    dialog.close()


def test_previa_e_salvamento_de_impressao_usam_porta_sem_imprimir():
    application = Application(); dialog = SettingsDialog(application)
    assert "PRÉVIA Clássico" in dialog.receipt_preview.toPlainText()
    with patch("ui_qt.administration.settings_dialog.QMessageBox.information"):
        dialog._save_printing()
    assert application.saved[-1]["impressora_recibo"] == "Padrão do Sistema"
    assert application.saved[-1]["formato_impressao_fechamento"] == "A4"
    dialog.close()


def test_shift_enter_e_auto_repeat_nao_salvam_impressao():
    application = Application(); dialog = SettingsDialog(application)
    assert dialog.eventFilter(dialog.save_printing, _enter(shift=True)) is True
    assert dialog.eventFilter(dialog.save_printing, _enter(repeat=True)) is True
    assert application.saved == []
    dialog.close()


def test_identidade_comercial_carrega_e_salva_sem_campos_fiscais():
    application=Application(); dialog=SettingsDialog(application)
    assert dialog.store_name.text()=="LOJA TESTE"
    dialog.store_name.setText("NOVA LOJA")
    with patch("ui_qt.administration.settings_dialog.QMessageBox.information"):
        dialog._save_store_identity()
    assert application.saved[-1]=={"name":"NOVA LOJA","receipt_footer":"OBRIGADO"}
    dialog.close()


def test_gui_nao_importa_banco_repositorios_fiscal_ou_legacy():
    source = Path(__file__).parents[1].joinpath(
        "ui_qt/administration/settings_dialog.py"
    ).read_text(encoding="utf-8")
    modules = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import): modules.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom): modules.append(str(node.module or "").lower())
    for forbidden in ("sqlite3", "database", "repositories", "fiscal", "sefaz", "nabicode_legacy"):
        assert not any(forbidden in module for module in modules)


def test_backup_distingue_diario_legado_da_opcao_protegida():
    dialog = SettingsDialog(Application())
    texts = [label.text() for label in dialog.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel)]
    assert any("dados pessoais" in text and "não é criptografado" in text for text in texts)
    assert dialog.protected_backup.text().startswith("Backup protegido")
    dialog.close()


def test_backup_manual_parcial_exibe_destino_com_falha_sem_alegar_sucesso():
    application = Application()
    application.create_backup = lambda: SimpleNamespace(
        created=("C:\\Teste\\principal.db",),
        errors=("C:\\OneDrive: indisponível",),
    )
    dialog = SettingsDialog(application)
    with patch("ui_qt.administration.settings_dialog.QMessageBox.warning") as warning, patch(
        "ui_qt.administration.settings_dialog.QMessageBox.information"
    ) as information:
        dialog._create_backup()
    assert "indisponível" in warning.call_args.args[2]
    information.assert_not_called()
    dialog.close()
