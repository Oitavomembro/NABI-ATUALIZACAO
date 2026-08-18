import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")

class EtapaComercialFiscalCompletaTests(unittest.TestCase):
    def test_modo_comercial_oculta_acoes_fiscais(self):
        self.assertIn("if modo_fiscal_ativo():", SOURCE)
        self.assertIn("comandos_fiscais", SOURCE)
        self.assertIn("Os recursos fiscais estão ocultos", SOURCE)

    def test_finalizacao_tem_impressao_e_fluxo_teclado(self):
        self.assertIn("def janela_pos_venda_comprovante", SOURCE)
        self.assertIn("_abrir_arquivo_sistema(caminho_pdf)", SOURCE)
        self.assertIn("def avancar", SOURCE)
        self.assertIn("<Shift-Return>", SOURCE)
        self.assertNotIn('janela.bind("<Return>", concluir)', SOURCE)

    def test_versao_nao_fica_congelada_em_teste(self):
        test_source = (ROOT / "tests/test_global_search_integration.py").read_text(encoding="utf-8")
        self.assertNotIn('"2.4.32"', test_source)

    def test_configuracao_fiscal_expoe_regimes_e_modelos_sem_campo_livre(self):
        self.assertIn("TAX_REGIME_LABELS", SOURCE)
        self.assertIn("MODEL_LABELS", SOURCE)
        self.assertIn('enabled_models', SOURCE)
        self.assertIn('default_model', SOURCE)
        self.assertNotIn('fields["tax_regime"] = field(', SOURCE)

    def test_certificado_a1_tem_selecao_e_validacao_guiadas(self):
        self.assertIn("1. Selecionar arquivo A1", SOURCE)
        self.assertIn("2. Verificar certificado", SOURCE)
        self.assertIn("self.fiscal_service.inspect_certificate(path, secret)", SOURCE)
        self.assertIn("A senha é usada somente para validar e nunca é salva", SOURCE)

if __name__ == "__main__":
    unittest.main()
