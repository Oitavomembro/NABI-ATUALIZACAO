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
        self.copy_button.setToolTip("Copia os 64 caracteres completos exigidos pelo emissor.")
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
        instructions = QLabel(
            "Envie ao emissor o texto obtido pelo botão Copiar código da máquina. "
            "Ele contém 64 caracteres; a identificação resumida não basta para emitir."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        layout.addLayout(buttons)
        self.activate_button.clicked.connect(self._select_and_activate)
        self.copy_button.clicked.connect(self._copy_machine_code)
        self.close_button.clicked.connect(self.reject)
        self._refresh(policy)

    def _refresh(self, policy: FicharioLicensePolicy) -> None:
        self.status.setText(policy.message)
        self.machine_code.setText(
            f"Identificação resumida desta máquina: <b>{policy.decision.machine_code}</b>"
        )

    def _copy_machine_code(self) -> None:
        try:
            fingerprint = self._service.activation_fingerprint()
        except Exception:
            self.copy_button.setText("Copiar código da máquina")
            QMessageBox.warning(
                self, "Código indisponível",
                "Não foi possível obter a identificação completa desta máquina. "
                "Não use o código resumido para emitir a licença.",
            )
            return
        QApplication.clipboard().setText(fingerprint)
        self.copy_button.setText("Código completo copiado!")

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
