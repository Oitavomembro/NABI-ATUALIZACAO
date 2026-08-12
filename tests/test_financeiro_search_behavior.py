from pathlib import Path
import unittest


class FinanceiroSearchBehaviorTests(unittest.TestCase):
    def test_filtros_financeiros_usam_comportamento_centralizado(self):
        source = Path('nabicode_legacy.py').read_text(encoding='utf-8')
        self.assertIn('SearchEntryBehavior.attach(self.fin_inicio, on_enter=self.carregar_financeiro)', source)
        self.assertIn('SearchEntryBehavior.attach(self.fin_fim, on_enter=self.carregar_financeiro)', source)


if __name__ == '__main__':
    unittest.main()
