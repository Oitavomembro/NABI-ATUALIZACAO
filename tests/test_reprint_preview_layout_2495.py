from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'nabicode_legacy.py').read_text(encoding='utf-8')


class ReprintPreviewLayout2495Tests(unittest.TestCase):
    def test_cliente_actions_use_compact_spacing(self):
        self.assertIn('font=ctk.CTkFont(size=11, weight="bold")', SOURCE)
        self.assertIn('fill="x", padx=2)', SOURCE)

    def test_reprint_uses_unified_preview(self):
        block = SOURCE.split('def reimprimir_movimentacao', 1)[1].split('def disparar_edicao_dash', 1)[0]
        self.assertIn('self.janela_preview_documento(', block)
        self.assertNotIn('self.janela_acoes_pdf(caminho', block)

    def test_unified_preview_has_explicit_print_pdf_close_actions(self):
        block = SOURCE.split('def janela_preview_documento', 1)[1].split('def janela_recibo_pagamento_cliente', 1)[0]
        self.assertIn('Imprimir cupom 80 mm', block)
        self.assertIn('Salvar PDF (opcional)', block)
        self.assertIn('text="Fechar"', block)
        self.assertIn('self.imprimir_texto_windows(', block)

    def test_reprint_pdf_is_generated_only_on_explicit_save(self):
        block = SOURCE.split('def reimprimir_movimentacao', 1)[1].split('def disparar_edicao_dash', 1)[0]
        self.assertIn('pdf_callback=lambda destino: self.gerar_pdf_venda(', block)
        self.assertNotIn('caminho=self.gerar_pdf_venda', block)


if __name__ == '__main__':
    unittest.main()
