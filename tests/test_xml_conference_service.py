import unittest

from services.xml_conference_service import XMLConferenceService


class XMLConferenceServiceTests(unittest.TestCase):
    def test_calcula_preco_por_margem(self):
        result = XMLConferenceService.por_margem("39,00", "30")
        self.assertEqual(float(result.preco_venda), 50.70)
        self.assertEqual(float(result.lucro_unitario), 11.70)
        self.assertEqual(float(result.markup_percentual), 30.0)

    def test_calcula_margem_por_preco(self):
        result = XMLConferenceService.por_preco(40, 60)
        self.assertEqual(float(result.margem_percentual), 50.0)
        self.assertEqual(float(result.lucro_unitario), 20.0)

    def test_parse_clipboard_rows_com_cabecalho_e_preco(self):
        rows = XMLConferenceService.parse_clipboard_rows(
            "Quantidade\tFator\tUnidade\tCusto\tMargem\tPreço\n"
            "2\t6\tUN\t3,50\t\t9,90\n"
            "1\t1\tCX\t10\t30\t"
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["quantidade"], 2.0)
        self.assertEqual(rows[0]["fator"], 6.0)
        self.assertEqual(rows[0]["preco"], 9.9)
        self.assertEqual(rows[1]["unidade"], "CX")
        self.assertEqual(rows[1]["preco"], 13.0)

    def test_parse_clipboard_rows_rejeita_linha_incompleta(self):
        with self.assertRaisesRegex(ValueError, "quantidade, fator, unidade e custo"):
            XMLConferenceService.parse_clipboard_rows("1\t2\tUN")

    def test_valida_todos_os_itens(self):
        configs = {
            0: {"quantidade": 1, "fator": 1, "unidade": "UN", "custo": 10, "preco": 15},
            1: {"quantidade": 0, "fator": 1, "unidade": "", "custo": 10, "preco": 0},
        }
        errors = XMLConferenceService.validar_todos(configs)
        self.assertNotIn(0, errors)
        self.assertIn(1, errors)
        self.assertGreaterEqual(len(errors[1]), 3)


if __name__ == "__main__":
    unittest.main()
