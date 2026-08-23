from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from database.maintenance import DatabaseMaintenanceService
from repositories.dashboard_repository import DashboardRepository
from services.security_service import SecurityService
from ui_qt.commercial.customer_dialog import CustomerManagementDialog, STYLE
from ui_qt.commercial.pdv_window import PDVWindow

from .receipt_dialog import CustomerReceiptDialog
from .legacy_import_dialog import LegacyFicharioImportDialog
from .pdv_view_model import FicharioPDVViewModel


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
        self._summary_labels = {}
        summary = QGridLayout()
        for index, (key, title_text, color) in enumerate((
            ("total", "TOTAL DE FICHAS", "#58a6ff"),
            ("current", "CLIENTES EM DIA", "#3fb950"),
            ("owing", "CLIENTES DEVENDO", "#ffd33d"),
            ("alert", "ATRASADOS +60 DIAS", "#ff7b72"),
            ("receivable", "TOTAL A RECEBER", "#00d084"),
        )):
            card = QFrame(); card.setObjectName("summaryCard")
            card.setStyleSheet(
                "QFrame#summaryCard{background:#161b22;border:1px solid #30363d;"
                "border-radius:10px;}"
            )
            card_layout = QVBoxLayout(card)
            heading = QLabel(title_text)
            heading.setStyleSheet(f"font-size:12px;font-weight:800;color:{color}")
            value = QLabel("Carregando...")
            value.setStyleSheet("font-size:18px;font-weight:900;color:#f0f6fc")
            value.setWordWrap(True)
            card_layout.addWidget(heading); card_layout.addWidget(value)
            self._summary_labels[key] = value
            summary.addWidget(card, index // 3, index % 3)
        layout.addLayout(summary)
        actions = QGridLayout()
        for index, (label, callback) in enumerate((
            ("PDV COMERCIAL / NAO FISCAL", self.open_pdv),
            ("CLIENTES E FICHAS", self.open_customers),
            ("RECEBER DE CLIENTE", self.open_receipt),
            ("IMPORTAR FICHÁRIO ANTIGO", self.open_legacy_import),
            ("CRIAR BACKUP", self.create_backup),
            ("RESTAURAR BACKUP", self.restore_backup),
            ("INFORMACOES DA INSTALACAO", self.show_settings),
        )):
            button = QPushButton(label); button.setMinimumHeight(78)
            button.setStyleSheet(
                "text-align:left;padding:0 20px;font-size:14px;"
                "background:#161b22;border:1px solid #30363d;border-radius:10px;"
            )
            button.clicked.connect(callback)
            actions.addWidget(button, index // 2, index % 2)
        layout.addLayout(actions, 1)
        footer = QLabel(f"{profile.label} - EDICAO FICHARIO - usuario {session.user.display_name}")
        layout.addWidget(footer)
        self.refresh_summary()

    def refresh_summary(self) -> None:
        try:
            result = DashboardRepository(self.database).client_summary()
        except Exception as error:
            for label in self._summary_labels.values():
                label.setText("Indisponível")
                label.setToolTip(str(error))
            return
        receivable = result.owing_value + result.alert_value
        self._summary_labels["total"].setText(f"{result.total_records} clientes")
        self._summary_labels["current"].setText(
            f"{result.current_count} clientes  •  R$ 0,00"
        )
        self._summary_labels["owing"].setText(
            f"{result.owing_count} clientes  •  R$ {result.owing_value:.2f}"
        )
        self._summary_labels["alert"].setText(
            f"{result.alert_count} clientes  •  R$ {result.alert_value:.2f}"
        )
        self._summary_labels["receivable"].setText(f"R$ {receivable:.2f}")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_summary()

    def _allowed(self, module: str, action: str = "view") -> bool:
        if self.security.require(module, action): return True
        QMessageBox.warning(self, "Permissao", "Seu usuario nao possui permissao para esta operacao.")
        return False

    def open_pdv(self) -> None:
        if not self._allowed("vendas", "create"): return
        self._pdv = PDVWindow(
            FicharioPDVViewModel(self.container.application), cash_label="Fichario",
            profile_label=f"{self.profile.label} - COMERCIAL / NAO FISCAL",
            loose_items_only=True,
            require_registered_customer=True,
        )
        self._pdv.show()

    def open_customers(self) -> None:
        if not self._allowed("clientes", "view"): return
        CustomerManagementDialog(self.container.customer_application, self).exec()
        self.refresh_summary()

    def open_receipt(self) -> None:
        if not self._allowed("clientes", "edit"): return
        CustomerReceiptDialog(
            self.container.customer_application, self.container.actions,
            self.session.user.username, self,
        ).exec()
        self.refresh_summary()

    def open_legacy_import(self) -> None:
        if not self._allowed("clientes", "edit"): return
        if self._pdv is not None and self._pdv.isVisible():
            QMessageBox.warning(
                self, "Importação", "Feche o PDV antes de importar o Fichário antigo."
            )
            return
        LegacyFicharioImportDialog(self.database, self.profile, self).exec()
        self.refresh_summary()

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
