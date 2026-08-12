import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
GLOBAL = (ROOT / "core" / "global_search.py").read_text(encoding="utf-8")


class SearchEntryGlobalIntegrationTests(unittest.TestCase):
    def test_global_palette_uses_shared_attachment(self):
        self.assertIn("SearchEntryBehavior.attach(", GLOBAL)
        self.assertIn("self.entry, on_enter=self.activate_selected", GLOBAL)
        self.assertNotIn('self.entry.bind("<Return>"', GLOBAL)

    def test_product_and_client_searches_use_shared_attachment(self):
        self.assertIn("self.entry_busca_produto, on_enter=self.carregar_produtos", LEGACY)
        self.assertIn("self.entry_busca_cliente, on_enter=self.filtrar_tabela_clientes", LEGACY)

    def test_pdv_enter_independente_usa_controlador_unico_sem_binding_concorrente(self):
        self.assertIn("PDVEnterController(", LEGACY)
        self.assertIn("SearchEntryBehavior.attach_focus(self.entry_item_venda)", LEGACY)
        self.assertGreaterEqual(LEGACY.count("self.entry_cliente_venda, on_enter=self.confirmar_sugestao_cliente"), 2)
        self.assertNotIn('win.bind("<Return>", self._enter_contexto_pdv', LEGACY)
        self.assertNotIn('self.entry_item_venda.bind("<Return>", self.confirmar_sugestao_produto)', LEGACY)
        self.assertNotIn('self.entry_cliente_venda.bind("<Return>", self.confirmar_sugestao_cliente)', LEGACY)

    def test_reports_search_uses_shared_attachment(self):
        self.assertIn("self.rel_busca, on_enter=self.gerar_relatorio_ui", LEGACY)

    def test_help_search_uses_shared_attachment(self):
        self.assertIn("SearchEntryBehavior.attach(busca, on_enter=pesquisar)", LEGACY)
        self.assertNotIn('busca.bind("<Return>"', LEGACY)


if __name__ == "__main__":
    unittest.main()
