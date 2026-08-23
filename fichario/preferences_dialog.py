from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)

from ui_qt.commercial.customer_dialog import STYLE


def fichario_settings() -> QSettings:
    return QSettings("NabiCode", "Fichario")


def interface_font_size() -> int:
    value = int(fichario_settings().value("interface/font_size", 15))
    return max(12, min(value, 30))


def configured_backup_directory(profile) -> Path:
    configured = str(
        fichario_settings().value("backup/directory", str(profile.paths.backups)) or ""
    ).strip()
    return Path(configured or profile.paths.backups).expanduser().resolve()


class FicharioPreferencesDialog(QDialog):
    def __init__(self, profile, parent=None) -> None:
        super().__init__(parent)
        self.profile = profile
        self.setWindowTitle("Configurar Fichário")
        self.setMinimumWidth(720)
        self.setStyleSheet(STYLE + "\nQDialog{font-size:15px;}")
        layout = QVBoxLayout(self)
        title = QLabel("BACKUP E APARÊNCIA")
        title.setStyleSheet("font-size:22px;font-weight:900;color:#00d084")
        layout.addWidget(title)
        form = QFormLayout()
        self.daily = QCheckBox("Criar automaticamente uma cópia íntegra por dia")
        self.daily.setChecked(
            str(fichario_settings().value("backup/daily_enabled", "false")).lower()
            in {"true", "1", "yes"}
        )
        directory_row = QHBoxLayout()
        self.directory = QLineEdit(str(configured_backup_directory(profile)))
        self.directory.setReadOnly(True)
        choose = QPushButton("Escolher pasta...")
        choose.clicked.connect(self._choose_directory)
        directory_row.addWidget(self.directory, 1); directory_row.addWidget(choose)
        self.font_size = QComboBox()
        self.font_size.addItems(tuple(str(value) for value in range(12, 31)))
        self.font_size.setCurrentText(str(interface_font_size()))
        form.addRow("Backup diário", self.daily)
        form.addRow("Pasta dos backups", directory_row)
        form.addRow("Tamanho global das letras", self.font_size)
        layout.addLayout(form)
        note = QLabel(
            "Você pode escolher uma pasta sincronizada pelo OneDrive. O NabiCode cria "
            "o backup localmente e valida banco, schema e vínculos antes de considerar o dia concluído."
        )
        note.setWordWrap(True); layout.addWidget(note)
        buttons = QHBoxLayout(); buttons.addStretch()
        cancel = QPushButton("Cancelar")
        save = QPushButton("Salvar configurações"); save.setObjectName("primary")
        cancel.clicked.connect(self.reject); save.clicked.connect(self._save)
        buttons.addWidget(cancel); buttons.addWidget(save); layout.addLayout(buttons)

    def _choose_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Escolher pasta dos backups", self.directory.text()
        )
        if selected:
            self.directory.setText(str(Path(selected).resolve()))

    def _save(self) -> None:
        directory = Path(self.directory.text()).expanduser().resolve()
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.warning(self, "Pasta de backup", str(error)); return
        settings = fichario_settings()
        settings.setValue("backup/daily_enabled", self.daily.isChecked())
        settings.setValue("backup/directory", str(directory))
        settings.setValue("interface/font_size", int(self.font_size.currentText()))
        settings.setValue("clientes/font_size", int(self.font_size.currentText()))
        settings.sync()
        self.accept()
