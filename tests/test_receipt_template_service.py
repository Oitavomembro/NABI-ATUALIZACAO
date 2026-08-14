from services.receipt_template_service import ReceiptTemplateService


SAMPLE = "LOJA TESTE\nCOMPROVANTE DE VENDA\n==========================================\n1x Produto\n------------------------------------------\nTOTAL: R$ 10,00"


def test_gallery_has_twenty_named_offline_presets():
    names = ReceiptTemplateService.names()
    assert len(names) == 20
    assert len(set(names)) == 20
    assert "Nabi exclusivo" in names


def test_every_preset_renders_with_safe_80mm_width_and_keeps_content():
    outputs = set()
    for name in ReceiptTemplateService.names():
        rendered = ReceiptTemplateService.render(SAMPLE, name)
        assert "Produto" in rendered
        assert "TOTAL: R$ 10,00" in rendered
        assert all(len(line) <= 42 for line in rendered.splitlines())
        outputs.add(rendered)
    assert len(outputs) == 20


def test_unknown_preset_falls_back_to_classic():
    assert ReceiptTemplateService.render(SAMPLE, "desconhecido") == ReceiptTemplateService.render(SAMPLE, "Clássico")
