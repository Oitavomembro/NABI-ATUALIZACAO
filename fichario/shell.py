from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from database.maintenance import DatabaseMaintenanceService
from services.security_service import SecurityService
from ui_qt.commercial.customer_dialog import CustomerManagementDialog, STYLE
from ui_qt.commercial.pdv_view_model import PDVViewModel
from ui_qt.commercial.pdv_window import PDVWindow

from .receipt_dialog import CustomerReceiptDialog


class LoginDialog(QDialog):
    def __init__(self, security: SecurityService, parent=None) -> None:
        super().__init__(parent); self.security = security; self.session = None
        self.setWindowTitle("Entrar no NabiCode Fichario"); self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self); form = QFormLayout()
        self.username = QLineEdit("admin"); self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Usuario", self.username); form.addRow("Senha", self.password)
        layout.addLayout(form)
        button = QPushButton("Entrar  [Enter]"); button.setObjectName("primary")
        button.clicked.connect(self._login); layout.addWidget(button)
        self.password.returnPressed.connect(self._login)

    def _login(self) -> None:
        self.session = self.security.authenticate(self.username.text(), self.password.text())
        if self.session is None:
            QMessageBox.warning(self, "Acesso", "Usuario ou senha invalidos.")
            self.password.clear(); self.password.setFocus(); return
        self.accept()


class FicharioWindow(QMainWindow):
    def __init__(self, container, database, profile, security, session, parent=None) -> None:
        super().__init__(parent)
        self.container = container; self.database = database; self.profile = profile
        self.security = security; self.session = session; self._pdv = None
        self.setWindowTitle("NabiCode Fichario")
        self.setMinimumSize(900, 600); self.setStyleSheet(STYLE)
        root = QWidget(); self.setCentralWidget(root); layout = QVBoxLayout(root)
        title = QLabel("NABICODE FICHARIO")
        title.setStyleSheet("font-size:28px;font-weight:900;color:#00d084")
        layout.addWidget(title)
        subtitle = QLabel("Clientes, fichas, recebimentos e vendas comerciais")
        subtitle.setStyleSheet("font-size:16px")
        layout.addWidget(subtitle)
        buttons = QVBoxLayout()
        for label, callback in (
            ("PDV COMERCIAL / NAO FISCAL", self.open_pdv),
            ("CLIENTES E FICHAS", self.open_customers),
            ("RECEBER DE CLIENTE", self.open_receipt),
            ("CRIAR BACKUP", self.create_backup),
            ("RESTAURAR BACKUP", self.restore_backup),
            ("INFORMACOES DA INSTALACAO", self.show_settings),
        ):
            button = QPushButton(label); button.setMinimumHeight(54)
            button.clicked.connect(callback); buttons.addWidget(button)
        buttons.addStretch(); layout.addLayout(buttons, 1)
        footer = QLabel(f"{profile.label} - EDICAO FICHARIO - usuario {session.user.display_name}")
        layout.addWidget(footer)

    def _allowed(self, module: str, action: str = "view") -> bool:
        if self.security.require(module, action): return True
        QMessageBox.warning(self, "Permissao", "Seu usuario nao possui permissao para esta operacao.")
        return False

    def open_pdv(self) -> None:
        if not self._allowed("vendas", "create"): return
        self._pdv = PDVWindow(
            PDVViewModel(self.container.application), cash_label="Fichario",
            profile_label=f"{self.profile.label} - COMERCIAL / NAO FISCAL",
        )
        self._pdv.show()

    def open_customers(self) -> None:
        if not self._allowed("clientes", "view"): return
        CustomerManagementDialog(self.container.customer_application, self).exec()

    def open_receipt(self) -> None:
        if not self._allowed("clientes", "edit"): return
        CustomerReceiptDialog(
            self.container.customer_application, self.container.actions,
            self.session.user.username, self,
        ).exec()

    def create_backup(self) -> None:
        if not self._allowed("backup", "create"): return
        try:
            target, report = self._maintenance().create_backup(prefix="fichario_manual")
        except Exception as error:
            QMessageBox.critical(self, "Backup", str(error)); return
        QMessageBox.information(
            self, "Backup concluido",
            f"Backup integro criado em:\n{target}\n\nSchema: {report.schema_version}",
        )

    def restore_backup(self) -> None:
        if not self._allowed("backup", "restore"): return
        if self._pdv is not None and self._pdv.isVisible():
            QMessageBox.warning(
                self, "Restauracao",
                "Feche o PDV antes de restaurar. Nenhum dado foi alterado.",
            ); return
        source, _ = QFileDialog.getOpenFileName(
            self, "Selecionar backup Fichario", str(self.profile.paths.backups),
            "Banco SQLite (*.db)",
        )
        if not source: return
        typed, accepted = QInputDialog.getText(
            self, "Confirmacao reforcada",
            "A restauracao substitui os dados atuais. Digite RESTAURAR para continuar:",
        )
        if not accepted or typed.strip().upper() != "RESTAURAR":
            QMessageBox.information(self, "Restauracao", "Restauracao cancelada."); return
        try:
            safety, report = self._maintenance().restore(source)
        except Exception as error:
            QMessageBox.critical(
                self, "Restauracao recusada",
                f"O banco atual foi preservado.\n\n{error}",
            ); return
        QMessageBox.information(
            self, "Restauracao concluida",
            f"Dados restaurados e validados.\nSchema: {report.schema_version}\n"
            f"Copia anterior preservada em:\n{safety}\n\nReinicie o programa.",
        )
        self.close()

    def _maintenance(self) -> DatabaseMaintenanceService:
        return DatabaseMaintenanceService(
            self.database.database_path, self.profile.paths.backups,
            expected_schema_version=20,
            required_tables=(
                "clientes", "produtos", "movimentacoes", "parcelas",
                "configuracoes", "historico_clientes",
            ),
        )

    def show_settings(self) -> None:
        QMessageBox.information(
            self, "Instalacao Fichario",
            f"Perfil: {self.profile.label}\nDados: {self.profile.app_dir}\n"
            f"Banco: {self.database.database_path}",
        )
