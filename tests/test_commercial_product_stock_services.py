from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from commercial.application.action_dto import ActionContext, ActionOrigin, ActionSensitivity
from commercial.application.product_dto import (
    ProductCreateCommand, ProductUpdateCommand, StockAdjustmentCommand,
    StockMovementCommand,
)
from commercial.application.stock_action_service import StockActionService
from commercial.infrastructure.runtime import create_commercial_container
from commercial.infrastructure.stock_gateway import NabiCodeProductStockGateway
from database import DatabaseManager
from database.schema_initializer import initialize_database


class FailingStockEvents:
    def stock_event(self, event):
        raise RuntimeError("consumer unavailable")


class DuplicateBarcodeService:
    def listar(self, term):
        return [
            {"id": 1, "codigo": "A", "codigo_barras": term, "nome": "A", "preco_venda": 1},
            {"id": 2, "codigo": "B", "codigo_barras": term, "nome": "B", "preco_venda": 1},
        ]


class CommercialProductStockServicesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db = DatabaseManager(root / "nabicode.db")
        initialize_database(
            db_name=str(root / "nabicode.db"), backup_dir=str(root / "backups"),
            pdf_dir=str(root / "pdfs"), schema_version=20,
            last_database_update={"executada": False, "de": 0, "para": 20, "backup": ""},
            network_mode=False, network_role="local", connect=self.db.connect,
            read_existing_version=lambda: 0, backup_before_update=lambda *_: "",
        )
        self.container = create_commercial_container(self.db)
        self.products = self.container.product_application
        self.actions = self.container.stock_actions
        self.context = ActionContext("estoque-teste", ActionOrigin.UI)

    def tearDown(self):
        self.temp.cleanup()

    def _create(self, code="P100", description="PRODUTO TESTE", barcode="789100", stock="10", minimum="3", allow_negative=False):
        return self.products.create_product(ProductCreateCommand(
            code, description, Decimal("25.00"), barcode=barcode,
            cost_price=Decimal("10.00"), current_stock=Decimal(stock),
            minimum_stock=Decimal(minimum), allow_negative_stock=allow_negative,
        ))

    def test_criar_editar_buscar_codigo_descricao_barcode_e_id(self):
        created = self._create()
        self.assertGreater(created.product_id, 0)
        self.assertEqual(self.products.get_product(created.product_id).product_id, created.product_id)
        self.assertEqual(self.products.search_products("PRODUTO")[0].product_id, created.product_id)
        self.assertEqual(self.products.search_products("P100")[0].product_id, created.product_id)
        self.assertEqual(self.products.get_product_by_barcode("789100").product_id, created.product_id)
        self.assertEqual(self.container.query.product_details(created.product_id).product_id, created.product_id)
        self.assertEqual(self.container.query.product_stock(created.product_id).current_quantity, Decimal("10.0000"))

        updated = self.products.update_product(ProductUpdateCommand(
            "P101", "PRODUTO EDITADO", Decimal("30.00"), barcode="789101",
            cost_price=Decimal("12.00"), current_stock=Decimal("10"),
            minimum_stock=Decimal("4"), product_id=created.product_id,
        ))
        self.assertEqual((updated.code, updated.description, updated.sale_price),
                         ("P101", "PRODUTO EDITADO", Decimal("30.00")))
        self.assertIsNone(self.products.get_product_by_barcode("789100"))
        self.assertEqual(self.products.get_product_by_barcode("789101").product_id, created.product_id)

    def test_barcode_duplicado_nao_escolhe_produto_arbitrario(self):
        gateway = NabiCodeProductStockGateway.__new__(NabiCodeProductStockGateway)
        gateway.products = DuplicateBarcodeService()
        with self.assertRaisesRegex(ValueError, "duplicado"):
            gateway.get_by_barcode("789")

    def test_entrada_saida_ajuste_historico_minimo_e_rollback(self):
        product = self._create(stock="10", minimum="3")
        stock = self.products.product_stock(product.product_id)
        self.assertEqual((stock.current_quantity, stock.status), (Decimal("10.0000"), "OK"))

        received = self.actions.receive_stock(
            StockMovementCommand(product.product_id, Decimal("5"), "Compra manual"),
            context=self.context, confirmed=True,
        )
        removed = self.actions.remove_stock(
            StockMovementCommand(product.product_id, Decimal("4"), "Avaria"),
            context=self.context, confirmed=True,
        )
        adjusted = self.actions.adjust_stock(
            StockAdjustmentCommand(product.product_id, Decimal("3"), "Contagem física"),
            context=self.context, confirmed=True,
        )
        self.assertEqual(received.resulting_balance, Decimal("15.0000"))
        self.assertEqual(removed.resulting_balance, Decimal("11.0000"))
        self.assertEqual(adjusted.resulting_balance, Decimal("3.0000"))
        self.assertEqual(len(self.products.product_movements(product.product_id)), 3)
        self.assertEqual([x.product_id for x in self.products.low_stock_products()], [product.product_id])

        rejected = self.actions.remove_stock(
            StockMovementCommand(product.product_id, Decimal("4"), "Saída excessiva"),
            context=self.context, confirmed=True,
        )
        self.assertFalse(rejected.committed)
        self.assertEqual(self.products.product_stock(product.product_id).current_quantity, Decimal("3.0000"))
        self.assertEqual(len(self.products.product_movements(product.product_id)), 3)

    def test_estoque_negativo_segue_politica_do_produto(self):
        blocked = self._create(code="B", barcode="111", stock="1", minimum="0")
        result = self.actions.remove_stock(
            StockMovementCommand(blocked.product_id, Decimal("2"), "Teste"),
            context=self.context, confirmed=True,
        )
        self.assertFalse(result.committed)

        allowed = self._create(code="A", barcode="222", stock="1", minimum="0", allow_negative=True)
        result = self.actions.remove_stock(
            StockMovementCommand(allowed.product_id, Decimal("2"), "Teste autorizado"),
            context=self.context, confirmed=True,
        )
        self.assertTrue(result.committed)
        self.assertEqual(result.resulting_balance, Decimal("-1.0000"))
        self.assertEqual(self.products.product_stock(allowed.product_id).status, "NEGATIVO")

    def test_confirmacao_evento_pos_commit_e_produto_acima_minimo(self):
        product = self._create(stock="10", minimum="3")
        command = StockMovementCommand(product.product_id, Decimal("1"), "Entrada")
        pending = self.actions.receive_stock(command, context=self.context, confirmed=False)
        self.assertFalse(pending.executed)
        self.assertEqual(pending.sensitivity, ActionSensitivity.SENSITIVE)
        self.assertEqual(self.products.low_stock_products(), ())

        service = StockActionService(self.actions._gateway, FailingStockEvents())
        result = service.receive_stock(command, context=self.context, confirmed=True)
        self.assertTrue(result.committed)
        self.assertTrue(result.secondary_effect_failed)
        self.assertEqual(self.products.product_stock(product.product_id).current_quantity, Decimal("11.0000"))
        self.assertIn("não repita", result.message)

    def test_consulta_de_maior_estoque_filtra_e_ordena_produtos_vendaveis(self):
        lower = self._create(code="LOW", description="MENOR", barcode="301", stock="4")
        higher = self._create(code="HIGH", description="MAIOR", barcode="302", stock="40")
        result = self.container.query.high_stock_products(limit=1)
        self.assertEqual([item.product_id for item in result], [higher.product_id])
        self.assertNotEqual(result[0].product_id, lower.product_id)

    def test_operacoes_concorrentes_nao_perdem_atualizacao(self):
        product = self._create(stock="10", minimum="0")
        barrier = threading.Barrier(3)
        results = []

        def receive():
            barrier.wait()
            results.append(self.actions.receive_stock(
                StockMovementCommand(product.product_id, Decimal("5"), "Concorrência entrada"),
                context=self.context, confirmed=True,
            ))

        def remove():
            barrier.wait()
            results.append(self.actions.remove_stock(
                StockMovementCommand(product.product_id, Decimal("3"), "Concorrência saída"),
                context=self.context, confirmed=True,
            ))

        threads = [threading.Thread(target=receive), threading.Thread(target=remove)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(5)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.committed for result in results))
        self.assertEqual(self.products.product_stock(product.product_id).current_quantity, Decimal("12.0000"))
        self.assertEqual(len(self.products.product_movements(product.product_id)), 2)


if __name__ == "__main__":
    unittest.main()
