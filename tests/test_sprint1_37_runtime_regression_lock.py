from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEGACY = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
SEARCH = (ROOT / "services" / "search_entry_behavior.py").read_text(encoding="utf-8")


class RuntimeRegressionLockTests(unittest.TestCase):
    def test_decimal_storage_is_imported_when_product_popup_uses_it(self):
        self.assertIn("from repositories.decimal_storage import DecimalStorage, DecimalStorageError", LEGACY)
        popup = LEGACY.split("def exibir_sugestoes_produto", 1)[1].split("def _cancelar_fechamento_sugestoes_produto", 1)[0]
        self.assertIn("DecimalStorage.to_decimal", popup)

    def test_search_behavior_has_native_tk_fallback(self):
        self.assertIn("entry.configure(fg=cls.TEXT_COLOR, insertbackground=cls.TEXT_COLOR)", SEARCH)
        self.assertIn("except Exception", SEARCH)

    def test_finalization_never_emits_automatically(self):
        block = LEGACY.split("def finalizar_venda", 1)[1].split("def tela_clientes", 1)[0]
        self.assertIn("janela_venda_finalizada", block)
        self.assertNotIn("resultado_emissao = self.emitir_venda_conforme_perfil", block)


if __name__ == "__main__":
    unittest.main()
