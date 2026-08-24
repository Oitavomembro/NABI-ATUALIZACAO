import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ItemAvulsoIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")

    def test_configuracao_expoe_modo_comercial_e_fiscal(self):
        self.assertIn("COMERCIAL — sem emissão fiscal", self.source)
        self.assertIn("FISCAL — com recursos fiscais", self.source)
        self.assertIn('salvar_config("modo_operacao"', self.source)

    def test_troca_de_modo_exige_senha_gerencial_antes_de_salvar(self):
        inicio = self.source.index("def salvar_configuracoes_gerais(self):")
        fim = self.source.index("def abrir_restauracao_fabrica(self):", inicio)
        fluxo = self.source[inicio:fim]
        self.assertIn("self._confirmar_senha_gerencial(", fluxo)
        self.assertIn("self.security.confirm_manager_password(senha)", self.source)
        self.assertLess(
            fluxo.index("self._confirmar_senha_gerencial("),
            fluxo.index('salvar_config("modo_operacao"'),
        )

    def test_habilitar_emissao_oficial_tambem_exige_senha_mestra(self):
        self.assertIn('title="Alterar emissão fiscal oficial"', self.source)
        self.assertIn('enabled.set(bool(config.get("enabled")))', self.source)

    def test_pdv_expoe_item_avulso_sem_estoque(self):
        self.assertIn("Produto avulso — não cadastra e não movimenta estoque", self.source)
        self.assertIn("def alternar_item_avulso_pdv", self.source)
        self.assertIn('"item_avulso": item_avulso', self.source)
        self.assertIn('"produto_id": None if item_avulso else produto_id', self.source)

    def test_modo_fiscal_bloqueia_item_avulso(self):
        self.assertIn("O modo fiscal não permite item avulso", self.source)
        self.assertIn("No modo fiscal, selecione um produto cadastrado com dados fiscais", self.source)

    def test_modo_fiscal_exige_configuracao_antes_de_salvar_e_vender(self):
        save_start = self.source.index("def salvar_configuracoes_gerais(self):")
        save_end = self.source.index("def abrir_restauracao_fabrica(self):", save_start)
        save_flow = self.source[save_start:save_end]
        self.assertIn("self.fiscal_service.validate_ready(", save_flow)
        self.assertIn("self.abrir_configuracao_fiscal(force_open=True)", save_flow)
        sale_start = self.source.index("def finalizar_venda(self, tipo_comprovante):")
        sale_end = self.source.index("def tela_clientes(self, parent):", sale_start)
        sale_flow = self.source[sale_start:sale_end]
        self.assertIn('fiscal_required = (obter_config("modo_operacao")', sale_flow)
        self.assertIn("Venda fiscal bloqueada", sale_flow)
        self.assertLess(
            sale_flow.index("self.fiscal_service.validate_ready("),
            sale_flow.index("self.solicitar_pagamentos_pdv("),
        )


if __name__ == "__main__":
    unittest.main()
