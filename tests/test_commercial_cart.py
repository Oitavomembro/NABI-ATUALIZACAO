from decimal import Decimal
import unittest

from commercial.domain.cart import Cart, CartItem


class CommercialCartTests(unittest.TestCase):
    def test_item_cadastrado_e_avulso(self):
        registered = CartItem("Produto", Decimal("2"), Decimal("10.00"), product_id=7)
        loose = CartItem("Serviço avulso", Decimal("1"), Decimal("5.50"))
        self.assertFalse(registered.is_loose)
        self.assertTrue(loose.is_loose)
        self.assertEqual(registered.subtotal, Decimal("20.00"))

    def test_adicionar_alterar_quantidade_preco_remover_e_limpar(self):
        cart = Cart()
        first = cart.add(CartItem("A", Decimal("1"), Decimal("10.00"), product_id=1))
        second = cart.add(CartItem("B", Decimal("2"), Decimal("5.00")))
        self.assertEqual(cart.total, Decimal("20.00"))

        updated = cart.change_quantity(second.line_id, Decimal("3"))
        self.assertEqual(updated.quantity, Decimal("3"))
        with self.assertRaises(PermissionError):
            cart.change_unit_price(first.line_id, Decimal("12.00"))
        cart.change_unit_price(first.line_id, Decimal("12.00"), allowed=True)
        self.assertEqual(cart.total, Decimal("27.00"))

        self.assertEqual(cart.remove(second.line_id).description, "B")
        self.assertEqual(cart.total, Decimal("12.00"))
        cart.clear()
        self.assertTrue(cart.is_empty)
        self.assertEqual(cart.total, Decimal("0.00"))

    def test_desconto_percentual_preserva_regra_comercial_do_pdv(self):
        item = CartItem(
            "Com desconto",
            Decimal("3"),
            Decimal("10.00"),
            discount_percent=Decimal("10"),
        )
        self.assertEqual(item.net_unit_price, Decimal("9.00"))
        self.assertEqual(item.subtotal, Decimal("27.00"))

    def test_edicao_atomica_preserva_preco_sem_permissao(self):
        cart = Cart([CartItem("Produto", 1, "10.00", product_id=7)])
        original = cart.items[0]
        with self.assertRaises(PermissionError):
            cart.edit_item(
                original.line_id,
                quantity=2,
                unit_price="12.00",
                discount_percent=10,
                allow_price_change=False,
            )
        self.assertEqual(cart.items[0], original)

        updated = cart.edit_item(
            original.line_id,
            quantity=2,
            unit_price="10.00",
            discount_percent=10,
            allow_price_change=False,
        )
        self.assertEqual(updated.quantity, Decimal("2"))
        self.assertEqual(updated.discount_percent, Decimal("10.00"))
        self.assertEqual(updated.subtotal, Decimal("18.00"))

    def test_validacoes_de_item_e_exposicao_imutavel(self):
        with self.assertRaises(ValueError):
            CartItem("", Decimal("1"), Decimal("1"))
        with self.assertRaises(ValueError):
            CartItem("A", Decimal("0"), Decimal("1"))
        with self.assertRaises(ValueError):
            CartItem("A", Decimal("1"), Decimal("-0.01"))
        with self.assertRaises(ValueError):
            CartItem("A", Decimal("1"), Decimal("1"), product_id=0)
        cart = Cart([CartItem("A", Decimal("1"), Decimal("1"))])
        self.assertIsInstance(cart.items, tuple)


if __name__ == "__main__":
    unittest.main()
