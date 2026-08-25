from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class _WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class BackupPackageWorker(QRunnable):
    def __init__(self, service, *, directory: str, encrypted: bool, password: str):
        super().__init__()
        self.service = service
        self.directory = directory
        self.encrypted = encrypted
        self.password = password
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.service.create_backup_package(
                directory=self.directory,
                encrypted=self.encrypted,
                password=self.password,
            )
        except Exception as error:
            self.signals.failed.emit(type(error).__name__)
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.password = ""


class BackupPackageDialog(QDialog):
    ENCRYPTED = "Criptografado e autenticado — recomendado"
    LEGACY = "Legado .db — não criptografado (inseguro)"

    def __init__(self, service, *, initial_directory: str = "", worker_pool=None, parent=None):
        super().__init__(parent)
        self.service = service
        self.pool = worker_pool or QThreadPool.globalInstance()
        self._busy = False
        self._worker = None
        self.setWindowTitle("Backup protegido do NabiCode")
        self.resize(660, 470)
        self.setStyleSheet(
            "QDialog{background:#0d1117;color:#f0f6fc;font-size:14px;}"
            "QLabel{color:#f0f6fc;}QLineEdit,QComboBox,QTextEdit{background:#161b22;"
            "color:#f0f6fc;border:1px solid #30363d;padding:6px;}"
            "QPushButton{background:#21262d;color:#f0f6fc;padding:8px;font-weight:700;}"
            "QPushButton#primary{background:#238636;}"
        )

        root = QVBoxLayout(self)
        title = QLabel("CRIAR E VERIFICAR BACKUP")
        title.setStyleSheet("font-size:20px;font-weight:900;color:#00d084")
        root.addWidget(title)
        root.addWidget(QLabel("Destino"))
        destination_row = QHBoxLayout()
        self.destination = QLineEdit(initial_directory)
        self.choose = QPushButton("Escolher…")
        self.choose.clicked.connect(self._choose_directory)
        destination_row.addWidget(self.destination, 1)
        destination_row.addWidget(self.choose)
        root.addLayout(destination_row)

        root.addWidget(QLabel("Proteção"))
        self.mode = QComboBox()
        self.mode.addItems((self.ENCRYPTED, self.LEGACY))
        self.mode.currentIndexChanged.connect(self._mode_changed)
        root.addWidget(self.mode)
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        root.addWidget(self.warning)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Mínimo de 12 caracteres")
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.setPlaceholderText("Repita a senha")
        self.password_label = QLabel("Senha do backup")
        self.confirm_password_label = QLabel("Confirme a senha")
        root.addWidget(self.password_label); root.addWidget(self.password)
        root.addWidget(self.confirm_password_label); root.addWidget(self.confirm_password)

        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setPlaceholderText(
            "O arquivo será gerado e restaurado somente em TEMP para comprovar integridade."
        )
        root.addWidget(self.result, 1)
        buttons = QHBoxLayout()
        self.cancel = QPushButton("Fechar [Esc]")
        self.cancel.clicked.connect(self.reject)
        self.generate = QPushButton("Gerar e verificar [Enter]")
        self.generate.setObjectName("primary")
        self.generate.clicked.connect(self._start)
        buttons.addWidget(self.cancel); buttons.addWidget(self.generate)
        root.addLayout(buttons)
        for widget in self.findChildren(QObject):
            widget.installEventFilter(self)
        self._mode_changed()
        self.destination.setFocus(Qt.FocusReason.OtherFocusReason)

    def _choose_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Escolher destino do backup", self.destination.text()
        )
        if selected:
            self.destination.setText(selected)

    def _mode_changed(self) -> None:
        encrypted = self.mode.currentText() == self.ENCRYPTED
        self.password.setVisible(encrypted)
        self.confirm_password.setVisible(encrypted)
        self.password_label.setVisible(encrypted)
        self.confirm_password_label.setVisible(encrypted)
        self.warning.setText(
            "Recomendado: a senha não será salva e não existe recuperação. "
            "Guarde-a separadamente."
            if encrypted else
            "ATENÇÃO: o formato legado contém dados pessoais sem criptografia. "
            "Use somente quando a compatibilidade for indispensável."
        )
        self.warning.setStyleSheet(
            "color:#d29922;font-weight:700" if encrypted else "color:#f85149;font-weight:900"
        )

    def _start(self) -> None:
        if self._busy:
            return
        destination = self.destination.text().strip()
        encrypted = self.mode.currentText() == self.ENCRYPTED
        password = self.password.text() if encrypted else ""
        confirmation = self.confirm_password.text() if encrypted else ""
        if not destination:
            self.result.setPlainText("Escolha uma pasta de destino.")
            self.destination.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        if encrypted and (len(password) < 12 or password != confirmation):
            self.result.setPlainText("Informe duas senhas iguais com ao menos 12 caracteres.")
            self.password.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self._clear_passwords()
        self._busy = True
        self.generate.setEnabled(False)
        self.cancel.setEnabled(False)
        self.mode.setEnabled(False)
        self.destination.setEnabled(False)
        self.result.setPlainText("Gerando e verificando em área temporária…")
        worker = BackupPackageWorker(
            self.service, directory=destination, encrypted=encrypted, password=password
        )
        self._worker = worker
        worker.signals.succeeded.connect(self._succeeded)
        worker.signals.failed.connect(self._failed)
        self.pool.start(worker)

    @Slot(object)
    def _succeeded(self, result) -> None:
        self._finish()
        protection = "criptografado e autenticado" if result.encrypted else "legado não criptografado"
        self.result.setPlainText(
            "BACKUP COMPROVADO\n"
            f"Arquivo: {result.filename}\n"
            f"Formato: {protection}\n"
            f"Schema: {result.schema_version}\n"
            f"SHA-256: {result.sha256}"
        )

    @Slot(str)
    def _failed(self, _error_type: str) -> None:
        self._finish()
        self.result.setPlainText(
            "Falha ao gerar ou verificar o backup. Nenhuma restauração foi aplicada "
            "ao banco ativo. Confira destino, espaço disponível e senha."
        )

    def _finish(self) -> None:
        self._clear_passwords()
        self._busy = False
        self._worker = None
        self.generate.setEnabled(True)
        self.cancel.setEnabled(True)
        self.mode.setEnabled(True)
        self.destination.setEnabled(True)
        self.generate.setFocus(Qt.FocusReason.OtherFocusReason)

    def _clear_passwords(self) -> None:
        self.password.clear()
        self.confirm_password.clear()

    def reject(self) -> None:
        self._clear_passwords()
        if self._busy:
            self.result.setPlainText("Aguarde a conclusão segura da geração e verificação.")
            return
        super().reject()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                if event.isAutoRepeat():
                    event.accept(); return True
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    previous = watched.previousInFocusChain()
                    if previous is not None:
                        previous.setFocus(Qt.FocusReason.BacktabFocusReason)
                    event.accept(); return True
                if watched is self.generate:
                    self._start(); event.accept(); return True
                next_widget = {
                    self.destination: self.mode,
                    self.mode: self.password if self.mode.currentText() == self.ENCRYPTED else self.generate,
                    self.password: self.confirm_password,
                    self.confirm_password: self.generate,
                }.get(watched)
                if next_widget is not None:
                    next_widget.setFocus(Qt.FocusReason.TabFocusReason)
                    event.accept(); return True
            if event.key() == Qt.Key.Key_Escape:
                self.reject(); event.accept(); return True
        return super().eventFilter(watched, event)
