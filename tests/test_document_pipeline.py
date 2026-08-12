from pathlib import Path
from unittest.mock import Mock

import pytest

from services.pdf_document_service import PDFDocumentService
from services.printing_service import PrintingService


class FakeCanvas:
    def __init__(self) -> None:
        self.save_calls = 0

    def save(self) -> None:
        self.save_calls += 1


def make_pdf_service(tmp_path: Path, registrar=None) -> PDFDocumentService:
    return PDFDocumentService(
        connection_factory=lambda: None,
        config_getter=lambda _key: "",
        pdf_dir=tmp_path,
        document_registrar=registrar,
    )


def test_finalize_document_saves_and_registers_once(tmp_path: Path) -> None:
    registrar = Mock()
    service = make_pdf_service(tmp_path, registrar)
    canvas = FakeCanvas()
    path = tmp_path / "documento.pdf"

    result = service._finalize_document(
        canvas,
        path,
        destination=None,
        document_id=17,
        category="recibo",
    )

    assert result == str(path.resolve())
    assert canvas.save_calls == 1
    registrar.assert_called_once_with(17, "recibo", str(path.resolve()), "17")


def test_finalize_document_does_not_register_explicit_destination(tmp_path: Path) -> None:
    registrar = Mock()
    service = make_pdf_service(tmp_path, registrar)
    canvas = FakeCanvas()
    path = tmp_path / "segunda_via.pdf"

    service._finalize_document(
        canvas,
        path,
        destination=path,
        document_id=17,
        category="recibo",
    )

    assert canvas.save_calls == 1
    registrar.assert_not_called()


def test_document_path_uses_monthly_folder_only_without_destination(tmp_path: Path) -> None:
    service = make_pdf_service(tmp_path)
    explicit = tmp_path / "manual.pdf"

    assert service._document_path(explicit, "ignorado.pdf") == explicit
    automatic = service._document_path(None, "automatico.pdf")
    assert automatic.name == "automatico.pdf"
    assert automatic.parent.parent.parent == tmp_path


def test_print_text_dispatches_once_to_raw_for_official_80mm() -> None:
    service = PrintingService()
    service.print_raw_text = Mock(return_value="Termica")
    service.print_a4_text = Mock(return_value="A4")

    result = service.print_text(
        "cupom", output_format="Cupom 80 mm", printer="Termica", title="Cupom"
    )

    assert result == "Termica"
    service.print_raw_text.assert_called_once_with("cupom", "Termica", "Cupom")
    service.print_a4_text.assert_not_called()



def test_legacy_58mm_persisted_format_is_normalized_to_official_80mm() -> None:
    service = PrintingService({"formato_impressao_recibo": "Cupom 58 mm"}.get)

    assert service.output_format("recibo") == "Cupom 80 mm"


def test_printing_80mm_dispatches_only_to_raw_backend() -> None:
    service = PrintingService()
    service.print_raw_text = Mock(return_value="Termica")
    service.print_a4_text = Mock(side_effect=AssertionError("Cupom 80 mm não deve usar backend A4"))

    result = service.print_text(
        "cupom", output_format="Cupom 80 mm", printer="Termica", title="Cupom"
    )

    assert result == "Termica"
    service.print_raw_text.assert_called_once_with("cupom", "Termica", "Cupom")
    service.print_a4_text.assert_not_called()


def test_physical_dispatch_rejects_legacy_58mm_choice() -> None:
    service = PrintingService()

    with pytest.raises(ValueError, match="Formato de impressão não suportado"):
        service.print_text("cupom", output_format="Cupom 58 mm")

def test_print_text_dispatches_once_to_a4() -> None:
    service = PrintingService()
    service.print_raw_text = Mock(return_value="Termica")
    service.print_a4_text = Mock(return_value="Laser")

    result = service.print_text(
        "relatorio", output_format="A4", printer="Laser", title="Relatório"
    )

    assert result == "Laser"
    service.print_a4_text.assert_called_once_with("relatorio", "Laser", "Relatório")
    service.print_raw_text.assert_not_called()


def test_print_text_rejects_non_physical_format() -> None:
    service = PrintingService()
    with pytest.raises(ValueError, match="Formato de impressão não suportado"):
        service.print_text("arquivo", output_format="PDF virtual")


def test_render_config_centralizes_pdf_typography(tmp_path: Path) -> None:
    values = {
        "impressao_margem_mm": "5",
        "impressao_fonte": "Courier",
        "impressao_fonte_tamanho": "6",
        "impressao_espacamento": "1.5",
    }
    service = PDFDocumentService(
        connection_factory=lambda: None,
        config_getter=lambda key: values.get(key, ""),
        pdf_dir=tmp_path,
    )

    margin, font, size, step = service._render_config(2.0, minimum_size=7)

    assert margin == 10.0
    assert font == "Courier"
    assert size == 7
    assert step == 10.5


def test_printer_resolution_validates_once() -> None:
    class FakeWin32Print:
        PRINTER_ENUM_LOCAL = 1
        PRINTER_ENUM_CONNECTIONS = 2

        def __init__(self) -> None:
            self.enum_calls = 0

        def GetDefaultPrinter(self):
            return "Laser"

        def EnumPrinters(self, _flags):
            self.enum_calls += 1
            return [(None, None, "Laser", None)]

    backend = FakeWin32Print()
    service = PrintingService()

    assert service._resolve_printer_name("Padrão do Sistema", backend) == "Laser"
    assert backend.enum_calls == 1

def test_legacy_58mm_pdf_model_is_normalized_to_official_80mm(tmp_path: Path) -> None:
    service = PDFDocumentService(
        connection_factory=lambda: None,
        config_getter=lambda key: "Térmica 58 mm econômica" if key == "modelo_recibo" else "",
        pdf_dir=tmp_path,
    )

    assert service.document_model("recibo") == "Térmica 80 mm"


def test_internal_58mm_canvas_compatibility_is_preserved(tmp_path: Path, monkeypatch) -> None:
    calls = {}

    class FakeReportCanvas:
        def __init__(self, path, pagesize):
            calls["path"] = path
            calls["pagesize"] = pagesize

    import reportlab.pdfgen.canvas as reportlab_canvas
    monkeypatch.setattr(reportlab_canvas, "Canvas", FakeReportCanvas)

    _canvas, page_size, _mm = PDFDocumentService._create_canvas(
        tmp_path / "historico_58mm.pdf", "Térmica 58 mm econômica", estimated_height_mm=120
    )

    assert round(page_size[0], 5) == round(58 * _mm, 5)
    assert calls["pagesize"] == page_size


def test_payment_pdf_uses_reconciled_balances_without_recalculating(tmp_path: Path) -> None:
    service = make_pdf_service(tmp_path)
    service._payment_details = Mock(return_value=(
        1, "Cliente", "C1", "F1", "Pagamento", 12, "07/08/2026", "PIX", "Caixa",
    ))
    service._sales_with_installments = Mock(return_value={})
    service.document_model = Mock(return_value="A4")
    service._document_path = Mock(return_value=tmp_path / "recibo.pdf")

    drawn = []

    class Renderer:
        def __init__(self):
            self.y = 100
        def draw(self, text="", **_kwargs):
            drawn.append(str(text))
            self.y -= 10
            return self.y

    class Canvas:
        def line(self, *_args):
            return None
        def save(self):
            return None

    service._create_canvas = Mock(return_value=(Canvas(), (595, 842), 1.0))
    service._render_config = Mock(return_value=(10, "Helvetica", 10, 13.5))
    service._draw_header = Mock(return_value=700)
    service._line_renderer = Mock(return_value=Renderer())
    service._draw_qr_if_enabled = Mock(side_effect=lambda _canvas, _width, y, *_args: y)
    service.config_bool = Mock(return_value=False)
    service._finalize_document = Mock(return_value=str(tmp_path / "recibo.pdf"))

    service.generate_customer_payment(
        20,
        allocations=[],
        balance_before="312.00",
        balance_after="300.00",
    )

    assert service._line_renderer.call_args.kwargs["step"] == 13.5
    assert "Saldo antes: R$ 312.00" in drawn
    assert "Saldo depois: R$ 300.00" in drawn
    assert "Saldo antes: R$ 1011.00" not in drawn


def test_payment_pdf_does_not_invent_balances_when_reconciled_values_are_missing(tmp_path: Path) -> None:
    source = (Path(__file__).resolve().parents[1] / "services/pdf_document_service.py").read_text(encoding="utf-8")
    method = source.split("def generate_customer_payment", 1)[1].split("def generate_closing", 1)[0]

    assert "balance_after +" not in method
    assert "current_balance or 0" not in method


def test_payment_coupon_service_does_not_recalculate_customer_balance() -> None:
    source = (Path(__file__).resolve().parents[1] / "services/receipt_service.py").read_text(encoding="utf-8")
    method = source.split("def build_payment_text", 1)[1]

    assert "balance_after + float(value" not in method
    assert "current_balance or 0" not in method


def test_printing_service_keeps_physical_80mm_separate_from_pdf_generation() -> None:
    source = (Path(__file__).resolve().parents[1] / "services/printing_service.py").read_text(encoding="utf-8")
    assert "PDFDocumentService" not in source
    assert "generate_" not in source


def test_pdf_profile_uses_58mm_only_for_explicit_legacy_models() -> None:
    from services.document_rendering import profile_for_pdf_model

    assert profile_for_pdf_model("Térmica 58 mm econômica").paper_width_mm == 58.0
    assert profile_for_pdf_model("58 mm").paper_width_mm == 58.0
    assert profile_for_pdf_model("modelo experimental 58 futuro").paper_width_mm == 80.0
    assert profile_for_pdf_model("Térmica 80 mm").paper_width_mm == 80.0
