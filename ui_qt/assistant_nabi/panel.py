from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from assistant_nabi import AssistantTurn


class _WorkerSignals(QObject):
    completed = Signal(int, object)


class _AskWorker(QRunnable):
    def __init__(self, generation: int, service, message: str) -> None:
        super().__init__()
        self.generation = generation
        self.service = service
        self.message = message
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            turn = self.service.ask(self.message)
        except Exception:
            turn = AssistantTurn(
                "A Nabi encontrou uma falha segura. O NabiCode continua disponível.",
                safe_failure=True,
            )
        self.signals.completed.emit(self.generation, turn)


class NabiAssistantPanel(QWidget):
    """Painel escrito opcional; não possui acesso direto a banco, GUI ou Fiscal."""

    def __init__(self, service, parent=None, *, thread_pool=None) -> None:
        super().__init__(parent)
        self._service = service
        self._pool = thread_pool or QThreadPool.globalInstance()
        self._generation = 0
        self._busy = False
        self._workers: set[_AskWorker] = set()
        self.setObjectName("nabiAssistantPanel")
        self.setMinimumWidth(320)

        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.mascot = QLabel("N")
        self.mascot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mascot.setFixedSize(42, 42)
        self.mascot.setAccessibleName("Mascote Nabi")
        self.title = QLabel("NABI — ASSISTENTE")
        self.title.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.status = QLabel("Disponível")
        self.status.setAccessibleName("Estado da Nabi")
        header.addWidget(self.mascot)
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.status)
        root.addLayout(header)

        self.history = QTextBrowser()
        self.history.setOpenExternalLinks(False)
        self.history.setAccessibleName("Histórico da conversa com a Nabi")
        root.addWidget(self.history, 1)

        entry = QHBoxLayout()
        self.message = QLineEdit()
        self.message.setPlaceholderText("Escreva o que deseja consultar...")
        self.message.setAccessibleName("Mensagem para a Nabi")
        self.send = QPushButton("Enviar")
        self.voice = QPushButton("Voz — em preparação")
        self.voice.setEnabled(False)
        self.voice.setToolTip("A primeira versão da Nabi funciona somente por texto.")
        entry.addWidget(self.message, 1)
        entry.addWidget(self.send)
        root.addLayout(entry)
        root.addWidget(self.voice)

        self.stop = QPushButton("PARAR NABI")
        self.stop.setObjectName("stopNabi")
        self.stop.setToolTip("Invalida a solicitação atual e impede novos comandos até reativar.")
        root.addWidget(self.stop)

        self.send.clicked.connect(self.submit)
        self.message.returnPressed.connect(self.submit)
        self.stop.clicked.connect(self.stop_nabi)
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QWidget#nabiAssistantPanel { background: #0d1117; color: #f0f6fc; }
            QTextBrowser, QLineEdit {
                background: #161b22; color: #f0f6fc; border: 1px solid #30363d;
                border-radius: 7px; padding: 8px;
            }
            QPushButton { background: #2478e5; color: white; border: 0; padding: 9px; }
            QPushButton#stopNabi { background: #b62324; font-weight: 700; }
            QLabel { color: #f0f6fc; }
        """)
        self.mascot.setStyleSheet(
            "background: #00d48a; color: #07130f; border-radius: 21px; font-weight: 900;"
        )

    def submit(self) -> None:
        if self._busy or not self.send.isEnabled():
            return
        text = self.message.text().strip()
        if not text:
            self.status.setText("Digite uma mensagem")
            self.message.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self._generation += 1
        generation = self._generation
        self._busy = True
        self._set_controls(False)
        self.status.setText("Pensando…")
        self.history.append(f"<b>Você:</b> {self._escape(text)}")
        self.message.clear()
        worker = _AskWorker(generation, self._service, text)
        self._workers.add(worker)
        worker.signals.completed.connect(
            lambda received_generation, turn, current=worker: self._complete(
                received_generation, turn, current
            )
        )
        self._pool.start(worker)

    def _complete(self, generation: int, turn: AssistantTurn, worker=None) -> None:
        if worker is not None:
            self._workers.discard(worker)
        if generation != self._generation:
            return
        self._busy = False
        self._set_controls(True)
        self.status.setText("Bloqueada" if turn.safe_failure else "Concluído")
        self.history.append(f"<b>Nabi:</b> {self._escape(turn.message)}")
        for result in turn.tool_results:
            state = "Concluída" if result.success else "Não executada"
            self.history.append(
                f"<small>{self._escape(result.tool_name)} — {state}</small>"
            )
            detail = self._result_text(result)
            if detail:
                self.history.append(f"<pre>{self._escape(detail)}</pre>")
        self.message.setFocus(Qt.FocusReason.OtherFocusReason)

    def stop_nabi(self) -> None:
        self._generation += 1
        self._busy = False
        self._set_controls(False)
        self.status.setText("Parada pelo operador")
        self.history.append("<b>Nabi:</b> Solicitações pendentes foram invalidadas.")

    def reactivate(self) -> None:
        self._generation += 1
        self._busy = False
        self._set_controls(True)
        self.status.setText("Disponível")

    def _set_controls(self, enabled: bool) -> None:
        self.message.setEnabled(enabled)
        self.send.setEnabled(enabled)

    @staticmethod
    def _escape(value: object) -> str:
        import html

        return html.escape(str(value or ""), quote=True)

    @staticmethod
    def _result_text(result) -> str:
        if not result.success:
            return result.message or "Consulta não executada."
        payload = result.payload
        if result.tool_name == "produtos.pesquisar":
            items = payload.get("items", ())
            if not items:
                return "Nenhum produto encontrado."
            return "\n".join(
                f"{item['code']} — {item['description']} — R$ {item['sale_price']}"
                for item in items
            )
        if result.tool_name == "clientes.pesquisar":
            items = payload.get("items", ())
            if not items:
                return "Nenhum cliente encontrado."
            return "\n".join(
                f"{item['record_number'] if item['record_number'] is not None else item['code']}"
                f" — {item['name']}"
                for item in items
            )
        if result.tool_name == "produtos.consultar_estoque":
            return (
                f"Produto #{payload['product_id']} — estoque {payload['current_quantity']} — "
                f"mínimo {payload['minimum_quantity']} — {payload['status']}"
            )
        if result.tool_name == "diagnostico.executar_testes":
            state = "APROVADA" if payload.get("passed") else "FALHOU"
            return f"Suíte {payload.get('suite', '')}: {state}\n{payload.get('output', '')}"
        return "Resultado disponível, sem renderizador visual registrado."
