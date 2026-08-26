from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
    QApplication, QLabel, QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
)

from services.nabimig_ui_service import preview_text


class DataMaintenanceDialog(QDialog):
    """Migração e backup; restauração ativa permanece fora do processo aberto."""

    CATEGORIES = (
        ("customers", "Clientes"), ("products", "Produtos"),
        ("stock", "Estoque"), ("suppliers", "Fornecedores"),
        ("sales", "Vendas históricas"), ("sale_items", "Itens das vendas"),
        ("credit_accounts", "Crediário"), ("receipts", "Recebimentos"),
    )

    def __init__(self, application, parent=None):
        super().__init__(parent)
        self.application = application
        self._preview = None
        self.setWindowTitle("Manutenção segura de dados")
        self.resize(850, 700)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint
        )
        root = QVBoxLayout(self)
        title = QLabel("MIGRAÇÃO, VERIFICAÇÃO E RESTAURAÇÃO SEGURA")
        title.setStyleSheet("font-size:20px;font-weight:900")
        root.addWidget(title)
        root.addWidget(QLabel(
            "Nenhuma restauração substitui o banco enquanto o NabiCode está aberto."
        ))
        root.addWidget(self._migration_box())
        root.addWidget(self._backup_box())
        self.output = QTextEdit(); self.output.setReadOnly(True)
        self.output.setPlaceholderText("Prévia e evidências aparecem aqui.")
        root.addWidget(self.output, 1)
        self.close_button = QPushButton("Fechar [Esc]")
        self.close_button.clicked.connect(self.reject); root.addWidget(self.close_button)
        for widget_type in (QLineEdit, QPushButton, QCheckBox):
            for widget in self.findChildren(widget_type):
                widget.installEventFilter(self)

    def _migration_box(self):
        box = QGroupBox("1. Migrar dados de outro sistema (.nabimig)")
        layout = QVBoxLayout(box); row = QHBoxLayout()
        self.migration_path = QLineEdit(); self.migration_path.setReadOnly(True)
        self.choose_migration = QPushButton("Escolher pacote")
        self.choose_migration.clicked.connect(self._choose_migration)
        self.preview_migration = QPushButton("Analisar sem importar")
        self.preview_migration.clicked.connect(self._preview_migration)
        row.addWidget(self.migration_path, 1); row.addWidget(self.choose_migration); row.addWidget(self.preview_migration)
        layout.addLayout(row)
        grid = QGridLayout(); self.category_checks = {}
        for index, (key, label) in enumerate(self.CATEGORIES):
            check = QCheckBox(label); check.setChecked(key in {"customers", "products", "stock", "suppliers"})
            self.category_checks[key] = check; grid.addWidget(check, index // 4, index % 4)
        layout.addLayout(grid)
        self.migration_confirmation = QLineEdit(); self.migration_confirmation.setPlaceholderText("Confirmação exibida após a análise")
        self.import_button = QPushButton("Importar após prévia e confirmação")
        self.import_button.setEnabled(False); self.import_button.clicked.connect(self._execute_migration)
        layout.addWidget(self.migration_confirmation); layout.addWidget(self.import_button)
        return box

    def _backup_box(self):
        box = QGroupBox("2. Verificar ou preparar restauração de backup nativo")
        layout = QVBoxLayout(box); row = QHBoxLayout()
        self.backup_path = QLineEdit(); self.backup_path.setReadOnly(True)
        self.choose_backup = QPushButton("Escolher backup")
        self.choose_backup.clicked.connect(self._choose_backup)
        self.verify_button = QPushButton("Verificar somente em TEMP")
        self.verify_button.clicked.connect(self._verify_backup)
        row.addWidget(self.backup_path, 1); row.addWidget(self.choose_backup); row.addWidget(self.verify_button)
        layout.addLayout(row)
        self.backup_password = QLineEdit(); self.backup_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.backup_password.setPlaceholderText("Senha somente se o backup for protegido; nunca é salva")
        self.restore_confirmation = QLineEdit(); self.restore_confirmation.setPlaceholderText("Confirmação exibida após a verificação")
        self.prepare_button = QPushButton("Preparar restauração e pré-backup")
        self.prepare_button.setEnabled(False); self.prepare_button.clicked.connect(self._prepare_restore)
        layout.addWidget(self.backup_password); layout.addWidget(self.restore_confirmation); layout.addWidget(self.prepare_button)
        return box

    def _choose_migration(self):
        path, _ = QFileDialog.getOpenFileName(self, "Escolher pacote NabiMig", "", "NabiMig (*.nabimig)")
        if path:
            self.migration_path.setText(path); self._preview = None; self.import_button.setEnabled(False)

    def _preview_migration(self):
        try:
            self._preview = self.application.preview_migration(self.migration_path.text())
            self.output.setPlainText(preview_text(self._preview))
            phrase = self.application.migration_confirmation(self._preview)
            self.migration_confirmation.setPlaceholderText(f"Digite: {phrase}")
            self.import_button.setEnabled(bool(self._preview.ready))
        except Exception as error:
            self.output.setPlainText(str(error)); self.import_button.setEnabled(False)

    def _execute_migration(self):
        if self._preview is None:
            return
        selected = tuple(key for key, check in self.category_checks.items() if check.isChecked())
        try:
            result = self.application.execute_migration(
                self.migration_path.text(), categories=selected,
                confirmation=self.migration_confirmation.text(),
            )
        except Exception as error:
            self.output.setPlainText(str(error)); return
        self.output.setPlainText(
            "IMPORTAÇÃO CONCLUÍDA E AUDITADA\n"
            f"Backup prévio: {result.backup}\n"
            f"Inseridos: {sum(result.inserted.values())}\nAtualizados: {sum(result.updated.values())}"
        )
        self.import_button.setEnabled(False); self.migration_confirmation.clear()

    def _choose_backup(self):
        path, _ = QFileDialog.getOpenFileName(self, "Escolher backup NabiCode", "", "Backup (*.nabibackup *.db)")
        if path:
            self.backup_path.setText(path); self.prepare_button.setEnabled(False)

    def _verify_backup(self):
        password = self.backup_password.text()
        try:
            result = self.application.verify_backup(self.backup_path.text(), password=password)
        except Exception as error:
            self.output.setPlainText(str(error)); self.prepare_button.setEnabled(False); self.backup_password.clear(); return
        phrase = self.application.restore_confirmation(result.sha256)
        self.restore_confirmation.setPlaceholderText(f"Digite: {phrase}")
        self.output.setPlainText(
            "BACKUP COMPROVADO SOMENTE EM TEMP\n"
            f"Formato: {result.backup_format}\nSchema: {result.schema_version}\nSHA-256: {result.sha256}\n"
            "O banco ativo não foi alterado."
        )
        self.prepare_button.setEnabled(True)

    def _prepare_restore(self):
        password = self.backup_password.text()
        try:
            result = self.application.prepare_restore(
                self.backup_path.text(), confirmation=self.restore_confirmation.text(),
                password=password,
            )
        except Exception as error:
            self.output.setPlainText(str(error)); self.backup_password.clear(); return
        finally:
            self.backup_password.clear()
        self.output.setPlainText(
            "RESTAURAÇÃO PREPARADA E AINDA NÃO APLICADA\n"
            f"Pré-backup: {result.safety_backup}\nSolicitação: {result.request_file}\n"
            "Para aplicar, o NabiCode precisa encerrar completamente."
        )
        self.prepare_button.setEnabled(False); self.restore_confirmation.clear()
        decision = QMessageBox.question(
            self, "Encerrar e restaurar",
            "O NabiCode será encerrado agora. O helper verificará novamente os hashes, "
            "aplicará o banco preparado e restaurará o banco anterior se algo falhar.\n\n"
            "Deseja encerrar e aplicar a restauração?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if decision != QMessageBox.StandardButton.Yes:
            return
        try:
            self.application.launch_prepared_restore(result)
        except Exception as error:
            self.output.append(f"\nNão foi possível iniciar o helper: {error}")
            return
        QApplication.instance().quit()

    def reject(self):
        self.backup_password.clear(); super().reject()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                if not event.isAutoRepeat(): self.reject()
                event.accept(); return True
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                if event.isAutoRepeat(): event.accept(); return True
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    watched.previousInFocusChain().setFocus(Qt.FocusReason.BacktabFocusReason)
                    event.accept(); return True
        return super().eventFilter(watched, event)
