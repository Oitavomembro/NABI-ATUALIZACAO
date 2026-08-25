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
    QFileDialog,
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


class _NFeEntrySignals(QObject):
    completed = Signal(int, object, object)


class _NFeEntryWorker(QRunnable):
    def __init__(self, generation: int, service, path: str) -> None:
        super().__init__()
        self.generation = generation
        self.service = service
        self.path = path
        self.signals = _NFeEntrySignals()

    def run(self) -> None:
        draft = error = None
        try:
            draft = self.service.prepare_selected_file(self.path)
        except Exception as exc:
            error = exc
        self.signals.completed.emit(self.generation, draft, error)


class NabiAssistantPanel(QWidget):
    """Painel escrito opcional; não possui acesso direto a banco, GUI ou Fiscal."""

    def __init__(
        self, service, parent=None, *, thread_pool=None, activation_manager=None,
        draft_transfer=None,
        nfe_entry_service=None,
        product_search_opener=None,
        module_hub_opener=None,
        fiscal_configuration_opener=None,
        company_xml_import_opener=None,
        product_xml_import_opener=None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._pool = thread_pool or QThreadPool.globalInstance()
        self._generation = 0
        self._busy = False
        self._activation_manager = activation_manager
        self._draft_transfer = draft_transfer
        self._nfe_entry_service = nfe_entry_service
        self._product_search_opener = product_search_opener
        self._module_hub_opener = module_hub_opener
        self._fiscal_configuration_opener = fiscal_configuration_opener
        self._company_xml_import_opener = company_xml_import_opener
        self._product_xml_import_opener = product_xml_import_opener
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

        self.prepare_nfe_entry_button = QPushButton("REVISAR XML DE ENTRADA")
        self.prepare_nfe_entry_button.setVisible(nfe_entry_service is not None)
        self.prepare_nfe_entry_button.setToolTip(
            "Lê um XML local como dado não confiável; não importa nem acessa a SEFAZ."
        )
        root.addWidget(self.prepare_nfe_entry_button)

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
        self.prepare_nfe_entry_button.clicked.connect(self.prepare_nfe_entry)
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
        self.history.append(
            "<b>Nabi:</b> Sessão autenticada. Consultas e rascunhos seguros ativos."
        )
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
            if result.success and result.tool_name in {
                "vendas.criar_rascunho",
                "vendas.sugerir_rascunho_por_estoque",
                "compras.preparar_recebimento",
                "compras.preparar_entrada_nfe_exata",
                "clientes.preparar_cadastro",
                "clientes.preparar_recebimento",
                "compras.preparar_fornecedor",
                "compras.preparar_pedido",
                "produtos.preparar_cadastro",
                "estoque.preparar_movimento",
                "financeiro.preparar_titulo",
                "financeiro.preparar_baixa",
            }:
                self._service.invalidate_confirmations()
                self._pending_draft = (
                    result.payload["draft_id"], result.payload["fingerprint"],
                    result.payload.get("operation_kind", "SALE"),
                )
                self._confirmation_token = None
                self.review_draft_button.setVisible(True)
                self.confirm_draft_button.setVisible(False)
            if (
                result.success
                and result.tool_name == "interface.abrir_pesquisa_produtos"
            ):
                if self._product_search_opener is None:
                    self.history.append(
                        "<b>Nabi:</b> A pesquisa ampliada não está disponível nesta tela."
                    )
                else:
                    opened = bool(
                        self._product_search_opener(result.payload.get("term", ""))
                    )
                    if not opened:
                        self.history.append(
                            "<b>Nabi:</b> Saia do modo Produto avulso para pesquisar o catálogo."
                        )
            if result.success and result.tool_name == "interface.abrir_modulos":
                if self._module_hub_opener is None:
                    self.history.append(
                        "<b>Nabi:</b> A Central de Módulos não está disponível nesta tela."
                    )
                else:
                    self._module_hub_opener()
            if result.success and result.tool_name in {
                "interface.abrir_configuracao_fiscal",
                "interface.abrir_importacao_xml_empresa",
                "interface.abrir_importacao_xml_produtos",
            }:
                routes = {
                    "interface.abrir_configuracao_fiscal": (
                        self._fiscal_configuration_opener,
                        "A configuração Fiscal não está disponível nesta tela.",
                    ),
                    "interface.abrir_importacao_xml_empresa": (
                        self._company_xml_import_opener,
                        "A importação de dados empresariais não está disponível nesta tela.",
                    ),
                    "interface.abrir_importacao_xml_produtos": (
                        self._product_xml_import_opener,
                        "A importação de produtos não está disponível nesta tela.",
                    ),
                }
                opener, unavailable = routes[result.tool_name]
                if opener is None:
                    self.history.append(f"<b>Nabi:</b> {self._escape(unavailable)}")
                else:
                    opener()
        self.message.setFocus(Qt.FocusReason.OtherFocusReason)

    def review_draft(self) -> None:
        if self._pending_draft is None:
            return
        draft_id, fingerprint, operation_kind = self._pending_draft
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
        guidance = {
            "PURCHASE_RECEIPT": "Confira pedido, itens, custos, total e financeiro.",
            "NFE_ENTRY_IMPORT": (
                "Confira chave, fornecedor, produtos vinculados, quantidades e fatores de conversão."
            ),
            "CUSTOMER_CREATE": (
                "Confira ficha, nome, documentos, contato, endereço e limite de crédito."
            ),
            "CUSTOMER_RECEIPT": (
                "Confira ficha, cliente, saldo anterior, valor, saldo restante, forma e data."
            ),
            "SUPPLIER_CREATE": "Confira nome, razão social, documento e contato do fornecedor.",
            "PURCHASE_ORDER_CREATE": "Confira fornecedor, produtos, quantidades, custos e total.",
            "PRODUCT_CREATE": "Confira código, descrição, preços e estoque mínimo. O saldo inicial será zero.",
            "STOCK_RECEIVE": "Confira produto, saldo anterior, quantidade de entrada, novo saldo e motivo.",
            "STOCK_REMOVE": "Confira produto, saldo anterior, quantidade de saída, novo saldo e motivo.",
            "STOCK_ADJUST": "Confira produto, saldo anterior, novo saldo absoluto e motivo.",
        }.get(operation_kind, "Confira itens, total, cliente e pagamento.")
        if operation_kind.startswith("FINANCIAL_CREATE_"):
            guidance = "Confira tipo, parte, valor, emissão, vencimento e documento do título."
        elif operation_kind.startswith("FINANCIAL_SETTLE_"):
            guidance = "Confira título, saldo anterior, valor da baixa, saldo restante, forma e data."
        self.history.append(
            f"<b>Nabi:</b> {guidance} "
            "A confirmação é temporária e vale somente para este conteúdo."
        )

    def confirm_draft(self) -> None:
        if self._pending_draft is None or self._confirmation_token is None:
            return
        draft_id, fingerprint, operation_kind = self._pending_draft
        try:
            if operation_kind == "PURCHASE_RECEIPT":
                result, _authorization = self._service.confirm_and_execute_purchase(
                    self._confirmation_token, draft_id, fingerprint
                )
            elif operation_kind == "NFE_ENTRY_IMPORT":
                result, _authorization = self._service.confirm_and_execute_nfe_entry(
                    self._confirmation_token, draft_id, fingerprint
                )
            elif operation_kind == "CUSTOMER_CREATE":
                result, _authorization = self._service.confirm_and_execute_customer(
                    self._confirmation_token, draft_id, fingerprint
                )
            elif operation_kind == "CUSTOMER_RECEIPT":
                result, _authorization = self._service.confirm_and_execute_customer_receipt(
                    self._confirmation_token, draft_id, fingerprint
                )
            elif operation_kind == "SUPPLIER_CREATE":
                result, _authorization = self._service.confirm_and_execute_supplier(
                    self._confirmation_token, draft_id, fingerprint
                )
            elif operation_kind == "PURCHASE_ORDER_CREATE":
                result, _authorization = self._service.confirm_and_execute_purchase_order(
                    self._confirmation_token, draft_id, fingerprint
                )
            elif operation_kind in {
                "PRODUCT_CREATE", "STOCK_RECEIVE", "STOCK_REMOVE", "STOCK_ADJUST",
            }:
                result, _authorization = self._service.confirm_and_execute_product_stock(
                    self._confirmation_token, draft_id, fingerprint
                )
            elif operation_kind.startswith("FINANCIAL_"):
                result, _authorization = self._service.confirm_and_execute_financial(
                    self._confirmation_token, draft_id, fingerprint
                )
            else:
                draft, authorization = self._service.confirm_draft(
                    self._confirmation_token, draft_id, fingerprint
                )
                if self._draft_transfer is None:
                    raise RuntimeError("A transferência ao PDV não está configurada.")
                self._draft_transfer(draft, authorization)
        except Exception:
            self._set_state("blocked", "Confirmação recusada")
            self.history.append("<b>Nabi:</b> A confirmação expirou ou o rascunho mudou.")
            return
        self._confirmation_token = None
        self.confirm_draft_button.setVisible(False)
        self._pending_draft = None
        if operation_kind == "PURCHASE_RECEIPT":
            self._set_state("completed", "Recebimento registrado")
            self.history.append(
                "<b>Nabi:</b> Recebimento confirmado pelo serviço oficial. "
                f"Registro #{int(result.recebimento_id)}; pedido {result.status_pedido}."
            )
        elif operation_kind == "NFE_ENTRY_IMPORT":
            self._set_state("completed", "Entrada de NF-e registrada")
            self.history.append(
                "<b>Nabi:</b> Entrada local confirmada pelo importador oficial. "
                f"Importação #{int(result['importacao_id'])}; "
                f"{int(result['itens_vinculados'])} item(ns) vinculado(s). "
                "Nenhuma comunicação com a SEFAZ foi realizada."
            )
        elif operation_kind == "CUSTOMER_CREATE":
            self._set_state("completed", "Cliente cadastrado")
            self.history.append(
                "<b>Nabi:</b> Cadastro confirmado pelo serviço oficial. "
                f"Ficha {int(result.record_number)}; cliente #{int(result.customer_id)}."
            )
        elif operation_kind == "CUSTOMER_RECEIPT":
            self._set_state("completed", "Recebimento registrado")
            self.history.append(
                "<b>Nabi:</b> Recebimento confirmado pelo serviço oficial. "
                f"Movimento #{int(result.resource_id)}."
            )
        elif operation_kind == "SUPPLIER_CREATE":
            self._set_state("completed", "Fornecedor cadastrado")
            self.history.append(
                f"<b>Nabi:</b> Fornecedor #{int(result)} cadastrado pelo serviço oficial."
            )
        elif operation_kind == "PURCHASE_ORDER_CREATE":
            self._set_state("completed", "Pedido criado")
            self.history.append(
                f"<b>Nabi:</b> Pedido de compra #{int(result)} criado pelo serviço oficial."
            )
        elif operation_kind == "PRODUCT_CREATE":
            self._set_state("completed", "Produto cadastrado")
            self.history.append(
                f"<b>Nabi:</b> Produto #{int(result)} cadastrado com estoque inicial zero."
            )
        elif operation_kind in {"STOCK_RECEIVE", "STOCK_REMOVE", "STOCK_ADJUST"}:
            self._set_state("completed", "Estoque movimentado")
            self.history.append(
                "<b>Nabi:</b> Movimento de estoque confirmado pelo serviço oficial. "
                f"Movimento #{int(result['movement_id'])}; saldo {result['resulting_balance']}."
            )
        elif operation_kind.startswith("FINANCIAL_"):
            self._set_state("completed", "Financeiro registrado")
            payment = (
                f"; pagamento #{int(result.payment_id)}"
                if result.payment_id is not None else ""
            )
            self.history.append(
                "<b>Nabi:</b> Operação financeira confirmada pelo serviço oficial. "
                f"Título #{int(result.title_id)}{payment}; saldo R$ {result.open_amount}."
            )
        else:
            self._set_state("completed", "Rascunho carregado no PDV")
            self.history.append(
                "<b>Nabi:</b> Rascunho carregado no PDV. Nenhuma venda foi registrada; "
                "revise o carrinho e finalize pelo fluxo oficial de Pagamentos."
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

    def prepare_nfe_entry(self) -> None:
        if self._nfe_entry_service is None or self._busy:
            return
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, "Selecionar XML de entrada", "", "XML de NF-e (*.xml)"
        )
        if not path:
            return
        self._generation += 1
        generation = self._generation
        self._busy = True
        self._set_controls(False)
        self.prepare_nfe_entry_button.setEnabled(False)
        self._set_state("thinking", "Analisando XML local…")
        worker = _NFeEntryWorker(generation, self._nfe_entry_service, path)
        self._workers.add(worker)
        worker.signals.completed.connect(
            lambda received, draft, error, current=worker: self._nfe_entry_complete(
                received, draft, error, current
            )
        )
        self._pool.start(worker)

    def _nfe_entry_complete(self, generation, draft, error, worker=None) -> None:
        if worker is not None:
            self._workers.discard(worker)
        if generation != self._generation:
            return
        self._busy = False
        self._set_controls(True)
        self.prepare_nfe_entry_button.setEnabled(True)
        if draft is None:
            self._set_state("blocked", "XML não preparado")
            self.history.append(
                f"<b>Nabi:</b> {self._escape(str(error or 'Falha segura ao analisar o XML.'))}"
            )
            return
        self._set_state("warning", "XML aguardando revisão manual")
        lines = [
            f"NF-e nº {draft.number or '-'} — fornecedor {draft.supplier_name or '-'}",
            f"Chave informada: {draft.access_key or '-'}",
            f"Evidência cStat no arquivo: {draft.protocol_status_evidence or '-'}",
            f"Destinatário no XML: {getattr(draft, 'recipient_name', '') or '-'} — "
            f"{getattr(draft, 'recipient_document', '') or '-'}",
        ]
        lines.extend(
            f"Item {item.index + 1}: {item.quantity} {item.unit} — {item.description} "
            f"— correspondência {item.match_status} ({item.match_criterion})"
            for item in draft.items
        )
        lines.append("SOMENTE REVISÃO — nenhum produto, estoque ou financeiro foi alterado.")
        self.history.append(f"<pre>{self._escape(chr(10).join(lines))}</pre>")

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
        if self._nfe_entry_service is not None:
            self.prepare_nfe_entry_button.setEnabled(enabled)

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
        if result.tool_name == "clientes.consultar_credito":
            return (
                f"Cliente #{payload['customer_id']} — limite R$ {payload['credit_limit']} — "
                f"saldo devedor R$ {payload['debt_balance']} — "
                f"disponível R$ {payload['available_credit']}"
            )
        if result.tool_name == "estoque.listar_baixo":
            items = payload.get("items", ())
            if not items:
                return "Nenhum produto com estoque baixo."
            return "\n".join(
                f"{item['code']} — {item['description']} — atual {item['current_quantity']} "
                f"— mínimo {item['minimum_quantity']}"
                for item in items
            )
        if result.tool_name == "vendas.listar_dia":
            items = payload.get("items", ())
            if not items:
                return f"Nenhuma venda em {payload['day']}."
            return "\n".join(
                f"Venda #{item['sale_id']} — {item['occurred_at']} — "
                f"R$ {item['total']} — {item['status']}"
                for item in items
            )
        if result.tool_name == "recebimentos.listar_dia":
            items = payload.get("items", ())
            if not items:
                return f"Nenhum recebimento em {payload['day']}."
            return "\n".join(
                f"{item['paid_at']} — {item['customer_name']} — "
                f"{item['payment_method']} — R$ {item['amount']}"
                for item in items
            )
        if result.tool_name == "cobrancas.listar_vencidas":
            items = payload.get("items", ())
            if not items:
                return "Nenhuma cobrança vencida."
            return "\n".join(
                f"{item['customer_name']} — parcela {item['installment_number']} — "
                f"vence {item['due_date']} — R$ {item['open_amount']}"
                for item in items
            )
        if result.tool_name == "financeiro.resumo":
            return "\n".join((
                f"Período: {payload['start_date']} a {payload['end_date']}",
                f"A receber aberto: R$ {payload['receivable_open']}",
                f"A receber vencido: R$ {payload['receivable_overdue']}",
                f"A pagar aberto: R$ {payload['payable_open']}",
                f"A pagar hoje: R$ {payload['payable_due_today']}",
                f"Recebido: R$ {payload['received_in_period']}",
                f"Pago: R$ {payload['paid_in_period']}",
            ))
        if result.tool_name == "financeiro.fluxo_caixa":
            items = payload.get("items", ())
            if not items:
                return "Nenhum movimento financeiro no período."
            return "\n".join(
                f"{item['occurred_at']} — {item['direction']} — "
                f"{item['origin']} — R$ {item['amount']}"
                for item in items
            )
        if result.tool_name in {"financeiro.listar_receber", "financeiro.listar_pagar"}:
            items = payload.get("items", ())
            if not items:
                return "Nenhum título encontrado para a situação solicitada."
            receiving = result.tool_name.endswith("receber")
            id_field = "customer_id" if receiving else "beneficiary_id"
            name_field = "customer_name" if receiving else "beneficiary_name"
            label = "Cliente" if receiving else "Beneficiário"
            return "\n".join(
                f"Título #{item['title_id']} — {label} #{item[id_field] or '-'} "
                f"{item[name_field] or '-'} — vence {item['due_date']} — "
                f"R$ {item['open_amount']} — {item['status']}"
                for item in items
            )
        if result.tool_name == "compras.listar_fornecedores":
            items = payload.get("items", ())
            if not items:
                return "Nenhum fornecedor encontrado."
            return "\n".join(
                f"Fornecedor #{item['supplier_id']} — {item['name']} — "
                f"{'ativo' if item['active'] else 'inativo'}"
                for item in items
            )
        if result.tool_name == "compras.listar_pedidos":
            items = payload.get("items", ())
            if not items:
                return "Nenhum pedido de compra encontrado."
            return "\n".join(
                f"Pedido #{item['order_id']} — {item['supplier_name']} — "
                f"{item['status']} — R$ {item['total']} — pendente {item['pending_quantity']}"
                for item in items
            )
        if result.tool_name == "compras.consultar_pedido":
            lines = [
                f"Pedido #{payload['order_id']} — {payload['supplier_name']} — {payload['status']}"
            ]
            lines.extend(
                f"{item['code']} — {item['description']} — pedido {item['ordered_quantity']} "
                f"— recebido {item['received_quantity']} — pendente {item['pending_quantity']} "
                f"— custo R$ {item['unit_cost']}"
                for item in payload.get("items", ())
            )
            return "\n".join(lines)
        if result.tool_name == "contexto.explicar_configuracao":
            return "\n".join((
                str(payload["title"]),
                str(payload["guidance"]),
                str(payload["limits"]),
            ))
        if result.tool_name == "compras.preparar_fornecedor":
            return "\n".join((
                f"Fornecedor: {payload['name']}",
                f"Razão social: {payload.get('legal_name') or '-'}",
                f"Documento: {payload.get('document') or '-'}",
                f"Contato: {payload.get('phone') or '-'} | {payload.get('email') or '-'}",
                "RASCUNHO — nenhum fornecedor foi cadastrado.",
            ))
        if result.tool_name == "compras.preparar_pedido":
            lines = [
                f"{item['quantity']}x {item['code']} — {item['description']} — "
                f"custo R$ {item['unit_cost']} — R$ {item['line_total']}"
                for item in payload.get("items", ())
            ]
            lines.extend((
                f"Fornecedor: {payload['supplier_name']}",
                f"Total proposto: R$ {payload['total']}",
                "RASCUNHO — nenhum pedido foi criado.",
            ))
            return "\n".join(lines)
        if result.tool_name == "produtos.preparar_cadastro":
            return "\n".join((
                f"Produto: {payload.get('code') or '-'} — {payload['description']}",
                f"Venda R$ {payload['sale_price']} — custo R$ {payload['cost_price']}",
                f"Estoque inicial: {payload['current_stock']} — mínimo {payload['minimum_stock']}",
                "RASCUNHO — nenhum produto foi cadastrado.",
            ))
        if result.tool_name == "estoque.preparar_movimento":
            return "\n".join((
                f"Produto #{payload['product_id']} — {payload['product_code']} — {payload['product_description']}",
                f"Saldo anterior: {payload['previous_balance']} — novo saldo: {payload['new_balance']}",
                f"Motivo: {payload['reason']}",
                "RASCUNHO — nenhum estoque foi movimentado.",
            ))
        if result.tool_name == "financeiro.preparar_titulo":
            return "\n".join((
                f"Título a {payload['title_type'].lower()}: R$ {payload['amount']}",
                f"Parte: #{payload.get('party_id') or '-'} — {payload.get('party_name') or '-'}",
                f"Vencimento: {payload['due_date']} — documento {payload.get('document') or '-'}",
                "RASCUNHO — nenhum título foi criado.",
            ))
        if result.tool_name == "financeiro.preparar_baixa":
            return "\n".join((
                f"Título #{payload['title_id']} a {payload['title_type'].lower()}",
                f"Saldo anterior: R$ {payload['previous_open_amount']}",
                f"Baixa: R$ {payload['amount']} — saldo esperado R$ {payload['expected_open_amount']}",
                f"Forma: {payload['payment_method']} — data {payload['payment_date']}",
                "RASCUNHO — nenhuma baixa foi registrada.",
            ))
        if result.tool_name == "relatorios.consultar_indicadores":
            return "\n".join((
                f"Período: {payload['start_date']} a {payload['end_date']}",
                f"Vendas: R$ {payload['sales_total']}",
                f"A receber: R$ {payload['receivable_open']}",
                f"A pagar: R$ {payload['payable_open']}",
                f"Produtos com estoque baixo: {payload['low_stock']}",
                f"Clientes ativos: {payload['active_customers']}",
            ))
        if result.tool_name == "caixa.consultar_atual":
            if not payload["is_open"]:
                return "O caixa deste terminal está fechado."
            return "\n".join((
                f"Caixa aberto — sessão #{payload['session_id']} — {payload['opened_at']}",
                f"Saldo inicial: R$ {payload['opening_balance']}",
                f"Dinheiro esperado: R$ {payload['expected_cash']}",
                f"Vendas: dinheiro R$ {payload['cash_sales']} — PIX R$ {payload['pix_sales']} "
                f"— cartões R$ {payload['card_sales']} — outros R$ {payload['other_sales']}",
                f"Recebimentos em dinheiro: R$ {payload['cash_receipts']}",
                f"Suprimentos: R$ {payload['supplies']} — sangrias R$ {payload['withdrawals']}",
            ))
        if result.tool_name == "interface.abrir_pesquisa_produtos":
            term = payload.get("term", "")
            return (
                f"Pesquisa ampliada solicitada para: {term}"
                if term else "Pesquisa ampliada solicitada."
            )
        if result.tool_name == "interface.abrir_modulos":
            return "Abertura da Central de Módulos solicitada."
        if result.tool_name in {
            "vendas.criar_rascunho",
            "vendas.sugerir_rascunho_por_estoque",
        }:
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
        if result.tool_name == "compras.preparar_recebimento":
            lines = [
                f"{item['quantity']}x {item['description']} — custo R$ {item['unit_cost']} "
                f"— R$ {item['line_total']}"
                for item in payload.get("items", ())
            ]
            lines.extend((
                f"Pedido: {payload.get('order_id', '-')}",
                f"Fornecedor: {payload.get('supplier_name', '-')}",
                f"Total da entrada: R$ {payload.get('total', '0.00')}",
                "EFEITOS: estoque e custo; financeiro somente quando indicado.",
                "RASCUNHO — nenhum recebimento foi registrado.",
            ))
            return "\n".join(lines)
        if result.tool_name == "compras.preparar_entrada_nfe_exata":
            lines = [
                f"Produto #{item['product_id']} — {item['description']} — "
                f"XML {item['xml_quantity']} × fator {item['conversion_factor']} "
                f"= estoque {item['stock_quantity']} — custo R$ {item['unit_cost']}"
                for item in payload.get("items", ())
            ]
            lines.extend((
                f"NF-e: {payload.get('number', '-')} — {payload.get('supplier_name', '-')}",
                f"Destinatário no XML: {payload.get('recipient_name', '-')} — "
                f"{payload.get('recipient_document', '-')}",
                f"Total informado no XML: R$ {payload.get('document_total', '0.00')}",
                "EFEITOS: vínculo de fornecedor, estoque e financeiro pelo importador oficial.",
                "RASCUNHO — nenhuma entrada foi registrada e nenhuma consulta à SEFAZ ocorreu.",
            ))
            return "\n".join(lines)
        if result.tool_name == "clientes.preparar_cadastro":
            return "\n".join((
                f"Ficha: {payload.get('record_number', '-')}",
                f"Cliente: {payload.get('name', '-')}",
                f"CPF: {payload.get('cpf') or '-'} — RG: {payload.get('rg') or '-'}",
                f"Telefone: {payload.get('phone') or '-'}",
                f"Endereço: {payload.get('address') or '-'}",
                f"Limite: R$ {payload.get('credit_limit', '0.00')}",
                "RASCUNHO — nenhum cliente foi cadastrado.",
            ))
        if result.tool_name == "clientes.preparar_recebimento":
            return "\n".join((
                f"Ficha: {payload.get('record_number', '-')} — {payload.get('customer_name', '-')}",
                f"Saldo antes: R$ {payload.get('previous_balance', '0.00')}",
                f"Valor recebido: R$ {payload.get('amount', '0.00')}",
                f"Saldo restante: R$ {payload.get('expected_balance', '0.00')}",
                f"Forma: {payload.get('payment_method', '-')} — Data: {payload.get('payment_date', '-')}",
                "RASCUNHO — nenhum pagamento foi registrado.",
            ))
        if result.tool_name == "diagnostico.executar_testes":
            state = "APROVADA" if payload.get("passed") else "FALHOU"
            return f"Suíte {payload.get('suite', '')}: {state}\n{payload.get('output', '')}"
        return "Resultado disponível, sem renderizador visual registrado."
