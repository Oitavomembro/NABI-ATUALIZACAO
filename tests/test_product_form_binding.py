import unittest

from services.product_application_service import ProductFormState
from services.product_form_binding import ProductFormBinding, ProductFormControls


class FakeTextControl:
    def __init__(self, value=""):
        self.value = str(value)
        self.state = "normal"

    def get(self):
        return self.value

    def delete(self, _start, _end):
        self.value = ""

    def insert(self, _index, value):
        self.value = str(value)

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]


class FakeChoiceControl:
    def __init__(self, value=""):
        self.value = str(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = str(value)


class FakeBooleanControl:
    def __init__(self, value=False):
        self.value = bool(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = bool(value)


class ProductFormBindingTests(unittest.TestCase):
    def make_binding(self):
        controls = ProductFormControls(
            codigo=FakeTextControl(), nome=FakeTextControl(), preco_venda=FakeTextControl(),
            categoria=FakeChoiceControl(), tipo_produto=FakeChoiceControl(), marca=FakeChoiceControl(),
            fornecedor=FakeChoiceControl(), unidade=FakeChoiceControl(), unidade_compra=FakeChoiceControl(),
            fator_conversao=FakeTextControl(), preco_custo=FakeTextControl(),
            despesas_percentual=FakeTextControl(), margem_lucro=FakeTextControl(),
            codigo_barras=FakeTextControl(), estoque_atual=FakeTextControl(),
            estoque_minimo=FakeTextControl(), permite_estoque_negativo=FakeBooleanControl(),
        )
        return ProductFormBinding(controls), controls

    def test_apply_writes_complete_state_without_tkinter_dependency(self):
        binding, controls = self.make_binding()
        state = ProductFormState(
            codigo="P9", nome="Mesa", preco_venda="120,50", categoria="Móveis",
            tipo_produto="MERCADORIA", marca="Nabi", fornecedor="Fornecedor A",
            unidade="UN", unidade_compra="CX", fator_conversao="12",
            preco_custo="80", despesas_percentual="5", margem_lucro="30",
            codigo_barras="789", estoque_atual="10", estoque_minimo="2",
            permite_estoque_negativo=True,
        )
        binding.apply(state, codigo_editavel=False)
        self.assertEqual(controls.codigo.get(), "P9")
        self.assertEqual(controls.codigo.state, "disabled")
        self.assertEqual(controls.nome.get(), "Mesa")
        self.assertEqual(controls.categoria.get(), "Móveis")
        self.assertEqual(controls.unidade_compra.get(), "CX")
        self.assertTrue(controls.permite_estoque_negativo.get())

    def test_capture_reads_complete_form_state(self):
        binding, controls = self.make_binding()
        controls.codigo.value = "P10"
        controls.nome.value = "Cadeira"
        controls.preco_venda.value = "99,90"
        controls.categoria.value = "Móveis"
        controls.tipo_produto.value = "SERVIÇO"
        controls.marca.value = "Nabi"
        controls.fornecedor.value = "Fornecedor B"
        controls.unidade.value = "UN"
        controls.unidade_compra.value = "CX"
        controls.fator_conversao.value = "6"
        controls.preco_custo.value = "60"
        controls.despesas_percentual.value = "4"
        controls.margem_lucro.value = "25"
        controls.codigo_barras.value = "123"
        controls.estoque_atual.value = "7"
        controls.estoque_minimo.value = "1"
        controls.permite_estoque_negativo.value = True

        state = binding.capture()
        self.assertEqual(state.codigo, "P10")
        self.assertEqual(state.nome, "Cadeira")
        self.assertEqual(state.preco_venda, "99,90")
        self.assertEqual(state.tipo_produto, "SERVIÇO")
        self.assertEqual(state.fator_conversao, "6")
        self.assertTrue(state.permite_estoque_negativo)

    def test_apply_can_keep_code_editable_for_existing_product(self):
        binding, controls = self.make_binding()
        binding.apply(ProductFormState(codigo="P1"), codigo_editavel=True)
        self.assertEqual(controls.codigo.state, "normal")


if __name__ == "__main__":
    unittest.main()
