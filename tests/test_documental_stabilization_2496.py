from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from services.printing_service import PrintingService
from services.receipt_service import ReceiptService


ROOT = Path(__file__).resolve().parents[1]
LEGACY_SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
PDF_SOURCE = (ROOT / "services/pdf_document_service.py").read_text(encoding="utf-8")
PRINT_SOURCE = (ROOT / "services/printing_service.py").read_text(encoding="utf-8")


def test_impressao_80mm_nao_cria_pdf() -> None:
    service = PrintingService()
    service.print_raw_text = Mock(return_value="Termica")
    service.print_a4_text = Mock(side_effect=AssertionError("backend A4 indevido"))

    assert service.print_text("cupom", output_format="Cupom 80 mm") == "Termica"
    service.print_raw_text.assert_called_once()
    assert "PDFDocumentService" not in PRINT_SOURCE


def test_pdf_nao_dispara_impressao_fisica() -> None:
    assert "PrintingService" not in PDF_SOURCE
    assert ".print_text(" not in PDF_SOURCE
    assert ".print_raw_text(" not in PDF_SOURCE


def test_reimpressao_usa_preview_unificado_sem_dialogo_antigo() -> None:
    block = LEGACY_SOURCE.split("def reimprimir_movimentacao", 1)[1].split("def disparar_edicao_dash", 1)[0]
    assert "self.janela_preview_documento(" in block
    assert "askyesnocancel" not in block
    assert "gerar_pdf_venda" in block
    assert "pdf_callback=lambda destino" in block


def test_segunda_via_preview_tem_acoes_padrao() -> None:
    block = LEGACY_SOURCE.split("def janela_preview_documento", 1)[1].split("def janela_recibo_pagamento_cliente", 1)[0]
    assert "Pré-visualização" in block
    assert "Imprimir cupom 80 mm" in block
    assert "Salvar PDF (opcional)" in block
    assert 'text="Fechar"' in block


def test_corte_escpos_acontece_uma_vez_no_payload() -> None:
    values = {
        "impressao_corte_automatico": "1",
        "impressao_linhas_antes_corte": "3",
        "impressao_tipo_corte": "PARCIAL",
    }
    service = PrintingService(values.get)
    payload = service._raw_payload("ABC")

    assert payload.endswith((b"\r\n" * 3) + b"\x1d\x56\x01")
    assert payload.count(b"\x1d\x56\x01") == 1


class _PaymentDb:
    def fetch_one(self, query, params=()):
        if "WHERE m.id=? AND m.tipo='PAGAMENTO'" in query:
            return (1, "CLIENTE", "C1", "F1", "Recebimento", 20, "07/08/2026", "PIX", "OPERADOR")
        return None

    def fetch_all(self, query, params=()):
        return []


def test_recibo_pagamento_usa_saldos_reconciliados() -> None:
    service = ReceiptService(_PaymentDb(), config_getter=lambda _key: "")
    text = service.build_payment_text(
        10,
        allocations=[],
        balance_before="220.00",
        balance_after="200.00",
    )
    assert "VALOR RECEBIDO: R$ 20.00" in text
    assert "Saldo antes: R$ 220.00" in text
    assert "Saldo depois: R$ 200.00" in text


class _InstallmentDb:
    def fetch_one(self, query, params=()):
        if "FROM clientes WHERE id=?" in query:
            return ("CLIENTE", "C1", "F1", "75999999999", "RUA A")
        if "FROM movimentacoes WHERE id=?" in query:
            return ("CREDIARIO", 2, 100, "PARCIAL")
        return None

    def fetch_all(self, query, params=()):
        if "FROM parcelas WHERE movimentacao_id=?" in query:
            return [(1, 50, "2026-09-07", "PENDENTE"), (2, 50, "2026-10-07", "PENDENTE")]
        return []


def test_venda_com_parcelas_preserva_detalhamento_documental() -> None:
    service = ReceiptService(_InstallmentDb(), config_getter=lambda _key: "")
    text = service.build_sale_text(
        1,
        [{"item": "PRODUTO", "qtd": 1, "preco": 100, "subtotal": 100}],
        100,
        "VENDA",
        sale_id=77,
    )
    assert "Compra a prazo: 2 parcela(s)" in text
    assert "01/02" in text
    assert "02/02" in text
    assert "Saldo financiado: R$ 100.00" in text


def test_documento_saldo_historico_usa_distribuicao_recebida() -> None:
    service = ReceiptService(_PaymentDb(), config_getter=lambda _key: "")
    text = service.build_payment_text(
        10,
        allocations=[{
            "tipo": "SALDO_LEGADO",
            "valor_aplicado": 20,
            "saldo_antes": 220,
            "saldo_depois": 200,
        }],
        balance_before=220,
        balance_after=200,
    )
    assert "Saldo histórico migrado" in text
    assert "Aplicado agora: R$ 20.00" in text
    assert "Saldo: R$ 220.00 -> R$ 200.00" in text
