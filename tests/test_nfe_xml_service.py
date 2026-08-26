import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from services import NFeXMLService


XML = '''<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe><infNFe Id="NFe351234">
    <ide><nNF>123</nNF></ide>
    <emit><CNPJ>12345678000199</CNPJ><xNome>Fornecedor Teste</xNome></emit>
    <det nItem="1"><prod><cProd>ABC1</cProd><xProd>Produto XML</xProd><qCom>2.0000</qCom><uCom>UN</uCom><vUnCom>12.50</vUnCom><vProd>25.00</vProd><NCM>12345678</NCM><CFOP>5102</CFOP><CEST>0100100</CEST><cEAN>7890000000000</cEAN></prod><imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST><vBC>25.00</vBC><pICMS>18.00</pICMS><vICMS>4.50</vICMS></ICMS00></ICMS><IPI><IPITrib><CST>50</CST><vBC>25.00</vBC><pIPI>5.00</pIPI><vIPI>1.25</vIPI></IPITrib></IPI><PIS><PISAliq><CST>01</CST><vBC>25.00</vBC><pPIS>1.65</pPIS><vPIS>0.41</vPIS></PISAliq></PIS><COFINS><COFINSAliq><CST>01</CST><vBC>25.00</vBC><pCOFINS>7.60</pCOFINS><vCOFINS>1.90</vCOFINS></COFINSAliq></COFINS><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib><gIBSCBS><vBC>25.00</vBC><gIBSUF><pIBSUF>0.1000</pIBSUF><vIBSUF>0.03</vIBSUF></gIBSUF><gIBSMun><pIBSMun>0.0000</pIBSMun><vIBSMun>0.00</vIBSMun></gIBSMun><vIBS>0.03</vIBS><gCBS><pCBS>0.9000</pCBS><vCBS>0.23</vCBS></gCBS></gIBSCBS></IBSCBS></imposto></det>
  </infNFe></NFe>
</nfeProc>'''


class NFeXMLServiceTests(unittest.TestCase):
    def test_itens_seguem_nitem_da_nota_mesmo_se_xml_estiver_fora_de_ordem(self):
        xml = XML.replace(
            '<det nItem="1">',
            '<det nItem="2">',
        ).replace(
            '</infNFe>',
            '<det nItem="1"><prod><cProd>PRIMEIRO</cProd><xProd>Primeiro</xProd>'
            '<qCom>1</qCom><uCom>UN</uCom><vUnCom>1</vUnCom><vProd>1</vProd>'
            '</prod></det></infNFe>',
        )
        with tempfile.TemporaryDirectory() as temp:
            arquivo = Path(temp) / "fora-de-ordem.xml"
            arquivo.write_text(xml, encoding="utf-8")
            document = NFeXMLService().ler(arquivo)
        self.assertEqual([item.item_numero for item in document.itens], [1, 2])
        self.assertEqual([item.codigo for item in document.itens], ["PRIMEIRO", "ABC1"])

    def test_le_nfe_com_namespace(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "nfe.xml"
            arquivo.write_text(XML, encoding="utf-8")
            doc = NFeXMLService().ler(arquivo)
            self.assertEqual(doc.numero, "123")
            self.assertEqual(doc.fornecedor, "Fornecedor Teste")
            self.assertEqual(doc.itens[0].codigo, "ABC1")
            self.assertEqual(doc.itens[0].valor_unitario, 12.5)
            self.assertEqual(doc.itens[0].ncm, "12345678")
            self.assertEqual(doc.itens[0].cfop, "5102")
            self.assertEqual(doc.itens[0].ibs_cbs_cst, "000")
            self.assertEqual(doc.itens[0].ibs_cbs_class, "000001")
            self.assertEqual(doc.itens[0].ibs_cbs_base, 25.0)
            self.assertEqual(doc.itens[0].ibs_uf_rate, 0.1)
            self.assertEqual(doc.itens[0].cbs_rate, 0.9)
            self.assertEqual(doc.itens[0].base_icms, 25.0)
            self.assertEqual(doc.itens[0].aliquota_icms, 18.0)
            self.assertEqual(doc.itens[0].valor_icms, 4.5)
            self.assertEqual(doc.itens[0].valor_pis, 0.41)
            self.assertEqual(doc.itens[0].valor_cofins, 1.9)
            self.assertEqual(doc.itens[0].valor_ipi, 1.25)
            self.assertEqual(doc.itens[0].preco_por_margem(30), 16.25)

    def test_rejeita_xml_sem_nfe(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "invalido.xml"
            arquivo.write_text("<raiz/>", encoding="utf-8")
            with self.assertRaises(ValueError):
                NFeXMLService().ler(arquivo)

    def test_le_duplicatas_e_formas_de_pagamento_sem_inferir_dados(self):
        financeiro = XML.replace(
            "</infNFe>",
            "<cobr><dup><nDup>001</nDup><dVenc>2026-09-10</dVenc><vDup>10.00</vDup></dup>"
            "<dup><nDup>002</nDup><dVenc>2026-10-10</dVenc><vDup>15.00</vDup></dup></cobr>"
            "<pag><detPag><tPag>03</tPag><vPag>25.00</vPag></detPag></pag></infNFe>",
        )
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "nfe.xml"
            arquivo.write_text(financeiro, encoding="utf-8")
            doc = NFeXMLService().ler(arquivo)
        self.assertEqual(
            [(dup.numero, dup.data_vencimento, dup.valor) for dup in doc.duplicatas],
            [("001", "2026-09-10", Decimal("10.00")),
             ("002", "2026-10-10", Decimal("15.00"))],
        )
        self.assertEqual([(pag.forma, pag.valor) for pag in doc.pagamentos], [("03", Decimal("25.00"))])

    def test_xml_antigo_sem_cobranca_mantem_financeiro_vazio(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "nfe.xml"
            arquivo.write_text(XML, encoding="utf-8")
            doc = NFeXMLService().ler(arquivo)
        self.assertEqual(doc.duplicatas, ())
        self.assertEqual(doc.pagamentos, ())

    def test_rejeita_duplicata_sem_vencimento(self):
        xml = XML.replace("</infNFe>", "<cobr><dup><nDup>1</nDup><vDup>25.00</vDup></dup></cobr></infNFe>")
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "nfe.xml"
            arquivo.write_text(xml, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "dVenc"):
                NFeXMLService().ler(arquivo)

    def test_salva_relatorio_atomico(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "nfe.xml"
            arquivo.write_text(XML, encoding="utf-8")
            service = NFeXMLService()
            doc = service.ler(arquivo)
            relatorio = service.salvar_relatorio(doc, [{"codigo": "ABC1", "status": "criado"}], Path(pasta) / "relatorios")
            self.assertTrue(relatorio.exists())
            self.assertIn('"status": "criado"', relatorio.read_text(encoding="utf-8"))

    def test_rejeita_margem_negativa(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "nfe.xml"
            arquivo.write_text(XML, encoding="utf-8")
            item = NFeXMLService().ler(arquivo).itens[0]
            with self.assertRaises(ValueError):
                item.preco_por_margem(-1)


if __name__ == "__main__":
    unittest.main()
