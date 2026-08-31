from __future__ import annotations


from PySide6.QtCore import QDate, QDateTime, QTimer, Qt, QSettings, QEvent
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from database.maintenance import DatabaseMaintenanceService
from repositories.dashboard_repository import DashboardRepository
from repositories.system_repository import SystemRepository
from services.security_service import SecurityService
from commercial.domain.money import MoneyCodec
from ui_qt.commercial.customer_dialog import CustomerManagementDialog, STYLE
from ui_qt.commercial.pdv_window import PDVWindow

from .receipt_dialog import CustomerReceiptDialog
from .customer_picker import CustomerPickerDialog
from .users_dialog import UsersDialog
from .receipt_output import FicharioCustomerReceiptOutput
from .legacy_import_dialog import LegacyFicharioImportDialog
from .pdv_view_model import FicharioPDVViewModel
from .preferences_dialog import (
    FicharioPreferencesDialog, configured_backup_directory, fichario_settings,
    interface_font_size,
)
from .update_runtime import FicharioUpdateRuntime


class LoginDialog(QDialog):
    def __init__(self, security: SecurityService, parent=None) -> None:
        super().__init__(parent); self.security = security; self.session = None
        self.setWindowTitle("Entrar no NabiCode Fichario"); self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self); form = QFormLayout()
        self.resize(620, 320)
        self.settings = QSettings("NabiCode", "Fichario")
        self.username = QLineEdit(str(self.settings.value("login/username", "")))
        self.password = QLineEdit()
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
        self.settings.setValue("login/username", self.session.user.username)
        self.password.clear()
        self.accept()


class FicharioWindow(QMainWindow):
    def __init__(self, container, database, profile, security, session, parent=None) -> None:
        super().__init__(parent)
        self.container = container; self.database = database; self.profile = profile
        self.security = security; self.session = session; self._pdv = None
        system_repository = SystemRepository(database.connect)
        self._receipt_output = FicharioCustomerReceiptOutput(
            database, profile.paths.pdfs, system_repository.get_config
        )
        self.setWindowTitle("NabiCode Fichario")
        self.setMinimumSize(1000, 640)
        self.resize(1220, 720)
        self._apply_interface_font()
        root = QWidget(); self.setCentralWidget(root); layout = QVBoxLayout(root)
        title = QLabel("NABICODE FICHARIO")
        title.setStyleSheet("font-size:28px;font-weight:900;color:#00d084")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        subtitle = QLabel("Clientes, fichas, recebimentos e vendas comerciais")
        subtitle.setStyleSheet("font-size:16px")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        system_menu = self.menuBar().addMenu("Sistema")
        self._users_action = system_menu.addAction("Usuários", self.open_users)
        self._users_action.setVisible(self.security.require("usuarios", "edit"))
        system_menu.addAction("Trocar usuário / entrar novamente", self.switch_user)
        system_menu.addAction("Importar Fichário antigo", self.open_legacy_import)
        system_menu.addSeparator()
        system_menu.addAction("Criar backup", self.create_backup)
        system_menu.addAction("Restaurar backup", self.restore_backup)
        system_menu.addAction("Aplicar atualização assinada", self.apply_update)
        system_menu.addSeparator()
        system_menu.addAction("Backup diário e tamanho das letras", self.open_preferences)
        system_menu.addAction("Informações da instalação", self.show_settings)
        self._summary_labels = {}
        summary = QGridLayout()
        for index, (key, title_text, color, segment) in enumerate((
            ("total", "TOTAL DE FICHAS", "#58a6ff", "all"),
            ("current", "CLIENTES EM DIA", "#3fb950", "current"),
            ("owing", "CLIENTES DEVENDO", "#ffd33d", "owing"),
            ("alert", "ATRASADOS +60 DIAS", "#ff7b72", "alert"),
            ("receivable", "TOTAL A RECEBER", "#00d084", "debt"),
            ("received_today", "RECEBIDO HOJE", "#58d5ff", None),
            ("credit_today", "FIADO GERADO HOJE", "#d2a8ff", None),
        )):
            card = QPushButton(title_text); card.setObjectName("summaryCard")
            card.setStyleSheet(
                f"QPushButton#summaryCard{{background:#161b22;border:1px solid #30363d;"
                f"border-radius:10px;color:{color};text-align:left;padding:12px;"
                "font-size:14px;font-weight:900;min-height:68px;}"
                "QPushButton#summaryCard:hover{border:2px solid #58a6ff;background:#21262d;}"
            )
            if segment is None:
                kind = "received" if key == "received_today" else "credit"
                card.setToolTip("Clique para consultar as operações que formam este valor")
                card.clicked.connect(
                    lambda _checked=False, current_kind=kind: self.open_daily_flow(current_kind)
                )
            else:
                card.setToolTip("Clique para ver os clientes desta situação")
                card.clicked.connect(
                    lambda _checked=False, current_segment=segment, current_title=title_text:
                    self.open_customer_segment(current_segment, current_title)
                )
            self._summary_labels[key] = (card, title_text)
            summary.addWidget(card, index // 3, index % 3)
        layout.addLayout(summary)
        actions = QGridLayout()
        for index, (label, callback) in enumerate((
            ("VENDAS", self.open_pdv),
            ("CLIENTES E FICHAS", self.open_customers),
            ("RECEBER DE CLIENTE", self.open_receipt),
            ("MENU DO SISTEMA", self.open_system_center),
        )):
            button = QPushButton(label); button.setMinimumHeight(112)
            button.setObjectName("mainActionCard")
            button.setStyleSheet(
                "QPushButton#mainActionCard{text-align:left;padding:0 26px;font-size:17px;"
                "font-weight:900;color:#f0f6fc;"
                "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 #343d48,stop:0.08 #242c35,stop:0.52 #171d24,stop:1 #0e1319);"
                "border:1px solid #596674;border-bottom:3px solid #090c10;"
                "border-radius:14px;}"
                "QPushButton#mainActionCard:hover{color:#ffffff;"
                "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 #465361,stop:0.10 #2c3742,stop:1 #151c23);"
                "border:2px solid #58a6ff;border-bottom:3px solid #162b40;}"
                "QPushButton#mainActionCard:focus{border:2px solid #00d084;"
                "border-left:6px solid #00d084;}"
                "QPushButton#mainActionCard:pressed{padding-top:3px;"
                "background:#10161c;border-bottom:1px solid #596674;}"
            )
            button.clicked.connect(callback)
            actions.addWidget(button, index // 2, index % 2)
        layout.addLayout(actions, 1)
        self.footer = QLabel()
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer.setStyleSheet("font-size:13px;font-weight:700;color:#8b949e")
        layout.addWidget(self.footer)
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._refresh_system_clock)
        self._refresh_system_clock()
        self._clock_timer.start()
        self.refresh_summary()
        QTimer.singleShot(0, self._run_daily_backup)

    def _apply_interface_font(self) -> None:
        self.setStyleSheet(
            STYLE + f"\nQMainWindow,QDialog,QMenu,QMenuBar{{font-size:{interface_font_size()}px;}}"
        )

    def _refresh_system_clock(self) -> None:
        current = QDateTime.currentDateTime().toString("dd/MM/yyyy HH:mm:ss")
        self.footer.setText(
            f"{self.profile.label} - EDICAO FICHARIO - usuario "
            f"{self.session.user.display_name}   •   DATA/HORA: {current}"
        )

    def open_system_center(self) -> None:
        dialog = QDialog(self); dialog.setWindowTitle("Menu do Sistema")
        dialog.setMinimumWidth(540); dialog.setStyleSheet(STYLE)
        layout = QVBoxLayout(dialog)
        title = QLabel("MENU DO SISTEMA")
        title.setStyleSheet("font-size:22px;font-weight:900;color:#00d084")
        layout.addWidget(title)
        for label, callback in (
            ("Fazer backup agora", self.create_backup),
            ("Restaurar backup do NabiCode", self.restore_backup),
            ("Importar Fichário antigo", self.open_legacy_import),
            ("Backup diário, pasta e tamanho das letras", self.open_preferences),
            ("Informações da instalação", self.show_settings),
        ):
            button = QPushButton(label); button.setMinimumHeight(52)
            button.clicked.connect(callback); layout.addWidget(button)
        close = QPushButton("Fechar"); close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def open_preferences(self) -> None:
        if FicharioPreferencesDialog(self.profile, self).exec() == QDialog.DialogCode.Accepted:
            self._apply_interface_font()
            self.statusBar().showMessage("Configurações salvas.", 3000)

    def _run_daily_backup(self) -> None:
        settings = fichario_settings()
        enabled = str(settings.value("backup/daily_enabled", "false")).lower() in {
            "true", "1", "yes"
        }
        today = QDate.currentDate().toString("yyyy-MM-dd")
        if not enabled or str(settings.value("backup/last_success", "")) == today:
            return
        try:
            target, _report = self._maintenance().create_backup(prefix="fichario_diario")
        except Exception as error:
            QMessageBox.warning(
                self, "Backup diário não concluído",
                f"Nenhum backup diário foi marcado como concluído.\n\n{error}",
            )
            return
        settings.setValue("backup/last_success", today); settings.sync()
        self.statusBar().showMessage(f"Backup diário validado: {target}", 6000)

    def refresh_summary(self) -> None:
        try:
            repository = DashboardRepository(self.database)
            result = repository.client_summary()
            flow = repository.daily_credit_flow()
        except Exception as error:
            for label, title in self._summary_labels.values():
                label.setText("Indisponível")
                label.setToolTip(str(error))
            return
        receivable = result.owing_value + result.alert_value
        self._summary_labels["total"][0].setText(
            f"TOTAL DE FICHAS\n{result.total_records} clientes"
        )
        self._summary_labels["current"][0].setText(
            f"CLIENTES EM DIA\n{result.current_count} clientes  •  R$ 0,00"
        )
        self._summary_labels["owing"][0].setText(
            f"CLIENTES DEVENDO\n{result.owing_count} clientes  •  R$ {result.owing_value:.2f}"
        )
        self._summary_labels["alert"][0].setText(
            f"ATRASADOS +60 DIAS\n{result.alert_count} clientes  •  R$ {result.alert_value:.2f}"
        )
        self._summary_labels["receivable"][0].setText(
            f"TOTAL A RECEBER\nR$ {MoneyCodec.format_br(receivable)}"
        )
        self._summary_labels["received_today"][0].setText(
            f"RECEBIDO HOJE\nR$ {MoneyCodec.format_br(flow.received_total)}"
        )
        self._summary_labels["credit_today"][0].setText(
            f"FIADO GERADO HOJE\nR$ {MoneyCodec.format_br(flow.financed_total)}"
        )

    def open_daily_flow(self, kind: str) -> None:
        if not self._allowed("clientes", "view"): return
        try:
            flow = DashboardRepository(self.database).daily_credit_flow()
        except Exception as error:
            QMessageBox.warning(self, "Resumo indisponível", str(error))
            return
        received = kind == "received"
        title = "VALORES RECEBIDOS HOJE" if received else "FIADO GERADO HOJE"
        dialog = QDialog(self); dialog.setWindowTitle(title); dialog.setStyleSheet(STYLE)
        dialog.resize(900, 560)
        layout = QVBoxLayout(dialog)
        heading = QLabel(title); heading.setObjectName("sectionTitle"); layout.addWidget(heading)
        total = flow.received_total if received else flow.financed_total
        total_label = QLabel(f"TOTAL: R$ {MoneyCodec.format_br(total)}")
        total_label.setStyleSheet("font-size:22px;font-weight:900;color:#58d5ff;padding:8px")
        layout.addWidget(total_label)
        table = QTableWidget(0, 6, dialog)
        table.setHorizontalHeaderLabels(("ID", "HORÁRIO", "CLIENTE", "DESCRIÇÃO", "VALOR", "USUÁRIO"))
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for entry in flow.entries:
            value = entry.received_value if received else entry.financed_value
            if value <= 0: continue
            row = table.rowCount(); table.insertRow(row)
            values = (
                str(entry.movement_id), entry.timestamp, entry.customer_name,
                entry.description, f"R$ {MoneyCodec.format_br(value)}",
                entry.operator or "Histórico sem autoria",
            )
            for column, text in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(text))
        layout.addWidget(table, 1)
        close = QPushButton("Fechar  [Esc]"); close.clicked.connect(dialog.accept)
        layout.addWidget(close); dialog.exec()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_summary()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow() and hasattr(self, "_clock_timer"):
            self.refresh_summary()

    def closeEvent(self, event) -> None:
        if self._pdv is not None:
            self._pdv.close()
        self.security.logout()
        super().closeEvent(event)

    def _allowed(self, module: str, action: str = "view") -> bool:
        if self.security.require(module, action): return True
        QMessageBox.warning(self, "Permissao", "Seu usuario nao possui permissao para esta operacao.")
        return False

    def open_users(self) -> None:
        if not self._allowed("usuarios", "edit"): return
        try:
            UsersDialog(self.security, self).exec()
        except Exception as error:
            QMessageBox.warning(self, "Usuários", str(error))

    def switch_user(self) -> None:
        if self._pdv is not None and self._pdv.isVisible():
            QMessageBox.information(self, "Trocar usuário", "Feche Vendas antes de trocar o usuário.")
            return
        self.security.logout()
        login = LoginDialog(self.security, self)
        if login.exec() != QDialog.DialogCode.Accepted:
            self.close()
            return
        self.session = self.security.session
        self._users_action.setVisible(self.security.require("usuarios", "edit"))
        self._refresh_system_clock()

    def open_pdv(self) -> None:
        if not self._allowed("vendas", "create"): return
        if self._pdv is not None and self._pdv.isVisible():
            self._pdv.raise_()
            self._pdv.activateWindow()
            return
        self._pdv = PDVWindow(
            FicharioPDVViewModel(self.container.application), cash_label="Fichario",
            profile_label=f"{self.profile.label} - COMERCIAL / NAO FISCAL",
            loose_items_only=True,
            require_registered_customer=True,
        )
        self._pdv.show()
        choose = QPushButton("Escolher cliente — fichas e saldos", self._pdv)
        choose.clicked.connect(self._choose_sale_customer)
        self._pdv.customer_search.parentWidget().layout().addWidget(choose, 4, 0, 1, 2)

    def _choose_sale_customer(self) -> None:
        if not self._allowed("clientes", "view"): return
        dialog = CustomerPickerDialog(self.container.customer_application, self._pdv)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, dialog.selected_customer.customer_id)
            self._pdv._select_customer(item)

    def open_customers(self) -> None:
        if not self._allowed("clientes", "view"): return
        CustomerManagementDialog(
            self.container.customer_application, self,
            deletion_authorizer=lambda: self._allowed("clientes", "edit"),
        ).exec()
        self.refresh_summary()

    def open_customer_segment(self, segment: str, title: str) -> None:
        if not self._allowed("clientes", "view"): return
        repository = DashboardRepository(self.database)

        def provider(term: str, limit: int):
            ids = repository.client_segment_ids(segment, term, limit=limit)
            return self.container.customer_application.list_customers_by_ids(ids)

        CustomerManagementDialog(
            self.container.customer_application, self,
            customer_provider=provider, filter_title=title,
            deletion_authorizer=lambda: self._allowed("clientes", "edit"),
        ).exec()
        self.refresh_summary()

    def open_receipt(self) -> None:
        if not self._allowed("financeiro", "pay"): return
        CustomerReceiptDialog(
            self.container.customer_application, self.container.actions,
            self.session.user.username, self, receipt_output=self._receipt_output,
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
            f"Backup íntegro criado em:\n{target}\n\nSchema: {report.schema_version}\n\n"
            "Conteúdo preservado: clientes, fichas, endereços, telefones, saldos, "
            "vendas, recebimentos, parcelas, históricos e configurações do banco.\n\n"
            "A pasta de backup e o tamanho das letras são preferências deste computador.",
        )

    def restore_backup(self) -> None:
        if not self._allowed("backup", "restore"): return
        if self._pdv is not None and self._pdv.isVisible():
            QMessageBox.warning(
                self, "Restauracao",
                "Feche o PDV antes de restaurar. Nenhum dado foi alterado.",
            ); return
        source, _ = QFileDialog.getOpenFileName(
            self, "Selecionar backup Fichario", str(configured_backup_directory(self.profile)),
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
            f"Dados restaurados e validados.\nSchema: {report.schema_version}\n\n"
            "Restaurados: clientes, fichas, endereços, telefones, saldos, vendas, "
            "recebimentos, parcelas, históricos e configurações do banco.\n"
            "As preferências locais de pasta e tamanho das letras foram preservadas.\n\n"
            f"Copia anterior preservada em:\n{safety}\n\nReinicie o programa.",
        )
        self.close()

    def apply_update(self) -> None:
        if self._pdv is not None and self._pdv.isVisible():
            QMessageBox.warning(
                self, "Atualização", "Feche a tela de Vendas antes de atualizar.",
            ); return
        source, _ = QFileDialog.getOpenFileName(
            self, "Selecionar atualização assinada", str(self.profile.app_dir / "atualizacoes"),
            "Atualização NabiCode (*.zip)",
        )
        if not source: return
        runtime = FicharioUpdateRuntime(self.profile, self.database.database_path)
        try:
            manifest = runtime.package_service.validate(source)
        except Exception as error:
            QMessageBox.critical(self, "Atualização recusada", str(error)); return
        answer = QMessageBox.question(
            self, "Confirmar atualização",
            f"Pacote assinado e íntegro.\n\nVersão: {manifest['version']}\n"
            f"Revisão: {manifest.get('revision', 0)}\nChave: {manifest.get('key_id')}\n\n"
            "Será criado um backup completo antes da troca. Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes: return
        try:
            _manifest, state, backup = runtime.prepare(source)
            runtime.launch_helper(state)
        except Exception as error:
            QMessageBox.critical(
                self, "Atualização não iniciada",
                f"Nenhum arquivo do programa foi substituído.\n\n{error}",
            ); return
        QMessageBox.information(
            self, "Atualização preparada",
            f"Backup validado em:\n{backup}\n\nO NabiCode será fechado, atualizado e reaberto.",
        )
        QApplication.instance().quit()

    def _maintenance(self) -> DatabaseMaintenanceService:
        return DatabaseMaintenanceService(
            self.database.database_path, configured_backup_directory(self.profile),
            expected_schema_version=21,
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
