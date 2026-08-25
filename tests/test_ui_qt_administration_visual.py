import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from ui_qt.administration.initial_setup_dialog import InitialSetupDialog
from ui_qt.administration.legacy_security_migration_dialog import LegacySecurityMigrationDialog
from ui_qt.administration.login_dialog import ADMIN_METALLIC_STYLE, ApplicationLoginDialog

APP = QApplication.instance() or QApplication([])


def test_estilo_administrativo_metalico_tem_foco_e_alerta_sem_paleta_multicolorida():
    assert "qlineargradient" in ADMIN_METALLIC_STYLE
    assert "#73c7dc" in ADMIN_METALLIC_STYLE
    assert "QPushButton#destructive" in ADMIN_METALLIC_STYLE
    assert "#00d084" not in ADMIN_METALLIC_STYLE
    assert "#1f6feb" not in ADMIN_METALLIC_STYLE


def test_login_preserva_campos_e_destaca_somente_acao_primaria():
    dialog = ApplicationLoginDialog(Mock())
    assert dialog.username.accessibleName() == "Usuário"
    assert dialog.password.accessibleName() == "Senha"
    assert dialog.enter.objectName() == "primary"
    assert dialog.cancel.objectName() != "destructive"
    dialog.close()


def test_primeiro_acesso_e_migracao_usam_mesmo_acabamento_sem_mudar_fluxo():
    setup = InitialSetupDialog(Mock())
    migration = LegacySecurityMigrationDialog(Mock())
    assert setup.finish.objectName() == "primary"
    assert migration.finish.objectName() == "primary"
    assert setup.fields[0] is setup.store_name
    assert migration.fields[0] is migration.username
    assert "#73c7dc" in setup.styleSheet()
    assert "#73c7dc" in migration.styleSheet()
    setup.close()
    migration.close()
