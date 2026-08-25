import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtWidgets import QApplication,QDialog,QMainWindow
from PySide6.QtCore import QEvent,Qt
from PySide6.QtGui import QKeyEvent
from ui_qt import app as qt_app
from ui_qt.administration.composition import build_administrative_modules
from ui_qt.administration.login_dialog import ApplicationLoginDialog
from ui_qt.administration.initial_setup_dialog import InitialSetupDialog
from ui_qt.administration.legacy_security_migration_dialog import LegacySecurityMigrationDialog
import main_qt

class Window(QMainWindow):
    def __init__(self,*args,**kwargs):super().__init__()

def setup_module():
    global QT;QT=QApplication.instance() or QApplication([])

def test_login_invalido_falha_fechado_e_nao_aceita():
    security=Mock();security.authenticate.return_value=None;dialog=ApplicationLoginDialog(security);dialog.username.setText("x");dialog.password.setText("segredo")
    with patch("ui_qt.administration.login_dialog.QMessageBox.warning"):dialog.authenticate()
    assert dialog.result()==0;assert dialog.password.text()=="";dialog.close()

def test_login_valido_cria_sessao_por_autenticacao_real():
    security=Mock();security.authenticate.return_value=object();dialog=ApplicationLoginDialog(security);dialog.username.setText("maria");dialog.password.setText("senha") ;dialog.authenticate()
    security.authenticate.assert_called_once_with("maria","senha");assert dialog.result()==QDialog.DialogCode.Accepted;dialog.close()

def test_login_auto_repeat_e_consumido_sem_autenticar():
    security=Mock();dialog=ApplicationLoginDialog(security);event=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier,"",True,1)
    assert dialog.eventFilter(dialog.enter,event) is True;security.authenticate.assert_not_called();dialog.close()

def test_configuracao_inicial_exige_senhas_iguais_e_nao_abre_sessao():
    security=Mock();dialog=InitialSetupDialog(security);dialog.store_name.setText("Loja");dialog.username.setText("dono");dialog.password.setText("segura123");dialog.password_confirmation.setText("diferente")
    with patch("ui_qt.administration.initial_setup_dialog.QMessageBox.warning"):
        dialog.complete()
    security.complete_initial_setup.assert_not_called();assert dialog.result()==0
    dialog.password.setText("segura123");dialog.password_confirmation.setText("segura123")
    with patch("ui_qt.administration.initial_setup_dialog.QMessageBox.information"):
        dialog.complete()
    security.complete_initial_setup.assert_called_once();assert dialog.result()==QDialog.DialogCode.Accepted;dialog.close()

def test_configuracao_inicial_consumo_de_auto_repeat_nao_grava():
    security=Mock();dialog=InitialSetupDialog(security);event=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier,"",True,1)
    assert dialog.eventFilter(dialog.finish,event) is True;security.complete_initial_setup.assert_not_called();dialog.close()

def test_nabi_orienta_primeiro_acesso_sem_modelo_local():
    dialog=InitialSetupDialog(Mock())
    assert "NABI" in dialog.nabi_guidance.text()
    dialog._show_guidance(dialog.document)
    assert "modo não fiscal" in dialog.nabi_guidance.text()
    dialog._show_guidance(dialog.password)
    assert "oito caracteres" in dialog.nabi_guidance.text()
    dialog.close()

def test_migracao_legada_exige_confirmacao_e_consumo_unico():
    security=Mock();dialog=LegacySecurityMigrationDialog(security);dialog.current_password.setText("antiga");dialog.new_password.setText("nova-segura");dialog.confirmation.setText("diferente")
    with patch("ui_qt.administration.legacy_security_migration_dialog.QMessageBox.warning"):dialog.complete()
    security.complete_existing_installation_migration.assert_not_called()
    dialog.new_password.setText("nova-segura");dialog.confirmation.setText("nova-segura")
    with patch("ui_qt.administration.legacy_security_migration_dialog.QMessageBox.information"):dialog.complete()
    security.complete_existing_installation_migration.assert_called_once_with(username="admin",current_password="antiga",new_password="nova-segura")
    assert dialog.result()==QDialog.DialogCode.Accepted;dialog.close()

def test_migracao_legada_bloqueia_auto_repeat():
    security=Mock();dialog=LegacySecurityMigrationDialog(security);event=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier,"",True,1)
    assert dialog.eventFilter(dialog.finish,event) is True
    security.complete_existing_installation_migration.assert_not_called();dialog.close()

def test_composicao_omite_opcionais_ausentes_sem_impedir_inicio_caixa_relatorios_usuarios():
    container=SimpleNamespace(customer_application=None,product_application=None,stock_actions=None,purchase_service=None,financial_query=None,financial_actions=None)
    database=SimpleNamespace(connect=Mock(),database_path=Path("C:/Teste/banco.db"));profile=SimpleNamespace(app_dir=Path("C:/Teste"),paths=SimpleNamespace(pdfs=Path("C:/Teste/PDF"),backups=Path("C:/Teste/backups"),rollback=Path("C:/Teste/rollback"),diagnostics=Path("C:/Teste/diagnosticos"),config=Path("C:/Teste/config"),fiscal=Path("C:/Teste/fiscal")));security=Mock()
    with patch("ui_qt.administration.composition.CashService"),patch("ui_qt.administration.composition.ReportService"),patch("ui_qt.administration.composition.SettingsApplicationService"),patch("ui_qt.administration.composition.BackupService") as backup:
        modules=build_administrative_modules(container,database,profile,security)
    assert tuple(m.label for m in modules)==("Início","Caixa","Relatórios","Usuários","Configurações","Ajuda","Auditoria")
    assert backup.call_args.kwargs["fiscal_directory"] == Path("C:/Teste/fiscal")

def test_composicao_de_clientes_liga_segmento_do_dashboard_ao_filtro_da_janela():
    customer_application=Mock();customer_application.list_customers_by_ids.return_value=("cliente",)
    container=SimpleNamespace(customer_application=customer_application,product_application=None,stock_actions=None,purchase_service=None,financial_query=None,financial_actions=None)
    database=SimpleNamespace(connect=Mock(),database_path=Path("C:/Teste/banco.db"));profile=SimpleNamespace(app_dir=Path("C:/Teste"),paths=SimpleNamespace(pdfs=Path("C:/Teste/PDF"),backups=Path("C:/Teste/backups"),rollback=Path("C:/Teste/rollback"),diagnostics=Path("C:/Teste/diagnosticos"),config=Path("C:/Teste/config"),fiscal=Path("C:/Teste/fiscal")));security=Mock()
    with patch("ui_qt.administration.composition.DashboardRepository") as repository_type,patch("ui_qt.administration.composition.CashService"),patch("ui_qt.administration.composition.ReportService"),patch("ui_qt.administration.composition.SettingsApplicationService"),patch("ui_qt.administration.composition.BackupService"),patch("ui_qt.administration.composition.CustomerManagementDialog") as dialog_type:
        repository_type.return_value.client_segment_ids.return_value=(7,9)
        modules=build_administrative_modules(container,database,profile,security)
        customers=next(module for module in modules if module.module_id=="clientes")
        customers.filtered_factory(None,"owing","CLIENTES DEVENDO")
    provider=dialog_type.call_args.kwargs["customer_provider"]
    assert dialog_type.call_args.kwargs["filter_title"]=="CLIENTES DEVENDO"
    assert provider("ana",25)==("cliente",)
    repository_type.return_value.client_segment_ids.assert_called_once_with("owing","ana",limit=25)
    customer_application.list_customers_by_ids.assert_called_once_with((7,9))

def test_shell_sem_factory_preserva_funcionamento_anterior():
    with patch.object(qt_app,"PDVWindow",Window),patch.object(qt_app,"PDVViewModel",lambda app:app):
        _qt,window=qt_app.create_application(object(),[])
    assert not hasattr(window,"nabicode_modules_toolbar");window.close()

def test_shell_abre_hub_uma_vez_e_recusa_factory_invalida():
    hub=Mock(spec=QDialog)
    with patch.object(qt_app,"PDVWindow",Window),patch.object(qt_app,"PDVViewModel",lambda app:app):
        _qt,window=qt_app.create_application(object(),[],administrative_hub_factory=lambda parent:hub)
    window.open_administrative_hub();hub.exec.assert_called_once_with();window.close()

def test_main_nao_usa_sessao_sem_senha():
    source=Path("main_qt.py").read_text(encoding="utf-8")
    assert "start_session_without_password" not in source
    assert "ApplicationLoginDialog(module_security).exec()" in source
    assert "InitialSetupDialog(module_security).exec()" in source
    assert "LegacySecurityMigrationDialog(module_security).exec()" in source

def test_factory_reautentica_sessao_expirada_e_cancela_fechado():
    security=Mock();security.session=None;security.is_expired.return_value=True
    factory=main_qt._administrative_hub_factory(security,())
    with patch.object(main_qt,"ApplicationLoginDialog") as login:
        login.return_value.exec.return_value=QDialog.DialogCode.Rejected
        try:factory(None)
        except PermissionError as error:assert "cancelada" in str(error)
        else:raise AssertionError("deveria falhar fechado")

def test_factory_nao_pede_nova_senha_com_sessao_valida():
    security=Mock();security.session=object();security.is_expired.return_value=False
    with patch.object(main_qt,"ApplicationLoginDialog") as login,patch.object(main_qt,"AdministrativeModuleHub",return_value="hub"):
        assert main_qt._administrative_hub_factory(security,())(None)=="hub"
    login.assert_not_called()
