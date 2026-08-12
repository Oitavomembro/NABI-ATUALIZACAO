from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import Mock

from controllers.legacy_backend_adapter import LegacyBackendAdapterMixin, LegacyBackendContext
from services.printing_service import PrintingService
from validators.receipt_validator import ReceiptValidator


ROOT = Path(__file__).resolve().parents[1]


class AdapterHarness(LegacyBackendAdapterMixin):
    def __init__(self):
        self.backend_context = LegacyBackendContext(
            database_manager=Mock(),
            connect=Mock(),
            get_config=lambda key: "Termica" if key == "impressora_recibo" else "",
            pdf_dir=".",
            product_application_service=Mock(),
            report_service=Mock(),
        )
        self.printing = Mock()
        self.printing.print_text.return_value = "Termica"
        self.receipts = Mock()
        self.receipts.build_sale_text.return_value = "CUPOM"

    def _servico_impressao(self):
        return self.printing

    def _servico_comprovantes(self):
        return self.receipts


def _legacy_method(name: str) -> str:
    source = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "FicharioMoveisApp")
    method = next(node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.get_source_segment(source, method) or ""


def test_sale_print_uses_application_adapter_and_official_80mm_once():
    adapter = AdapterHarness()
    result = adapter.imprimir_cupom_venda_80mm(
        1,
        [{"item": "Produto", "qtd": 1, "preco": 10, "subtotal": 10}],
        10,
        "RECIBO",
        99,
    )
    assert result == "Termica"
    adapter.receipts.build_sale_text.assert_called_once()
    adapter.printing.print_text.assert_called_once_with(
        "CUPOM",
        output_format=PrintingService.OFFICIAL_THERMAL_FORMAT,
        printer="Termica",
        title="Comprovante de venda",
    )


def test_sale_print_adapter_does_not_generate_pdf():
    source = (ROOT / "controllers" / "legacy_backend_adapter.py").read_text(encoding="utf-8")
    method = source.split("def imprimir_cupom_venda_80mm", 1)[1].split("\n    def ", 1)[0]
    assert "gerar_pdf" not in method
    assert "generate_" not in method


def test_historical_purchase_and_receipt_are_sale_aliases():
    items = [{"item": "Produto", "qtd": 1, "preco": 10, "subtotal": 10}]
    assert ReceiptValidator.sale_header("COMPRA", items, 10)[0] == "VENDA"
    assert ReceiptValidator.sale_header("RECIBO", items, 10)[0] == "VENDA"


def test_reprint_keeps_unified_preview_and_optional_pdf():
    source = _legacy_method("reimprimir_movimentacao")
    assert 'tipo=="COMPRA"' in source
    assert "self.janela_preview_documento(" in source
    assert "pdf_callback=lambda destino:" in source
    assert "janela_acoes_pdf" not in source


def test_pdv_has_main_owner_and_restores_focus_after_close():
    opening = _legacy_method("abrir_pdv_independente")
    closing = _legacy_method("_fechar_pdv")
    assert "win = ctk.CTkToplevel(self)" in opening
    assert "win.transient(self)" not in opening
    assert "command=self._minimizar_pdv" in opening
    assert "win.grab_release()" in closing
    assert closing.index("win.destroy()") < closing.index("self.after_idle(self._garantir_janela_principal_visivel)")
    assert "tk.Tk(" not in opening + closing
