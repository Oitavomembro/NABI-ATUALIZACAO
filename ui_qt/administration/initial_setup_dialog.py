from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)
from services.company_xml_import_service import CompanyXMLImportService


class InitialSetupDialog(QDialog):
    """Primeiro acesso restrito; não oferece nenhum módulo operacional."""

    def __init__(self, security, parent=None):
        super().__init__(parent)
        self.security = security
        self.setWindowTitle("Configuração inicial do NabiCode")
        self.setModal(True)
        self.setMinimumWidth(560)
        root = QVBoxLayout(self)
        title = QLabel("PRIMEIRO ACESSO")
        title.setStyleSheet("font-size:22px;font-weight:900;color:#00d084")
        root.addWidget(title)
        note = QLabel(
            "Configure a empresa e crie o primeiro administrador. "
            "Nenhuma venda, operação financeira ou fiscal será liberada antes da conclusão."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        self.nabi_guidance = QLabel()
        self.nabi_guidance.setObjectName("nabiOnboardingGuide")
        self.nabi_guidance.setWordWrap(True)
        self.nabi_guidance.setStyleSheet(
            "QLabel#nabiOnboardingGuide{background:#111b26;border:1px solid #21b7d8;"
            "border-radius:10px;padding:12px;color:#e8f6ff;font-size:14px;}"
        )
        root.addWidget(self.nabi_guidance)
        form = QFormLayout()
        self.store_name = QLineEdit()
        self.document = QLineEdit(); self.document.setMaxLength(18)
        self.email = QLineEdit(); self.email.setMaxLength(160)
        self.username = QLineEdit("admin"); self.username.setMaxLength(60)
        self.display_name = QLineEdit("Administrador"); self.display_name.setMaxLength(120)
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_confirmation = QLineEdit(); self.password_confirmation.setEchoMode(QLineEdit.EchoMode.Password)
        for label, field in (
            ("Empresa/loja*", self.store_name), ("CNPJ", self.document),
            ("E-mail", self.email), ("Usuário administrador*", self.username),
            ("Nome do administrador*", self.display_name), ("Senha*", self.password),
            ("Repita a senha*", self.password_confirmation),
        ):
            form.addRow(label, field)
        root.addLayout(form)
        self.import_xml_button = QPushButton("Importar dados de XML")
        self.import_xml_button.clicked.connect(lambda _checked=False: self.import_xml())
        root.addWidget(self.import_xml_button)
        self.finish = QPushButton("Concluir configuração [Enter]")
        self.finish.setStyleSheet("background:#238636;color:white;min-height:38px;font-weight:800")
        self.finish.clicked.connect(self.complete)
        root.addWidget(self.finish)
        self.fields = (
            self.store_name, self.document, self.email, self.username,
            self.display_name, self.password, self.password_confirmation,
            self.import_xml_button, self.finish,
        )
        for field in self.fields:
            field.installEventFilter(self)
        self._guidance = {
            self.store_name: "Olá! Eu sou a Nabi. Primeiro, informe o nome que aparecerá nas telas e comprovantes.",
            self.document: "Digite o CNPJ da empresa. No modo não fiscal ele identifica a empresa, sem iniciar comunicação fiscal.",
            self.email: "Informe um e-mail administrativo para contato e recuperação. Nada será enviado automaticamente.",
            self.username: "Escolha o nome usado para entrar no NabiCode. Anote-o exatamente como foi digitado.",
            self.display_name: "Informe o nome que aparecerá na auditoria das operações.",
            self.password: "Crie uma senha exclusiva com pelo menos oito caracteres. Eu nunca mostro nem armazeno essa senha em texto aberto.",
            self.password_confirmation: "Repita a senha. Depois desta etapa, o acesso exigirá usuário e senha.",
            self.import_xml_button: "Escolha um XML fiscal autorizado local. Vou mostrar emitente e destinatário e nada será salvo sem sua confirmação.",
            self.finish: "Vou validar os dados e criar somente o primeiro administrador. Depois ajudarei com caixa, impressão e backup.",
        }
        self._show_guidance(self.store_name)
        self.store_name.setFocus()

    def import_xml(self, path=None, *, selected_role="") -> bool:
        # QPushButton.clicked emits a boolean.  Keep this public entry point
        # defensive as it is also used directly by tests and integrations.
        if isinstance(path, bool):
            path = None
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Importar dados de XML", "", "XML fiscal (*.xml)")
            if not path:
                return False
        try:
            service = CompanyXMLImportService()
            review = service.inspect(path, known_documents=(self.document.text(),))
            role = selected_role or review.selected_role
            if not role:
                labels = [f"{item.role}: {item.legal_name} ({item.document})" for item in review.participants]
                choice, accepted = QInputDialog.getItem(
                    self, "Qual participante é sua empresa?", "Confirme o participante:", labels, 0, False,
                )
                if not accepted:
                    return False
                role = review.participants[labels.index(choice)].role
            review = service.select(review, role, known_documents=(self.document.text(),))
            participant = review.selected
            preview = (
                f"Origem: XML local autorizado\nParticipante: {participant.role}\n"
                f"Empresa/loja: {self.store_name.text() or '(vazio)'} → {participant.trade_name or participant.legal_name}\n"
                f"CNPJ/CPF: {self.document.text() or '(vazio)'} → {participant.document}\n"
                f"E-mail: {self.email.text() or '(vazio)'} → {participant.email or '(ausente; manter)'}\n\n"
                "Regime/CRT, CSC, certificado, senha, séries, numeração e credenciamento não serão preenchidos."
            )
            answer = QMessageBox.question(
                self, "Prévia da importação de XML", preview,
                QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Apply:
                return False
            self.store_name.setText(participant.trade_name or participant.legal_name)
            self.document.setText(participant.document)
            if participant.email:
                self.email.setText(participant.email)
            return True
        except Exception as error:
            QMessageBox.warning(self, "Importar dados de XML", str(error))
            return False

    def _show_guidance(self, field) -> None:
        message = self._guidance.get(field)
        if message:
            self.nabi_guidance.setText(
                f"<b>NABI • ASSISTENTE DE CONFIGURAÇÃO</b><br>{message}"
            )

    def eventFilter(self, watched, event):
        if watched in self.fields and event.type() == QEvent.Type.FocusIn:
            self._show_guidance(watched)
        if watched in self.fields and event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            event.accept()
            if event.isAutoRepeat():
                return True
            index = self.fields.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.fields[max(0, index - 1)].setFocus()
            elif watched is self.finish:
                self.complete()
            elif watched is self.import_xml_button:
                self.import_xml()
            else:
                self.fields[index + 1].setFocus()
            return True
        return super().eventFilter(watched, event)

    def complete(self) -> None:
        if self.password.text() != self.password_confirmation.text():
            QMessageBox.warning(self, "Configuração inicial", "As senhas não coincidem.")
            self.password.clear(); self.password_confirmation.clear(); self.password.setFocus()
            return
        try:
            self.security.complete_initial_setup(
                username=self.username.text(), display_name=self.display_name.text(),
                password=self.password.text(), store_name=self.store_name.text(),
                document=self.document.text(), email=self.email.text(),
            )
        except Exception as error:
            QMessageBox.warning(self, "Configuração inicial", str(error))
            return
        self.password.clear(); self.password_confirmation.clear()
        QMessageBox.information(
            self, "Configuração concluída",
            "Primeiro administrador criado. Agora entre com o usuário e a senha definidos.",
        )
        self.accept()
