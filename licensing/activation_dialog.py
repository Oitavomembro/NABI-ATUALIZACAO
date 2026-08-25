from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout,
)

from .gate import Capability, LicenseGate
from .runtime import startup_block_message


class LicenseActivationDialog(QDialog):
    """Ativa a licença oficial sem inicializar banco ou serviços."""

    def __init__(self, license_service, decision, parent=None):
        super().__init__(parent)
        self._service = license_service
        self.setWindowTitle("Ativar NabiCode")
        self.setMinimumWidth(560)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.machine_code = QLabel()
        self.machine_code.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.copy_button = QPushButton("Copiar código da máquina")
        self.activate_button = QPushButton("Selecionar licença .nabilic")
        self.close_button = QPushButton("Fechar")
        buttons = QHBoxLayout()
        buttons.addWidget(self.close_button)
        buttons.addStretch(1)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.activate_button)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Licença do NabiCode</h2>"))
        layout.addWidget(QLabel(
            "O programa está em modo restrito. Ative uma licença oficial "
            "assinada para iniciar a configuração."
        ))
        layout.addWidget(self.status)
        layout.addWidget(self.machine_code)
        layout.addLayout(buttons)
        self.close_button.clicked.connect(self.reject)
        self.copy_button.clicked.connect(self._copy_machine_code)
        self.activate_button.clicked.connect(self._select_and_activate)
        self._refresh(decision)

    def _refresh(self, decision) -> None:
        self._decision = decision
        self._machine_code_value = decision.machine_code
        self.status.setText(
            startup_block_message(LicenseGate(decision), Capability.QT)
        )
        self.machine_code.setText(
            f"Código desta máquina: <b>{decision.machine_code}</b>"
        )

    def _copy_machine_code(self) -> None:
        QApplication.clipboard().setText(self._machine_code_value)
        self.copy_button.setText("Código copiado!")

    def _select_and_activate(self) -> None:
        selected, _selected_filter = QFileDialog.getOpenFileName(
            self, "Selecionar licença NabiCode", "", "Licença NabiCode (*.nabilic)"
        )
        if not selected:
            return
        try:
            decision = self._service.activate(Path(selected))
        except Exception:
            QMessageBox.warning(
                self, "Licença não aceita",
                "Não foi possível validar esse arquivo. Confira a licença e tente novamente.",
            )
            return
        self._refresh(decision)
        if not LicenseGate(decision).allows(Capability.QT):
            QMessageBox.warning(self, "Licença não aceita", self.status.text())
            return
        QMessageBox.information(self, "Licença ativada", "Licença ativada com sucesso.")
        self.accept()
