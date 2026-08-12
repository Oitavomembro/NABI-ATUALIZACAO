import sqlite3
import tempfile
from decimal import Decimal
from pathlib import Path
import unittest

from services.pdv_service import PDVService


class PDVServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "pdv.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE configuracoes(id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT UNIQUE, valor TEXT)")
        conn.commit(); conn.close()
        self.service = PDVService(lambda: sqlite3.connect(self.db_path))

    def tearDown(self):
        self.temp.cleanup()

    def test_suspender_e_reabrir_remove_da_lista(self):
        venda = self.service.suspender([{"item": "A", "qtd": 2, "preco": 3.5, "subtotal": 7}], cliente_id=4, cliente_nome="Cliente")
        self.assertEqual(venda.total, 7)
        self.assertEqual(len(self.service.listar_suspensas()), 1)
        reaberta = self.service.reabrir(venda.id)
        self.assertEqual(reaberta.cliente_id, 4)
        self.assertEqual(len(self.service.listar_suspensas()), 0)

    def test_totalizar_rejeita_quantidade_invalida(self):
        with self.assertRaises(ValueError):
            self.service.totalizar([{"qtd": 0, "preco": 10}])

    def test_pagamento_misto_calcula_troco(self):
        recebido, troco = self.service.validar_pagamentos(100, [
            {"forma": "PIX", "valor": 40}, {"forma": "DINHEIRO", "valor": 70}
        ])
        self.assertEqual(recebido, 110)
        self.assertEqual(troco, 10)

    def test_pagamento_misto_rejeita_valor_insuficiente(self):
        with self.assertRaisesRegex(ValueError, "Faltam"):
            self.service.validar_pagamentos(100, [{"forma": "PIX", "valor": 90}])


    def test_rejeita_forma_desconhecida(self):
        with self.assertRaisesRegex(ValueError, "Forma de pagamento inválida"):
            self.service.validar_pagamentos(100, [{"forma": "CHEQUE", "valor": 100}])

    def test_entrada_mais_crediario_e_permitido(self):
        recebido, troco = self.service.validar_pagamentos(100, [
            {"forma": "PIX", "valor": 30},
            {"forma": "CREDIARIO", "valor": 70},
        ])
        self.assertEqual(recebido, 100)
        self.assertEqual(troco, 0)

    def test_entrada_mais_crediario_deve_fechar_o_total(self):
        with self.assertRaisesRegex(ValueError, "entrada somada ao valor financiado"):
            self.service.validar_pagamentos(100, [
                {"forma": "PIX", "valor": 20},
                {"forma": "CREDIARIO", "valor": 70},
            ])

    def test_nao_permite_duas_partes_em_crediario(self):
        with self.assertRaisesRegex(ValueError, "somente uma parte em crediário"):
            self.service.validar_pagamentos(100, [
                {"forma": "CREDIARIO", "valor": 50},
                {"forma": "CREDIARIO", "valor": 50},
            ])

    def test_pix_nao_gera_troco(self):
        with self.assertRaisesRegex(ValueError, "não podem gerar troco"):
            self.service.validar_pagamentos(100, [{"forma": "PIX", "valor": 110}])

    def test_troco_considera_somente_dinheiro(self):
        recebido, troco = self.service.validar_pagamentos(100, [
            {"forma": "PIX", "valor": 80}, {"forma": "DINHEIRO", "valor": 30}
        ])
        self.assertEqual(recebido, 110)
        self.assertEqual(troco, 10)

    def test_registra_pagamentos_estruturados_na_mesma_transacao(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("BEGIN")
            self.service.registrar_pagamentos_transacao(
                conn, 7, [{"forma": "PIX", "valor": 40}, {"forma": "DINHEIRO", "valor": 70}],
                total=100, recebido=110, troco=10,
            )
            conn.commit()
        finally:
            conn.close()
        dados = self.service.obter_pagamentos_venda(7)
        self.assertEqual(dados["troco"], 10)
        self.assertEqual(dados["pagamentos"][0]["forma"], "PIX")

    def test_modo_pdv_normalizado(self):
        self.assertEqual(self.service.normalizar_modo("touch"), "TOUCH")
        with self.assertRaises(ValueError):
            self.service.normalizar_modo("inexistente")

    def test_salvar_e_consumir_orcamento(self):
        documento = self.service.salvar_documento(
            "ORCAMENTO", [{"item": "A", "qtd": 1, "preco": 15, "subtotal": 15}],
            cliente_id=2, cliente_nome="Cliente",
        )
        self.assertEqual(documento.tipo, "ORCAMENTO")
        self.assertEqual(len(self.service.listar_documentos("ORCAMENTO")), 1)
        consumido = self.service.consumir_documento(documento.id)
        self.assertEqual(consumido.total, 15)
        self.assertEqual(self.service.listar_documentos(), [])

    def test_documento_rejeita_tipo_invalido(self):
        with self.assertRaises(ValueError):
            self.service.salvar_documento("PEDIDO", [{"item": "A", "qtd": 1, "preco": 1}])

    def test_aplicar_desconto_preserva_preco_original(self):
        item = {"item": "A", "qtd": 2, "preco": 50, "subtotal": 100}
        descontado = self.service.aplicar_desconto(item, 10)
        self.assertEqual(descontado["preco_original"], 50)
        self.assertEqual(descontado["preco"], 45)
        self.assertEqual(descontado["subtotal"], 90)
        restaurado = self.service.aplicar_desconto(descontado, 0)
        self.assertEqual(restaurado["preco"], 50)
        self.assertEqual(restaurado["subtotal"], 100)

    def test_atualizar_quantidade_recalcula_subtotal(self):
        item = {"item": "A", "qtd": 1, "preco": 12.5, "subtotal": 12.5}
        atualizado = self.service.atualizar_quantidade(item, 3)
        self.assertEqual(atualizado["qtd"], 3)
        self.assertEqual(atualizado["subtotal"], 37.5)
        self.assertEqual(item["qtd"], 1)

    def test_atualizar_quantidade_rejeita_zero(self):
        with self.assertRaisesRegex(ValueError, "maior que zero"):
            self.service.atualizar_quantidade({"qtd": 1, "preco": 10}, 0)

    def test_aplicar_desconto_rejeita_percentual_invalido(self):
        with self.assertRaisesRegex(ValueError, "entre 0 e 100"):
            self.service.aplicar_desconto({"qtd": 1, "preco": 10}, 101)

    def test_editar_item_venda_recalcula_com_precisao_sem_alterar_cadastro(self):
        original = {
            "produto_id": 7,
            "item": "CADEIRA",
            "codigo": "C7",
            "qtd": 1,
            "preco": 10,
            "subtotal": 10,
            "controla_estoque": True,
        }
        editado = self.service.editar_item_venda(
            original,
            quantidade="2.5",
            preco_unitario="12.34",
            desconto_percentual="10",
        )
        self.assertEqual(editado["qtd"], Decimal("2.5"))
        self.assertEqual(editado["preco_original"], Decimal("12.34"))
        self.assertEqual(editado["preco"], Decimal("11.11"))
        self.assertEqual(editado["subtotal"], Decimal("27.78"))
        self.assertEqual(editado["item"], "CADEIRA")
        self.assertEqual(editado["codigo"], "C7")
        self.assertEqual(editado["produto_id"], 7)
        self.assertEqual(original["qtd"], 1)
        self.assertNotIn("preco_original", original)

    def test_editar_item_venda_rejeita_valores_transacionais_invalidos(self):
        item = {"item": "A", "qtd": 1, "preco": 10, "subtotal": 10}
        for kwargs, mensagem in (
            ({"quantidade": 0, "preco_unitario": 10}, "maior que zero"),
            ({"quantidade": 1, "preco_unitario": -1}, "não pode ser negativo"),
            ({"quantidade": 1, "preco_unitario": 10, "desconto_percentual": 101}, "entre 0 e 100"),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, mensagem):
                self.service.editar_item_venda(item, **kwargs)


if __name__ == "__main__":
    unittest.main()

class TestFinalizacaoEtapa2(unittest.TestCase):
    def test_desconto_percentual_troco_e_falta(self):
        calculo = PDVService.calcular_finalizacao(
            55.0, desconto=10, desconto_tipo="PERCENTUAL", recebido=100, forma="DINHEIRO"
        )
        self.assertEqual(calculo["desconto_valor"], 5.50)
        self.assertEqual(calculo["total_final"], 49.50)
        self.assertEqual(calculo["troco"], 50.50)
        self.assertEqual(calculo["falta"], 0.0)

        insuficiente = PDVService.calcular_finalizacao(55.0, recebido=30, forma="DINHEIRO")
        self.assertEqual(insuficiente["falta"], 25.0)
        self.assertEqual(insuficiente["troco"], 0.0)

    def test_acrescimo_percentual_e_rateio(self):
        calculo = PDVService.calcular_finalizacao(
            100.0, acrescimo=10, acrescimo_tipo="PERCENTUAL", recebido=110, forma="PIX"
        )
        self.assertEqual(calculo["acrescimo_valor"], 10.0)
        self.assertEqual(calculo["total_final"], 110.0)
        itens = [
            {"item": "A", "qtd": 1, "preco": 40.0, "subtotal": 40.0},
            {"item": "B", "qtd": 2, "preco": 30.0, "subtotal": 60.0},
        ]
        rateados = PDVService.ratear_total_itens(itens, 110.0)
        self.assertEqual(PDVService.totalizar(rateados), 110.0)

    def test_novas_formas_pagamento(self):
        for forma in ("PIX", "DEBITO", "CREDITO", "OUTROS"):
            recebido, troco = PDVService.validar_pagamentos(55.0, [{"forma": forma, "valor": 55.0}])
            self.assertEqual(recebido, 55.0)
            self.assertEqual(troco, 0.0)
