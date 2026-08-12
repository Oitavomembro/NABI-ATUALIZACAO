from decimal import Decimal
import unittest

from controllers.customer_registration_controller import CustomerRegistrationController
from controllers.product_registration_controller import ProductRegistrationController
from repositories import ClienteRepository, CustomersRepository, ProdutoRepository, ProductsRepository
from validators import AuxiliaryRegistrationValidator, CustomerValidator, ProductValidator


class CadastroModularization2495Tests(unittest.TestCase):
    def test_repository_aliases_do_not_duplicate_implementation(self):
        self.assertIs(CustomersRepository, ClienteRepository)
        self.assertIs(ProductsRepository, ProdutoRepository)

    def test_customer_validator_normalizes_and_parses(self):
        self.assertEqual(CustomerValidator.normalize_name("  Maria   Silva "), "Maria Silva")
        self.assertEqual(CustomerValidator.parse_record_number(" 42 "), 42)
        self.assertEqual(CustomerValidator.parse_credit_limit("R$ 1.234,56"), 1234.56)

    def test_product_validator_centralizes_product_rules(self):
        self.assertEqual(ProductValidator.normalize_type("serviço"), "SERVICO")
        self.assertEqual(ProductValidator.normalize_filter_type("todos"), "TODOS")
        ProductValidator.validate_values(
            sale_price=Decimal("10"), conversion_factor=Decimal("1"), minimum_stock=0
        )
        with self.assertRaises(ValueError):
            ProductValidator.validate_values(sale_price=Decimal("-0.01"))

    def test_auxiliary_validator_normalizes_unit(self):
        self.assertEqual(AuxiliaryRegistrationValidator.normalize_type(" fornecedor "), "fornecedor")
        self.assertEqual(AuxiliaryRegistrationValidator.normalize_name(" un ", unit=True), "UN")

    def test_customer_controller_only_delegates(self):
        class Service:
            def __init__(self): self.received = None
            def criar(self, **data): self.received = data; return 17
        service = Service()
        controller = CustomerRegistrationController(service)  # type: ignore[arg-type]
        self.assertEqual(controller.create(nome="Ana"), 17)
        self.assertEqual(service.received, {"nome": "Ana"})

    def test_product_controller_builds_command_and_delegates(self):
        class Service:
            def criar_comando(self, data): return ("command", data)
            def salvar(self, command): return ("saved", command)
        service = Service()
        controller = ProductRegistrationController(service)  # type: ignore[arg-type]
        marker = object()
        self.assertEqual(controller.save(marker), ("saved", ("command", marker)))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
