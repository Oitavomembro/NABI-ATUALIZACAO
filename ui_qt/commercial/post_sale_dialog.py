from __future__ import annotations

from PySide6.QtCore import QUrl, Qt, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout

from commercial.application.dto import CheckoutResult
from commercial.domain.money import MoneyCodec
from .pdv_view_model import PDVViewModel


class PostSaleDialog(QDialog):
    """Oferece saídas pós-venda sem executar impressão automaticamente."""

    def __init__(
        self, view_model: PDVViewModel, result: CheckoutResult, parent=None, *,
        fiscal_info=None, fiscal_sale_service=None,
    ) -> None:
        super().__init__(parent)
        if not result.committed or result.receipt is None:
            raise ValueError("O pós-venda exige uma venda confirmada.")
        self.view_model = view_model
        self.sale_result = result
        self.fiscal_info = dict(fiscal_info or {})
        self.fiscal_sale_service = fiscal_sale_service
        self.setWindowTitle(
            "NF-e 55 — processamento fiscal"
            if self.fiscal_info else "Venda comercial não fiscal finalizada"
        )
        self.setModal(True)
        self.resize(460, 260)
        root = QVBoxLayout(self)
        title = QLabel(
            "NF-e 55 preparada com segurança"
            if self.fiscal_info else "✓ Venda comercial finalizada"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #00ff88;")
        root.addWidget(title)
        self.fiscal_status = QLabel()
        self.fiscal_status.setWordWrap(True)
        self.fiscal_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.fiscal_status)
        self._render_fiscal_status(self.fiscal_info)
        total = QLabel(f"Total: R$ {MoneyCodec.format_br(result.total)}")
        total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total.setStyleSheet("font-size: 17px; font-weight: 700;")
        root.addWidget(total)
        root.addWidget(QLabel(
            "Acompanhe abaixo o retorno da SEFAZ. Não repita a venda se o status "
            "estiver pendente ou desconhecido."
            if self.fiscal_info else
            "Escolha uma ação para o comprovante comercial. Para emitir NF-e 55, "
            "use o fluxo fiscal separado."
        ))
        actions = QHBoxLayout()
        self.finish_button = QPushButton(
            "Fechar acompanhamento" if self.fiscal_info else "Fechar venda não fiscal"
        )
        self.print_button = QPushButton("Imprimir comprovante comercial")
        self.pdf_button = QPushButton("Gerar comprovante em PDF")
        self.danfe_button = QPushButton("Gerar e abrir DANFE")
        self.danfe_button.setVisible(bool(self.fiscal_info))
        self.danfe_button.setEnabled(
            str(self.fiscal_info.get("status") or "").upper() == "AUTORIZADO"
        )
        actions.addWidget(self.finish_button)
        actions.addWidget(self.print_button)
        actions.addWidget(self.pdf_button)
        actions.addWidget(self.danfe_button)
        root.addLayout(actions)
        self.finish_button.clicked.connect(self.accept)
        self.print_button.clicked.connect(self._print)
        self.pdf_button.clicked.connect(self._pdf)
        self.danfe_button.clicked.connect(self._danfe)
        self.finish_button.setFocus(Qt.FocusReason.OtherFocusReason)
        self._status_timer = None
        if self.fiscal_info and self.fiscal_sale_service is not None:
            self._status_timer = QTimer(self)
            self._status_timer.setInterval(1000)
            self._status_timer.timeout.connect(self._refresh_fiscal_status)
            self._status_timer.start()

    def _render_fiscal_status(self, info) -> None:
        if not info:
            self.fiscal_status.setText(
                "NÃO FISCAL — esta operação não gerou NF-e, não recebeu chave/protocolo "
                "e não foi enviada à SEFAZ."
            )
            self.fiscal_status.setStyleSheet(
                "background:#3b2f05;color:#ffd866;padding:12px;font-size:15px;font-weight:800;"
            )
            return
        status = str(info.get("status") or "ENFILEIRADO").upper()
        key = str(info.get("access_key") or "")
        protocol = str(info.get("protocol") or "")
        message = str(info.get("last_message") or info.get("last_error") or "")
        lines = [f"NF-e 55 — {status}", f"Chave: {key or 'aguardando geração'}"]
        if protocol:
            lines.append(f"Protocolo SEFAZ: {protocol}")
        elif status in {"PENDENTE", "ENFILEIRADO", "PROCESSANDO"}:
            lines.append("Aguardando processamento/retorno da SEFAZ…")
        elif status == "RESPOSTA_DESCONHECIDA":
            lines.append("Resposta desconhecida: consultar a SEFAZ; não retransmitir.")
        if message:
            lines.append(message)
        self.fiscal_status.setText("\n".join(lines))
        color = "#0f5132" if status == "AUTORIZADO" else "#3b2f05"
        foreground = "#75ffb0" if status == "AUTORIZADO" else "#ffd866"
        self.fiscal_status.setStyleSheet(
            f"background:{color};color:{foreground};padding:12px;font-size:15px;font-weight:800;"
        )
        if hasattr(self, "danfe_button"):
            self.danfe_button.setEnabled(status == "AUTORIZADO")

    def _refresh_fiscal_status(self) -> None:
        sale_id = int(self.fiscal_info.get("sale_id") or 0)
        rows = self.fiscal_sale_service.list_sales()
        current = next((row for row in rows if int(row.get("sale_id") or 0) == sale_id), None)
        if current is None:
            return
        self.fiscal_info.update(current)
        self._render_fiscal_status(self.fiscal_info)
        if str(current.get("status") or "").upper() in {
            "AUTORIZADO", "FALHA", "CANCELADO", "CANCELADO_FISCAL",
        }:
            self._status_timer.stop()

    def _print(self) -> None:
        try:
            printer = self.view_model.application.print_receipt(self.sale_result)
        except Exception as error:
            QMessageBox.critical(self, "Impressão", str(error))
            self.print_button.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        QMessageBox.information(self, "Cupom enviado", f"Cupom enviado para: {printer}")
        self.accept()

    def _pdf(self) -> None:
        try:
            self.view_model.application.generate_receipt_pdf(self.sale_result)
        except Exception as error:
            QMessageBox.critical(self, "PDF", str(error))
            self.pdf_button.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self.accept()

    def _danfe(self) -> None:
        if self.fiscal_sale_service is None:
            QMessageBox.warning(self, "DANFE", "O serviço fiscal não está disponível.")
            return
        try:
            path = self.fiscal_sale_service.generate_danfe_for_sale(
                int(self.fiscal_info.get("sale_id") or 0)
            )
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                raise RuntimeError(f"DANFE gerado em {path}, mas não foi possível abri-lo.")
        except Exception as error:
            QMessageBox.warning(self, "DANFE não disponível", str(error))
            self.danfe_button.setFocus(Qt.FocusReason.OtherFocusReason)
