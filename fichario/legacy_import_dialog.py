from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTextEdit, QVBoxLayout,
)

from database.sqlite_connection import backup_database
from services.mysql_migration_service import MySQLMigrationService
from ui_qt.commercial.customer_dialog import STYLE


class LegacyFicharioImportDialog(QDialog):
    """Assistente explícito para o dump MySQL do Fichário antigo."""

    def __init__(self, database, profile, parent=None, *, service=None) -> None:
        super().__init__(parent)
        self.database = database
        self.profile = profile
        self.service = service or MySQLMigrationService()
        self._summary = None
        self.setWindowTitle("Importar Fichário antigo")
        self.resize(760, 560)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        title = QLabel("IMPORTAR CLIENTES DO FICHÁRIO ANTIGO")
        title.setStyleSheet("font-size:22px;font-weight:900;color:#00d084")
        layout.addWidget(title)
        layout.addWidget(QLabel(
            "O arquivo será analisado primeiro. A importação cria um backup automático "
            "e preserva número da ficha, cadastro e saldo atual. O histórico antigo não "
            "será carregado nesta primeira importação."
        ))
        self.report = QTextEdit(); self.report.setReadOnly(True)
        self.report.setPlainText("Selecione o arquivo .sql do sistema antigo.")
        layout.addWidget(self.report, 1)
        row = QHBoxLayout()
        self.analyze_button = QPushButton("Selecionar e analisar arquivo .sql")
        self.import_button = QPushButton("IMPORTAR DADOS ANALISADOS")
        self.import_button.setObjectName("primary"); self.import_button.setEnabled(False)
        close = QPushButton("Fechar  [Esc]")
        self.analyze_button.clicked.connect(self._select_and_analyze)
        self.import_button.clicked.connect(self._import)
        close.clicked.connect(self.reject)
        row.addWidget(self.analyze_button); row.addWidget(self.import_button); row.addWidget(close)
        layout.addLayout(row)

    @staticmethod
    def _money(value) -> str:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def _select_and_analyze(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, "Selecionar backup do Fichário antigo", str(Path.home() / "Desktop"),
            "Backup SQL antigo (*.sql)",
        )
        if not source:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            audit = self.service.analyze_dump(source)
            summary = self.service.prepare_summary(source)
        except Exception as error:
            self._summary = None; self.import_button.setEnabled(False)
            QMessageBox.critical(self, "Arquivo recusado", str(error))
            return
        finally:
            QApplication.restoreOverrideCursor()
        clients = summary.get("clientes", {})
        counts = summary.get("contagens", {})
        self._summary = summary
        self.report.setPlainText(
            f"Arquivo: {source}\n\n"
            f"Clientes reconhecidos: {len(clients)}\n"
            f"Vendas antigas: {int(counts.get('venda', 0))}\n"
            f"Recebimentos antigos: {int(counts.get('recebimento', 0))}\n"
            f"Saldo total calculado: {self._money(summary.get('saldo_total', 0))}\n"
            "Movimentos antigos que serão importados: 0\n\n"
            f"Avisos da análise: {len(audit.get('avisos', []))}\n"
            "Revise estes totais antes de importar. Nenhum dado foi alterado nesta etapa."
        )
        self.import_button.setEnabled(bool(clients))

    def _import(self) -> None:
        if not self._summary:
            return
        answer = QMessageBox.question(
            self, "Confirmar importação",
            "Importar agora os clientes, fichas e saldos atuais?\n\n"
            "Um backup do banco atual será criado automaticamente antes da alteração.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.import_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = self.service.execute_summary(
                self._summary,
                database_path=self.database.database_path,
                backup_dir=self.profile.paths.backups,
                connect=self.database.connect,
                backup_database=backup_database,
                network_mode=False,
                import_events=False,
            )
        except Exception as error:
            QMessageBox.critical(
                self, "Importação não concluída",
                f"O banco foi preservado ou restaurado pelo processo seguro.\n\n{error}",
            )
            self.import_button.setEnabled(True)
            return
        finally:
            QApplication.restoreOverrideCursor()
        QMessageBox.information(
            self, "Importação concluída",
            f"Clientes incluídos: {result.get('novos', 0)}\n"
            f"Clientes atualizados: {result.get('atualizados', 0)}\n"
            f"Backup de segurança: {result.get('backup', 'criado')}",
        )
        self.accept()
