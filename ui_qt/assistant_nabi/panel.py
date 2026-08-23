from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QRunnable,
    Qt,
    QThreadPool,
    Signal,
)
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from assistant_nabi import AssistantTurn

from .activation_dialog import NabiActivationDialog


class _WorkerSignals(QObject):
    completed = Signal(int, object)


class _ActivationSignals(QObject):
    completed = Signal(int, object, object)


class _ActivationWorker(QRunnable):
    def __init__(self, generation: int, manager, username: str, password: str) -> None:
        super().__init__()
        self.generation = generation
        self.manager = manager
        self.username = username
        self.password = password
        self.signals = _ActivationSignals()

    def run(self) -> None:
        error = None
        try:
            service = self.manager.activate(self.username, self.password)
        except Exception as exc:
            service = None
            error = exc
        finally:
            self.password = ""
        self.signals.completed.emit(self.generation, service, error)


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

    def __init__(
        self, service, parent=None, *, thread_pool=None, activation_manager=None
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._pool = thread_pool or QThreadPool.globalInstance()
        self._generation = 0
        self._busy = False
        self._activation_manager = activation_manager
        self._workers: set[_AskWorker] = set()
        self._pending_draft = None
        self._confirmation_token = None
        self.setObjectName("nabiAssistantPanel")
        self.setMinimumWidth(320)

        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.mascot = QLabel()
        self.mascot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mascot.setFixedSize(72, 72)
        self.mascot.setAccessibleName("Mascote Nabi")
        self._load_mascot()
        self._mascot_opacity = QGraphicsOpacityEffect(self.mascot)
        self.mascot.setGraphicsEffect(self._mascot_opacity)
        self._mascot_animation = QPropertyAnimation(
            self._mascot_opacity, b"opacity", self
        )
        self._mascot_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.title = QLabel("NABI — ASSISTENTE")
        self.title.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.status = QLabel()
        self.status.setAccessibleName("Estado da Nabi")
        identity = QVBoxLayout()
        identity.setSpacing(2)
        identity.addWidget(self.title)
        identity.addWidget(self.status)
        header.addWidget(self.mascot)
        header.addLayout(identity, 1)
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

        confirmation = QHBoxLayout()
        self.review_draft_button = QPushButton("REVISAR RASCUNHO")
        self.confirm_draft_button = QPushButton("CONFIRMAR RASCUNHO")
        self.review_draft_button.setVisible(False)
        self.confirm_draft_button.setVisible(False)
        confirmation.addWidget(self.review_draft_button)
        confirmation.addWidget(self.confirm_draft_button)
        root.addLayout(confirmation)

        self.activate_button = QPushButton("ATIVAR NABI")
        self.activate_button.setObjectName("activateNabi")
        self.activate_button.setVisible(activation_manager is not None)
        self.activate_button.setToolTip(
            "Exige usuário e senha reais antes de iniciar o modelo local."
        )
        root.addWidget(self.activate_button)

        self.stop = QPushButton("PARAR NABI")
        self.stop.setObjectName("stopNabi")
        self.stop.setToolTip("Invalida a solicitação atual e impede novos comandos até reativar.")
        root.addWidget(self.stop)

        self.send.clicked.connect(self.submit)
        self.message.returnPressed.connect(self.submit)
        self.activate_button.clicked.connect(self.request_activation)
        self.review_draft_button.clicked.connect(self.review_draft)
        self.confirm_draft_button.clicked.connect(self.confirm_draft)
        self.stop.clicked.connect(self.stop_nabi)
        self._apply_style()
        self._set_state("available", "Disponível")
        if not getattr(service, "available", True):
            self._show_unavailable(
                getattr(
                    service,
                    "unavailable_message",
                    "A Nabi ainda nao esta disponivel neste ambiente.",
                )
            )

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QWidget#nabiAssistantPanel { background: #0d1117; color: #f0f6fc; }
            QTextBrowser, QLineEdit {
                background: #161b22; color: #f0f6fc; border: 1px solid #30363d;
                border-radius: 7px; padding: 8px;
            }
            QPushButton { background: #2478e5; color: white; border: 0; padding: 9px; }
            QPushButton#stopNabi { background: #b62324; font-weight: 700; }
            QPushButton#activateNabi { background: #1769aa; font-weight: 700; }
            QLabel { color: #f0f6fc; }
        """)
        self.mascot.setStyleSheet("background: transparent;")

    def _load_mascot(self) -> None:
        asset = (
            Path(__file__).resolve().parent
            / "assets"
            / "nabi_mascot_blue_v2_transparent.png"
        )
        pixmap = QPixmap(str(asset))
        if pixmap.isNull():
            self.mascot.setText("N")
            self.mascot.setStyleSheet(
                "background: #2478e5; border-radius: 36px; font-weight: 900;"
            )
            self.mascot.setToolTip("Mascote Nabi indisponível; assistente continua funcional.")
            return
        self.mascot.setPixmap(
            pixmap.scaled(
                self.mascot.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _set_state(self, state: str, text: str) -> None:
        colors = {
            "available": "#58d6ff",
            "thinking": "#8ab4ff",
            "completed": "#36d98b",
            "warning": "#ffca5c",
            "blocked": "#ff6b6b",
            "stopped": "#a6adb7",
            "offline": "#a6adb7",
        }
        animated = state in {"thinking"}
        self.status.setText(text)
        self.status.setProperty("nabiState", state)
        self.status.setStyleSheet(
            f"color: {colors.get(state, '#f0f6fc')}; font-weight: 700;"
        )
        description = f"Nabi: {text}"
        self.status.setAccessibleDescription(description)
        self.mascot.setAccessibleDescription(description)
        self.mascot.setToolTip(description)
        self._mascot_animation.stop()
        self._mascot_opacity.setOpacity(1.0 if state != "offline" else 0.55)
        if animated:
            self._mascot_animation.setDuration(900)
            self._mascot_animation.setStartValue(0.62)
            self._mascot_animation.setEndValue(1.0)
            self._mascot_animation.setLoopCount(-1)
            self._mascot_animation.start()

    def submit(self) -> None:
        if self._busy or not self.send.isEnabled():
            return
        text = self.message.text().strip()
        if not text:
            self._set_state("warning", "Digite uma mensagem")
            self.message.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self._generation += 1
        generation = self._generation
        self._busy = True
        self._set_controls(False)
        self._set_state("thinking", "Pensando…")
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

    def request_activation(self) -> None:
        if self._activation_manager is None or self._busy:
            return
        credentials = NabiActivationDialog.get_credentials(self)
        if credentials is None:
            return
        self._start_activation(*credentials)

    def _start_activation(self, username: str, password: str) -> None:
        self._generation += 1
        generation = self._generation
        self._busy = True
        self._set_controls(False)
        self.activate_button.setEnabled(False)
        self._set_state("thinking", "Inicializando com segurança…")
        worker = _ActivationWorker(
            generation, self._activation_manager, username, password
        )
        self._workers.add(worker)
        worker.signals.completed.connect(
            lambda received, service, error, current=worker: self._activation_complete(
                received, service, error, current
            )
        )
        self._pool.start(worker)

    def _activation_complete(self, generation, service, error, worker=None) -> None:
        if worker is not None:
            self._workers.discard(worker)
        if generation != self._generation:
            if service is not None and self._activation_manager is not None:
                self._activation_manager.stop()
            return
        self._busy = False
        if service is None:
            self.activate_button.setEnabled(True)
            self._set_state("blocked", "Ativação não concluída")
            message = str(error or "Falha segura ao ativar a Nabi.")
            self.history.append(f"<b>Nabi:</b> {self._escape(message)}")
            return
        self._service = service
        self.activate_button.setVisible(False)
        self._set_controls(True)
        self._set_state("available", "Disponível")
        self.history.append("<b>Nabi:</b> Sessão autenticada. Modo somente leitura ativo.")
        self.message.setFocus(Qt.FocusReason.OtherFocusReason)

    def _complete(self, generation: int, turn: AssistantTurn, worker=None) -> None:
        if worker is not None:
            self._workers.discard(worker)
        if generation != self._generation:
            return
        self._busy = False
        self._set_controls(True)
        if turn.safe_failure:
            self._set_state("blocked", "Bloqueada")
        else:
            self._set_state("completed", "Concluído")
        self.history.append(f"<b>Nabi:</b> {self._escape(turn.message)}")
        for result in turn.tool_results:
            state = "Concluída" if result.success else "Não executada"
            self.history.append(
                f"<small>{self._escape(result.tool_name)} — {state}</small>"
            )
            detail = self._result_text(result)
            if detail:
                self.history.append(f"<pre>{self._escape(detail)}</pre>")
            if result.success and result.tool_name == "vendas.criar_rascunho":
                self._service.invalidate_confirmations()
                self._pending_draft = (
                    result.payload["draft_id"], result.payload["fingerprint"]
                )
                self._confirmation_token = None
                self.review_draft_button.setVisible(True)
                self.confirm_draft_button.setVisible(False)
        self.message.setFocus(Qt.FocusReason.OtherFocusReason)

    def review_draft(self) -> None:
        if self._pending_draft is None:
            return
        draft_id, fingerprint = self._pending_draft
        try:
            challenge = self._service.review_draft(draft_id, fingerprint)
        except Exception:
            self._set_state("blocked", "Revisão inválida")
            self.history.append("<b>Nabi:</b> O rascunho não pôde ser revisado com segurança.")
            return
        self._confirmation_token = challenge.token
        self.review_draft_button.setVisible(False)
        self.confirm_draft_button.setVisible(True)
        self._set_state("warning", "Aguardando confirmação")
        self.history.append(
            "<b>Nabi:</b> Confira itens, total, cliente e pagamento. "
            "A confirmação é temporária e vale somente para este conteúdo."
        )

    def confirm_draft(self) -> None:
        if self._pending_draft is None or self._confirmation_token is None:
            return
        draft_id, fingerprint = self._pending_draft
        try:
            self._service.confirm_draft(
                self._confirmation_token, draft_id, fingerprint
            )
        except Exception:
            self._set_state("blocked", "Confirmação recusada")
            self.history.append("<b>Nabi:</b> A confirmação expirou ou o rascunho mudou.")
            return
        self._confirmation_token = None
        self.confirm_draft_button.setVisible(False)
        self._set_state("completed", "Rascunho autorizado")
        self.history.append(
            "<b>Nabi:</b> Rascunho autorizado. Nenhuma venda foi registrada; "
            "a transferência segura ao PDV é a próxima etapa."
        )

    def stop_nabi(self) -> None:
        self._generation += 1
        self._busy = False
        self._set_controls(False)
        if hasattr(self._service, "invalidate_confirmations"):
            self._service.invalidate_confirmations()
        self._pending_draft = None
        self._confirmation_token = None
        self.review_draft_button.setVisible(False)
        self.confirm_draft_button.setVisible(False)
        if self._activation_manager is not None:
            self._activation_manager.stop()
            self.activate_button.setVisible(True)
            self.activate_button.setEnabled(True)
        self._set_state("stopped", "Parada pelo operador")
        self.history.append("<b>Nabi:</b> Solicitações pendentes foram invalidadas.")

    def reactivate(self) -> None:
        if self._activation_manager is not None and not self._activation_manager.active:
            self.activate_button.setVisible(True)
            self.activate_button.setEnabled(True)
            self._set_state("offline", "Autenticação necessária")
            return
        if not getattr(self._service, "available", True):
            return
        self._generation += 1
        self._busy = False
        self._set_controls(True)
        self._set_state("available", "Disponível")

    def _set_controls(self, enabled: bool) -> None:
        self.message.setEnabled(enabled)
        self.send.setEnabled(enabled)

    def _show_unavailable(self, message: str) -> None:
        self._set_controls(False)
        self._set_state("offline", "Em preparação")
        self.history.append(f"<b>Nabi:</b> {self._escape(message)}")

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
        if result.tool_name == "vendas.criar_rascunho":
            lines = [
                f"{item['quantity']}x {item['description']} — R$ {item['line_total']}"
                for item in payload.get("items", ())
            ]
            lines.extend((
                f"Total proposto: R$ {payload.get('total', '0.00')}",
                f"Pagamento proposto: {payload.get('payment_method', '-')}",
                "RASCUNHO — nenhuma venda foi registrada.",
            ))
            return "\n".join(lines)
        if result.tool_name == "diagnostico.executar_testes":
            state = "APROVADA" if payload.get("passed") else "FALHOU"
            return f"Suíte {payload.get('suite', '')}: {state}\n{payload.get('output', '')}"
        return "Resultado disponível, sem renderizador visual registrado."
