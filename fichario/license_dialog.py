from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout,
)

from .license_policy import FicharioLicensePolicy


class FicharioLicenseDialog(QDialog):
    """Ativação restrita: não inicializa banco nem serviços comerciais."""

    def __init__(self, license_service, policy: FicharioLicensePolicy, parent=None):
        super().__init__(parent)
        self._service = license_service
        self.setWindowTitle("Ativar NabiCode Fichário")
        self.setMinimumWidth(520)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.machine_code = QLabel()
        self.machine_code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.copy_button = QPushButton("Copiar código da máquina")
        self.activate_button = QPushButton("Selecionar licença .nabilic")
        self.close_button = QPushButton("Fechar")
        buttons = QHBoxLayout()
        buttons.addWidget(self.close_button)
        buttons.addStretch(1)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.activate_button)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>Licença do NabiCode Fichário</h2>"))
        layout.addWidget(QLabel(
            "Este programa está em modo restrito. Selecione a licença assinada "
            "da edição FICHÁRIO para liberar o uso."
        ))
        layout.addWidget(self.status)
        layout.addWidget(self.machine_code)
        layout.addLayout(buttons)
        self.activate_button.clicked.connect(self._select_and_activate)
        self.copy_button.clicked.connect(self._copy_machine_code)
        self.close_button.clicked.connect(self.reject)
        self._refresh(policy)

    def _refresh(self, policy: FicharioLicensePolicy) -> None:
        self.status.setText(policy.message)
        self.machine_code.setText(
            f"Código desta máquina: <b>{policy.decision.machine_code}</b>"
        )
        self._machine_code_value = policy.decision.machine_code

    def _copy_machine_code(self) -> None:
        QApplication.clipboard().setText(self._machine_code_value)
        self.copy_button.setText("Código copiado!")

    def _select_and_activate(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self, "Selecionar licença NabiCode", "", "Licença NabiCode (*.nabilic)"
        )
        if not selected:
            return
        try:
            decision = self._service.activate(Path(selected))
        except Exception:
            QMessageBox.warning(
                self, "Licença não aceita",
                "Não foi possível validar este arquivo. Confira a licença e tente novamente.",
            )
            return
        policy = FicharioLicensePolicy(decision)
        self._refresh(policy)
        if not policy.operational:
            QMessageBox.warning(self, "Licença não aceita", policy.message)
            return
        QMessageBox.information(self, "Licença ativada", "Licença FICHÁRIO ativada com sucesso.")
        self.accept()
