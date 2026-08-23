from __future__ import annotations

import unittest
from types import SimpleNamespace

from assistant_nabi import create_purchase_assistant_components


class PurchaseCompositionTests(unittest.TestCase):
    def test_usa_mesma_instancia_oficial_para_leitura_e_execucao(self):
        purchase = SimpleNamespace(repository=SimpleNamespace())
        drafts, executor = create_purchase_assistant_components(
            SimpleNamespace(purchase_service=purchase)
        )
        self.assertIs(drafts._gateway, executor)
        self.assertIs(executor._service, purchase)

    def test_falha_fechada_sem_servico_oficial(self):
        with self.assertRaisesRegex(RuntimeError, "não está configurado"):
            create_purchase_assistant_components(SimpleNamespace())


if __name__ == "__main__": unittest.main()
