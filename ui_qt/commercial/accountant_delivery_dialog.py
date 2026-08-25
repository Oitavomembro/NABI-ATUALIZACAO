from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout,
)

from .accountant_center_dialog import STYLE


class _DeliverySignals(QObject):
    completed = Signal(int, str, object, object)


class AccountantDeliveryWorker(QRunnable):
    def __init__(self, generation, operation, application, plan):
        super().__init__()
        self.generation = generation
        self.operation = operation
        self.application = application
        self.plan = plan
        self.signals = _DeliverySignals()

    @Slot()
    def run(self):
        try:
            result, error = getattr(self.application, self.operation)(self.plan), None
        except Exception as caught:
            result, error = None, caught
        self.signals.completed.emit(self.generation, self.operation, result, error)


class AccountantDeliveryDialog(QDialog):
    """Entrega guiada: cada transição exige uma ação humana independente."""

    def __init__(self, application, package, parent=None, *, worker_pool=None):
        super().__init__(parent)
        self.application = application
        self.package = package
        self.pool = worker_pool or QThreadPool.globalInstance()
        self._plan = None
        self._status = ""
        self._busy = False
        self._generation = 0
        self._workers = []
        self.setWindowTitle("Entregar ao contador")
        self.resize(850, 620)
        self.setMinimumSize(760, 560)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        title = QLabel("ENTREGA AO CONTADOR")
        title.setStyleSheet("font-size:25px;font-weight:900;color:#d7e0e8")
        root.addWidget(title)
        summary = QLabel(
            f"Pacote: {package.path}\nCNPJ: {package.cnpj} • Competência: "
            f"{package.competence} • Perfil: {package.profile}"
        )
        summary.setWordWrap(True)
        root.addWidget(summary)
        self.recipient = QLineEdit()
        self.recipient.setPlaceholderText("Nome ou identificação do contador destinatário")
        root.addWidget(self.recipient)
        destination = QHBoxLayout()
        self.destination = QLineEdit()
        self.destination.setPlaceholderText("Pasta local, de rede ou OneDrive já existente")
        self.choose = QPushButton("Escolher pasta")
        self.choose.clicked.connect(self._choose_destination)
        destination.addWidget(self.destination, 1)
        destination.addWidget(self.choose)
        root.addLayout(destination)
        self.cnpj_confirmed = QCheckBox("Confirmei que este é o CNPJ correto")
        self.consent = QCheckBox("Autorizo entregar este pacote a este destinatário")
        root.addWidget(self.cnpj_confirmed)
        root.addWidget(self.consent)
        self.review = QPushButton("1. REVISAR ENTREGA")
        self.prepare = QPushButton("2. PREPARAR PACOTE IMUTÁVEL")
        self.enqueue = QPushButton("3. AUTORIZAR UMA TENTATIVA")
        self.dispatch = QPushButton("4. COPIAR PARA A PASTA")
        self.check = QPushButton("5. VERIFICAR RECEBIMENTO")
        self.dispatch.setObjectName("primary")
        for button in (self.review, self.prepare, self.enqueue, self.dispatch, self.check):
            root.addWidget(button)
        self.status = QLabel("REVISÃO PENDENTE — nada foi preparado ou copiado.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            "background:#171d24;border:1px solid #4b5662;border-radius:8px;"
            "padding:12px;color:#d6b95f;font-weight:800"
        )
        root.addWidget(self.status)
        footer = QHBoxLayout()
        footer.addStretch()
        close = QPushButton("Fechar [Esc]")
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        root.addLayout(footer)
        self.review.clicked.connect(self._review)
        self.prepare.clicked.connect(lambda: self._run("prepare"))
        self.enqueue.clicked.connect(lambda: self._run("enqueue"))
        self.dispatch.clicked.connect(lambda: self._run("dispatch"))
        self.check.clicked.connect(lambda: self._run("check_receipt"))
        self._fields = (
            self.recipient, self.destination, self.choose, self.cnpj_confirmed,
            self.consent, self.review, self.prepare, self.enqueue, self.dispatch, self.check,
        )
        for field in self._fields:
            field.installEventFilter(self)
        for field in (self.recipient, self.destination, self.cnpj_confirmed, self.consent):
            signal = getattr(field, "textChanged", None) or getattr(field, "toggled", None)
            signal.connect(self._invalidate)
        self._escape = QShortcut(QKeySequence("Esc"), self)
        self._escape.setAutoRepeat(False)
        self._escape.activated.connect(self.reject)
        self._update_actions()
        self.recipient.setFocus(Qt.FocusReason.OtherFocusReason)

    def _choose_destination(self):
        path = QFileDialog.getExistingDirectory(self, "Escolher pasta de entrega")
        if path:
            self.destination.setText(path)

    def _invalidate(self, *_):
        if self._plan is None:
            return
        self._plan = None
        self._status = ""
        self.status.setText("REVISÃO PENDENTE — dados alterados; revise novamente.")
        self._set_editable(True)
        self._update_actions()

    def _set_editable(self, editable):
        for field in (
            self.recipient, self.destination, self.choose,
            self.cnpj_confirmed, self.consent, self.review,
        ):
            field.setEnabled(editable and not self._busy)

    def _review(self):
        if self._busy:
            return
        try:
            self._plan = self.application.review(
                package=self.package, recipient=self.recipient.text(),
                destination=self.destination.text(),
                cnpj_confirmed=self.cnpj_confirmed.isChecked(),
                consent=self.consent.isChecked(),
            )
        except Exception as error:
            QMessageBox.warning(self, "Entrega ao contador", str(error))
            return
        self._status = "REVISADO"
        self.status.setText(
            "REVISADO — nenhuma outbox foi criada e nenhum arquivo foi copiado. "
            "Use Preparar para criar o snapshot imutável."
        )
        self._set_editable(False)
        self._update_actions()
        self.prepare.setFocus(Qt.FocusReason.OtherFocusReason)

    def _run(self, operation):
        if self._busy or self._plan is None:
            return
        allowed = {
            "prepare": self._status == "REVISADO",
            "enqueue": self._status in {"PREPARADO", "FALHA"},
            "dispatch": self._status == "ENFILEIRADO",
            "check_receipt": self._status in {
                "ENVIADO_AO_TRANSPORTE", "DESCONHECIDO", "RECEBIDO_CONFIRMADO"
            },
        }
        if not allowed.get(operation, False):
            return
        self._busy = True
        self._generation += 1
        worker = AccountantDeliveryWorker(
            self._generation, operation, self.application, self._plan
        )
        worker.signals.completed.connect(self._completed)
        self._workers.append(worker)
        self._update_actions()
        self.pool.start(worker)

    def _completed(self, generation, operation, result, error):
        self._workers = [worker for worker in self._workers if worker.generation != generation]
        if generation != self._generation:
            return
        self._busy = False
        if error is not None:
            self.status.setText(f"OPERAÇÃO NÃO CONCLUÍDA — {error}")
            self._update_actions()
            return
        self._status = result.status
        messages = {
            "PREPARADO": "PREPARADO — snapshot imutável criado; ainda não foi enfileirado ou copiado.",
            "ENFILEIRADO": "ENFILEIRADO — uma tentativa foi autorizada; ainda não foi copiado.",
            "ENVIADO_AO_TRANSPORTE": (
                "ENVIADO AO TRANSPORTE — a cópia foi aceita pela pasta, mas o "
                "recebimento ainda não está confirmado."
            ),
            "RECEBIDO_CONFIRMADO": (
                "RECEBIDO CONFIRMADO — presença e recibo foram verificados. Isso não "
                "significa que o contador abriu, leu, importou ou aprovou o pacote."
            ),
            "DESCONHECIDO": (
                "RESULTADO DESCONHECIDO — não repita a entrega. Verifique o recebimento "
                "antes de qualquer nova tentativa."
            ),
            "FALHA": "FALHA — a tentativa falhou; revise o erro antes de autorizar outra tentativa.",
        }
        suffix = f" Código: {result.last_error_code}." if result.last_error_code else ""
        self.status.setText(messages.get(result.status, result.status) + suffix)
        self._update_actions()

    def _update_actions(self):
        self.prepare.setEnabled(not self._busy and self._status == "REVISADO")
        self.enqueue.setEnabled(not self._busy and self._status in {"PREPARADO", "FALHA"})
        self.dispatch.setEnabled(not self._busy and self._status == "ENFILEIRADO")
        self.check.setEnabled(
            not self._busy and self._status in {
                "ENVIADO_AO_TRANSPORTE", "DESCONHECIDO", "RECEBIDO_CONFIRMADO"
            }
        )

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in {
            Qt.Key.Key_Return, Qt.Key.Key_Enter
        } and watched in self._fields:
            if event.isAutoRepeat():
                event.accept()
                return True
            visible = [field for field in self._fields if field.isVisible() and field.isEnabled()]
            if not visible:
                return True
            index = visible.index(watched)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                visible[max(0, index - 1)].setFocus(Qt.FocusReason.BacktabFocusReason)
            elif watched is self.review:
                self._review()
            elif watched is self.prepare:
                self._run("prepare")
            elif watched is self.enqueue:
                self._run("enqueue")
            elif watched is self.dispatch:
                self._run("dispatch")
            elif watched is self.check:
                self._run("check_receipt")
            else:
                visible[min(index + 1, len(visible) - 1)].setFocus(Qt.FocusReason.TabFocusReason)
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        self._generation += 1
        self._busy = False
        super().closeEvent(event)
