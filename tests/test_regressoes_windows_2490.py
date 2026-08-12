from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEGACY = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
OPENER = (ROOT / "services" / "windows_file_opener.py").read_text(encoding="utf-8")


class WindowsObservedRegressionTests(unittest.TestCase):
    def test_favorito_usa_repositorio_disponivel(self):
        bloco = LEGACY.split("def alternar_favorito_cliente", 1)[1].split("def abrir_cadastro_cliente", 1)[0]
        self.assertIn("CLIENTE_REPOSITORY.toggle_favorite", bloco)
        self.assertNotIn("self.cliente_repository.toggle_favorite", bloco)

    def test_historico_exibe_saldo_devedor_em_destaque(self):
        bloco = LEGACY.split("def abrir_historico_cliente(self, cliente_id)", 1)[1].split("def exportar_clientes_csv", 1)[0]
        self.assertIn("SALDO DEVEDOR: R$", bloco)

    def test_clientes_reabrem_sem_scroll_horizontal_estrutural(self):
        bloco = LEGACY.split("def tela_clientes(self, parent)", 1)[1].split("def carregar_clientes", 1)[0]
        self.assertNotIn("BidirectionalScrollableFrame", bloco)
        self.assertIn("LayoutManager.apply_client_treeview", bloco)

    def test_pdv_exige_confirmacao_antes_de_estoque_negativo(self):
        self.assertIn("def _confirmar_estoque_pdv_ao_selecionar", LEGACY)
        self.assertIn("def _confirmar_estoque_pdv_para_quantidade", LEGACY)
        self.assertIn('"estoque_override"', LEGACY)

    def test_abertura_pdf_nao_destaca_powershell_do_desktop_interativo(self):
        bloco = OPENER.split("def open", 1)[1]
        self.assertNotIn('getattr(subprocess, "DETACHED_PROCESS"', bloco)


if __name__ == "__main__":
    unittest.main()
