import sqlite3
import unittest
from decimal import Decimal

from services.product_application_service import ProductApplicationService, ProductFormData, ProductFormState, ProductSaveCommand


class FakeProdutoService:
    def __init__(self, existing=None, rows=None):
        self.existing = existing
        self.rows = rows or []
        self.saved = []
        self.list_calls = []
        self.duplicate_data = None
        self.history = []
        self.next_status = None
        self.action_calls = []
        self.next_code = "P100"
        self.search_calls = []
        self.categories = []
        self.auxiliaries = {"marca": [], "fornecedor": [], "unidade": []}

    def listar_categorias_ativas(self):
        self.action_calls.append(("listar_categorias", None))
        return list(self.categories)

    def listar_auxiliares(self, tipo):
        self.action_calls.append(("listar_auxiliares", tipo))
        return list(self.auxiliaries[tipo])

    def criar_categoria(self, nome):
        self.action_calls.append(("criar_categoria", nome))
        return 71

    def criar_auxiliar(self, tipo, nome, **extras):
        self.action_calls.append(("criar_auxiliar", tipo, nome, extras))
        return 72

    def buscar(self, produto_id):
        self.search_calls.append(produto_id)
        return self.existing

    def proximo_codigo(self):
        self.action_calls.append(("proximo_codigo", None))
        return self.next_code

    def salvar(self, **kwargs):
        self.saved.append(kwargs)
        return int(kwargs.get("produto_id") or 55)

    def listar(self, termo="", tipo="TODOS"):
        self.list_calls.append((termo, tipo))
        return list(self.rows)

    def localizar_similares(self, nome, *, codigo_barras=""):
        return list(self.rows)

    def preparar_duplicacao(self, produto_id):
        self.action_calls.append(("duplicar", produto_id))
        if self.duplicate_data is None:
            raise ValueError("Produto não encontrado.")
        return dict(self.duplicate_data)

    def listar_historico(self, produto_id):
        self.action_calls.append(("historico", produto_id))
        return list(self.history)

    def alternar_status(self, produto_id):
        self.action_calls.append(("status", produto_id))
        return self.next_status


class FakeEstoqueService:
    def __init__(self):
        self.adjustments = []

    def ajustar(self, produto_id, saldo, *, motivo, usuario):
        result = object()
        self.adjustments.append((produto_id, saldo, motivo, usuario, result))
        return result


class ProductApplicationServiceTests(unittest.TestCase):
    def command(self, **overrides):
        values = dict(
            codigo="1", nome="Mesa", preco_venda=100,
            categoria_id=None, tipo_produto="MERCADORIA", estoque_atual=8,
        )
        values.update(overrides)
        return ProductSaveCommand(**values)

    def test_new_product_does_not_duplicate_stock_adjustment(self):
        products = FakeProdutoService(existing=None)
        stock = FakeEstoqueService()
        result = ProductApplicationService(products, stock).salvar(self.command())
        self.assertTrue(result.criado)
        self.assertEqual(result.produto_id, 55)
        self.assertEqual(stock.adjustments, [])

    def test_edit_adjusts_stock_when_balance_changed(self):
        products = FakeProdutoService(existing={"estoque_atual": 3})
        stock = FakeEstoqueService()
        result = ProductApplicationService(products, stock).salvar(
            self.command(produto_id=9, estoque_atual=7)
        )
        self.assertFalse(result.criado)
        self.assertTrue(result.estoque_foi_ajustado)
        self.assertEqual(stock.adjustments[0][:2], (9, 7.0))
        self.assertEqual(result.estoque_anterior, 3.0)
        self.assertEqual(result.estoque_atual, 7.0)

    def test_service_product_never_generates_stock_adjustment(self):
        products = FakeProdutoService(existing={"estoque_atual": 4})
        stock = FakeEstoqueService()
        result = ProductApplicationService(products, stock).salvar(
            self.command(produto_id=9, tipo_produto="SERVIÇO", estoque_atual=0)
        )
        self.assertFalse(result.estoque_foi_ajustado)
        self.assertEqual(stock.adjustments, [])

    def test_editing_missing_product_is_rejected_before_save(self):
        products = FakeProdutoService(existing=None)
        stock = FakeEstoqueService()
        with self.assertRaisesRegex(ValueError, "Produto não encontrado"):
            ProductApplicationService(products, stock).salvar(
                self.command(produto_id=999)
            )
        self.assertEqual(products.saved, [])
        self.assertEqual(stock.adjustments, [])

    def test_table_rows_are_formatted_outside_ui(self):
        products = FakeProdutoService(rows=[{
            "id": 3, "codigo": "P3", "nome": "CADEIRA", "ativo": 0,
            "preco_venda": 50, "estoque_atual": 2, "categoria": "MÓVEIS",
            "marca": None, "unidade": "UN", "tipo_produto": "MERCADORIA",
        }])
        result = ProductApplicationService(products, FakeEstoqueService()).listar_tabela()
        self.assertEqual(result.rows[0].produto_id, 3)
        self.assertEqual(result.rows[0].values[1], "CADEIRA [INATIVO]")
        self.assertEqual(result.rows[0].values[2], "R$ 50.00")
        self.assertEqual(result.rows[0].values[-1], "Mercadoria")

    def test_product_list_result_centralizes_filter_rows_and_total(self):
        products = FakeProdutoService(rows=[{
            "id": 3, "codigo": "P3", "nome": "CADEIRA", "ativo": 1,
            "preco_venda": 50, "estoque_atual": 2, "categoria": None,
            "marca": None, "unidade": None, "tipo_produto": "SERVICO",
        }])
        result = ProductApplicationService(products, FakeEstoqueService()).listar_tabela(
            "  cadeira   azul ", " serviço "
        )
        self.assertEqual(products.list_calls, [("cadeira azul", "SERVIÇO")])
        self.assertEqual(result.query.termo, "cadeira azul")
        self.assertEqual(result.query.tipo, "SERVIÇO")
        self.assertEqual(result.total, 1)
        self.assertEqual(result.total_texto, "1 produto(s)")
        self.assertEqual(result.rows[0].produto_id, 3)
        self.assertEqual(result.rows[0].values[4:8], ("Sem categoria", "Sem marca", "UN", "Serviço"))

    def test_unknown_product_type_filter_falls_back_to_all(self):
        query = ProductApplicationService.normalizar_consulta_listagem(" mesa ", "qualquer")
        self.assertEqual(query.termo, "mesa")
        self.assertEqual(query.tipo, "TODOS")

    def test_selected_product_id_is_validated_outside_ui(self):
        self.assertEqual(ProductApplicationService.obter_produto_id_selecionado(("42",)), 42)
        with self.assertRaisesRegex(ValueError, "Selecione um produto"):
            ProductApplicationService.obter_produto_id_selecionado(())
        with self.assertRaisesRegex(ValueError, "Seleção de produto inválida"):
            ProductApplicationService.obter_produto_id_selecionado(("abc",))
        with self.assertRaisesRegex(ValueError, "Seleção de produto inválida"):
            ProductApplicationService.obter_produto_id_selecionado(("0",))

    def test_duplicate_assessment_is_centralized_outside_ui(self):
        products = FakeProdutoService(rows=[{
            "codigo": "P1", "nome": "MESA", "similaridade": 91.25,
            "criterio_similaridade": "NOME",
        }])
        assessment = ProductApplicationService(products, FakeEstoqueService()).avaliar_duplicidade(
            "Mesa grande", codigo_barras="789"
        )
        self.assertTrue(assessment.possui_similares)
        self.assertEqual(len(assessment.similares), 1)
        self.assertEqual(assessment.resumo(), "• P1 — MESA (91.2% por NOME)")

    def test_duplicate_assessment_is_skipped_when_editing(self):
        products = FakeProdutoService(rows=[{
            "codigo": "P1", "nome": "MESA", "similaridade": 100,
            "criterio_similaridade": "EAN",
        }])
        assessment = ProductApplicationService(products, FakeEstoqueService()).avaliar_duplicidade(
            "Mesa", codigo_barras="789", produto_id=1
        )
        self.assertFalse(assessment.possui_similares)

    def test_product_record_is_converted_to_form_state_outside_ui(self):
        state = ProductApplicationService.criar_estado_formulario(
            {
                "codigo": "P9", "nome": "Mesa", "preco_venda": 1234.5,
                "categoria_id": 2, "tipo_produto": "SERVICO", "marca_id": 3,
                "fornecedor_id": 4, "unidade_id": 5, "unidade_compra_id": 6,
                "fator_conversao": 12, "preco_custo": 800.25,
                "despesas_percentual": 5.5, "margem_lucro": 30,
                "codigo_barras": "789", "estoque_atual": 10.25,
                "estoque_minimo": 2, "permite_estoque_negativo": 1,
            },
            categorias={"Móveis": 2}, marcas={"Nabi": 3},
            fornecedores={"Fornecedor A": 4}, unidades={"UN": 5, "CX": 6},
        )
        self.assertEqual(state.preco_venda, "1234,5")
        self.assertEqual(state.tipo_produto, "SERVIÇO")
        self.assertEqual(state.categoria, "Móveis")
        self.assertEqual(state.unidade_compra, "CX")
        self.assertTrue(state.permite_estoque_negativo)

    def test_empty_product_creates_default_form_state(self):
        state = ProductApplicationService.criar_estado_formulario(
            None, categorias={}, marcas={}, fornecedores={}, unidades={},
            codigo_padrao="P10", unidade_padrao="UN",
        )
        self.assertEqual(state.codigo, "P10")
        self.assertEqual(state.fator_conversao, "1")
        self.assertEqual(state.estoque_atual, "0")
        self.assertEqual(state.unidade, "UN")

    def test_form_state_resolves_selected_names_to_ids(self):
        data = ProductApplicationService.criar_dados_formulario(
            ProductFormState(
                codigo="P1", nome="Mesa", preco_venda="100,00",
                categoria="Móveis", marca="Nabi", fornecedor="Fornecedor A",
                unidade="UN", unidade_compra="CX", tipo_produto="MERCADORIA",
            ),
            categorias={"Móveis": 2}, marcas={"Nabi": 3},
            fornecedores={"Fornecedor A": 4}, unidades={"UN": 5, "CX": 6},
            produto_id=9, usuario="Admin",
        )
        self.assertEqual(data.categoria_id, 2)
        self.assertEqual(data.marca_id, 3)
        self.assertEqual(data.unidade_id, 5)
        self.assertEqual(data.unidade_compra_id, 6)
        self.assertEqual(data.produto_id, 9)
        self.assertEqual(data.usuario, "Admin")

    def test_form_data_is_converted_to_save_command_outside_ui(self):
        command = ProductApplicationService.criar_comando(ProductFormData(
            codigo=" P1 ", nome=" Mesa ", preco_venda="1.234,56",
            categoria_id=2, tipo_produto=" MERCADORIA ",
            fator_conversao="12", preco_custo="800,50",
            despesas_percentual="5,5", margem_lucro="30",
            codigo_barras=" 789 ", estoque_atual="10,25",
            estoque_minimo="2", permite_estoque_negativo=True, produto_id=7,
        ))
        self.assertEqual(command.codigo, "P1")
        self.assertEqual(command.nome, "Mesa")
        self.assertEqual(command.preco_venda, Decimal("1234.56"))
        self.assertEqual(command.preco_custo, 800.50)
        self.assertEqual(command.estoque_atual, 10.25)
        self.assertEqual(command.codigo_barras, "789")
        self.assertEqual(command.produto_id, 7)
        self.assertTrue(command.permite_estoque_negativo)

    def test_form_data_uses_defaults_for_blank_numeric_fields(self):
        command = ProductApplicationService.criar_comando(ProductFormData(
            codigo="1", nome="Mesa", preco_venda="",
            categoria_id=None, tipo_produto="MERCADORIA",
            fator_conversao="",
        ))
        self.assertEqual(command.preco_venda, 0.0)
        self.assertEqual(command.fator_conversao, 1.0)

    def test_form_data_rejects_invalid_numeric_value(self):
        with self.assertRaisesRegex(ValueError, "Valor numérico inválido"):
            ProductApplicationService.criar_comando(ProductFormData(
                codigo="1", nome="Mesa", preco_venda="cem reais",
                categoria_id=None, tipo_produto="MERCADORIA",
            ))

    def test_sale_price_calculation_is_outside_tkinter_callbacks(self):
        state = ProductApplicationService.calcular_preco_formulario("100,00", "10", "20")
        self.assertEqual(state.preco_venda, "132")
        self.assertEqual(state.margem_lucro, "20")

    def test_margin_calculation_uses_total_cost_and_decimal_rounding(self):
        state = ProductApplicationService.calcular_margem_formulario("100", "10", "132")
        self.assertEqual(state.preco_venda, "132")
        self.assertEqual(state.margem_lucro, "20")

    def test_margin_calculation_does_not_allow_negative_margin_in_form(self):
        state = ProductApplicationService.calcular_margem_formulario("100", "0", "80")
        self.assertEqual(state.margem_lucro, "0")

    def test_price_calculation_rejects_invalid_percentage(self):
        with self.assertRaisesRegex(ValueError, "Margem inválido"):
            ProductApplicationService.calcular_preco_formulario("100", "0", "abc")

    def test_product_name_validation_is_outside_ui(self):
        self.assertEqual(ProductApplicationService.validar_nome_formulario("  Mesa   grande  "), "Mesa grande")
        with self.assertRaisesRegex(ValueError, "Informe o nome"):
            ProductApplicationService.validar_nome_formulario("   ")

    def test_numeric_field_validation_is_outside_ui(self):
        self.assertEqual(
            ProductApplicationService.validar_numero_formulario("1.234,50", "Preço de venda"),
            1234.5,
        )
        with self.assertRaisesRegex(ValueError, "Preço de venda inválido"):
            ProductApplicationService.validar_numero_formulario("abc", "Preço de venda")
        with self.assertRaisesRegex(ValueError, "Fator de conversão deve ser maior"):
            ProductApplicationService.validar_numero_formulario("0", "Fator de conversão", maior_zero=True)

    def test_save_command_rejects_empty_name_before_repository(self):
        products = FakeProdutoService(existing=None)
        with self.assertRaisesRegex(ValueError, "Informe o nome"):
            ProductApplicationService(products, FakeEstoqueService()).salvar(
                self.command(nome="   ")
            )
        self.assertEqual(products.saved, [])

    def test_save_command_rejects_invalid_business_consistency(self):
        service = ProductApplicationService(FakeProdutoService(), FakeEstoqueService())
        with self.assertRaisesRegex(ValueError, "fator de conversão"):
            service.salvar(self.command(fator_conversao=0))
        with self.assertRaisesRegex(ValueError, "Estoque mínimo"):
            service.salvar(self.command(estoque_minimo=-1))
        with self.assertRaisesRegex(ValueError, "Estoque não pode ser negativo"):
            service.salvar(self.command(estoque_atual=-1, permite_estoque_negativo=False))




    def test_registration_preparation_fetches_edit_data_and_builds_state(self):
        products = FakeProdutoService(existing={
            "id": 7, "codigo": "P7", "nome": "Mesa", "preco_venda": 120,
            "categoria_id": 2, "tipo_produto": "MERCADORIA",
        })
        result = ProductApplicationService(products, FakeEstoqueService()).preparar_cadastro(
            7, {"nome": "Dados ignorados"},
            categorias={"Móveis": 2}, marcas={}, fornecedores={}, unidades={"UN": 1},
        )
        self.assertTrue(result.editing)
        self.assertEqual(result.window_title, "Editar produto")
        self.assertEqual(result.state.codigo, "P7")
        self.assertEqual(result.state.nome, "Mesa")
        self.assertEqual(products.search_calls, [7])
        self.assertNotIn(("proximo_codigo", None), products.action_calls)

    def test_registration_preparation_uses_preloaded_data_and_next_code_for_new_product(self):
        products = FakeProdutoService()
        result = ProductApplicationService(products, FakeEstoqueService()).preparar_cadastro(
            dados_precarregados={"nome": "Mesa cópia", "codigo": ""},
            categorias={}, marcas={}, fornecedores={}, unidades={"UN": 1},
        )
        self.assertFalse(result.editing)
        self.assertEqual(result.heading, "Cadastrar produto")
        self.assertEqual(result.state.nome, "Mesa cópia")
        self.assertEqual(result.state.codigo, "")
        self.assertEqual(products.search_calls, [])
        self.assertEqual(products.action_calls, [("proximo_codigo", None)])

    def test_registration_preparation_rejects_missing_edit_product(self):
        products = FakeProdutoService(existing=None)
        with self.assertRaisesRegex(ValueError, "Produto não encontrado para edição"):
            ProductApplicationService(products, FakeEstoqueService()).preparar_cadastro(
                99, categorias={}, marcas={}, fornecedores={}, unidades={}
            )
        self.assertEqual(products.search_calls, [99])

    def test_duplicate_flow_is_orchestrated_by_application_service(self):
        products = FakeProdutoService(existing={"id": 7, "nome": "Mesa"})
        products.duplicate_data = {"codigo": "P1-COPIA", "nome": "MESA CÓPIA"}
        result = ProductApplicationService(products, FakeEstoqueService()).preparar_duplicacao(("7",))
        self.assertEqual(result["codigo"], "P1-COPIA")
        self.assertEqual(products.action_calls, [("duplicar", 7)])

    def test_history_flow_returns_formatted_immutable_rows(self):
        products = FakeProdutoService(existing={"id": 7, "nome": "Mesa"})
        products.history = [{
            "data": "05/08/2026", "motivo": "ATUALIZAR",
            "preco_anterior": 10, "preco_novo": 12.5,
            "custo": 8.25, "margem_percentual": 20,
        }]
        result = ProductApplicationService(products, FakeEstoqueService()).obter_historico(("7",))
        self.assertEqual(result.titulo, "Histórico — Mesa")
        self.assertEqual(result.rows[0].values, (
            "05/08/2026", "ATUALIZAR", "R$ 10.00", "R$ 12.50", "R$ 8.25", "20.00"
        ))
        self.assertEqual(products.action_calls, [("historico", 7)])

    def test_status_flow_returns_new_status_and_rejects_missing_product(self):
        products = FakeProdutoService(existing={"id": 7, "nome": "Mesa"})
        products.next_status = False
        service = ProductApplicationService(products, FakeEstoqueService())
        result = service.alternar_status(("7",))
        self.assertFalse(result.ativo)
        self.assertEqual(result.status_texto, "Inativo")
        products.next_status = None
        with self.assertRaisesRegex(ValueError, "Produto não encontrado"):
            service.alternar_status(("7",))

    def test_integrity_messages_are_centralized(self):
        self.assertIn("produto com esse código", ProductApplicationService.mensagem_integridade(
            sqlite3.IntegrityError("UNIQUE constraint failed: produtos.codigo")
        ))
        self.assertIn("código de barras", ProductApplicationService.mensagem_integridade(
            sqlite3.IntegrityError("UNIQUE constraint failed: produtos.codigo_barras")
        ))

    def test_auxiliary_catalog_is_typed_and_centralized(self):
        products = FakeProdutoService()
        products.categories = [{"id": 1, "nome": "Móveis"}]
        products.auxiliaries["marca"] = [{"id": 2, "nome": "Nabi"}]
        products.auxiliaries["fornecedor"] = [{"id": 3, "nome": "Fornecedor"}]
        products.auxiliaries["unidade"] = [{"id": 4, "nome": "UN"}]
        catalog = ProductApplicationService(products, FakeEstoqueService()).carregar_catalogo_auxiliar()
        self.assertEqual(catalog.mapa_categorias, {"Móveis": 1})
        self.assertEqual(catalog.mapa_marcas, {"Nabi": 2})
        self.assertEqual(catalog.mapa_fornecedores, {"Fornecedor": 3})
        self.assertEqual(catalog.mapa_unidades, {"UN": 4})

    def test_auxiliary_creation_is_delegated_and_type_validated(self):
        products = FakeProdutoService()
        service = ProductApplicationService(products, FakeEstoqueService())
        self.assertEqual(service.criar_categoria("Móveis"), 71)
        self.assertEqual(service.criar_auxiliar("fornecedor", "ACME", razao_social="ACME LTDA"), 72)
        with self.assertRaisesRegex(ValueError, "Tipo de cadastro auxiliar inválido"):
            service.criar_auxiliar("invalido", "X")


if __name__ == "__main__":
    unittest.main()

class ProductAuxiliaryHardeningTests(unittest.TestCase):
    def make_service(self):
        return ProductApplicationService(FakeProdutoService(), FakeEstoqueService())

    def test_catalog_rejects_duplicate_visible_names(self):
        from services.product_application_service import ProductApplicationError, ProductAuxiliaryCatalog, ProductAuxiliaryOption
        catalog = ProductAuxiliaryCatalog(
            categorias=(ProductAuxiliaryOption(1, "Móveis"), ProductAuxiliaryOption(2, "Móveis")),
            marcas=(), fornecedores=(), unidades=(),
        )
        with self.assertRaisesRegex(ProductApplicationError, "duplicados"):
            _ = catalog.mapa_categorias

    def test_malformed_auxiliary_record_is_rejected_with_context(self):
        from services.product_application_service import ProductApplicationError
        products = FakeProdutoService()
        products.categories = [{"id": 1}]
        with self.assertRaisesRegex(ProductApplicationError, "posição 1"):
            ProductApplicationService(products, FakeEstoqueService()).listar_categorias()

    def test_auxiliary_command_builds_infrastructure_extras_outside_ui(self):
        from services.product_application_service import ProductAuxiliaryCreateCommand
        products = FakeProdutoService()
        service = ProductApplicationService(products, FakeEstoqueService())
        result = service.criar_auxiliar_comando(ProductAuxiliaryCreateCommand(
            tipo="fornecedor", nome="Nabi", descricao="Nabi Comércio LTDA"
        ))
        self.assertEqual(result.item_id, 72)
        self.assertIn(("criar_auxiliar", "fornecedor", "Nabi", {"razao_social": "Nabi Comércio LTDA"}), products.action_calls)

    def test_sqlite_duplicate_is_translated_to_application_error(self):
        from services.product_application_service import ProductApplicationError, ProductAuxiliaryCreateCommand
        class DuplicateProdutoService(FakeProdutoService):
            def criar_auxiliar(self, tipo, nome, **extras):
                raise sqlite3.IntegrityError("UNIQUE constraint failed")
        service = ProductApplicationService(DuplicateProdutoService(), FakeEstoqueService())
        with self.assertRaisesRegex(ProductApplicationError, "Já existe"):
            service.criar_auxiliar_comando(ProductAuxiliaryCreateCommand("marca", "Nabi"))
