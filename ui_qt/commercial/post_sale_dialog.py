from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout

from commercial.application.dto import CheckoutResult
from commercial.domain.money import MoneyCodec
from .customer_dialog import STYLE
from .pdv_view_model import PDVViewModel


class PostSaleDialog(QDialog):
    """Oferece saídas pós-venda sem executar impressão automaticamente."""

    def __init__(self, view_model: PDVViewModel, result: CheckoutResult, parent=None) -> None:
        super().__init__(parent)
        if not result.committed or result.receipt is None:
            raise ValueError("O pós-venda exige uma venda confirmada.")
        self.view_model = view_model
        self.sale_result = result
        self.setWindowTitle("Venda finalizada")
        self.setModal(True)
        self.resize(460, 260)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        title = QLabel("✓ Venda finalizada")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #00ff88;")
        root.addWidget(title)
        total = QLabel(f"Total: R$ {MoneyCodec.format_br(result.total)}")
        total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total.setStyleSheet("font-size: 17px; font-weight: 700;")
        root.addWidget(total)
        root.addWidget(QLabel("Escolha uma ação para o comprovante. A venda já foi confirmada."))
        actions = QHBoxLayout()
        self.finish_button = QPushButton("Finalizar")
        self.print_button = QPushButton("Imprimir cupom 80 mm")
        self.pdf_button = QPushButton("Gerar e abrir PDF")
        actions.addWidget(self.finish_button)
        actions.addWidget(self.print_button)
        actions.addWidget(self.pdf_button)
        root.addLayout(actions)
        self.finish_button.clicked.connect(self.accept)
        self.print_button.clicked.connect(self._print)
        self.pdf_button.clicked.connect(self._pdf)
        self.finish_button.setFocus(Qt.FocusReason.OtherFocusReason)

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
