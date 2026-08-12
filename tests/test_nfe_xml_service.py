import tempfile
import unittest
from pathlib import Path

from services import NFeXMLService


XML = '''<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe><infNFe Id="NFe351234">
    <ide><nNF>123</nNF></ide>
    <emit><CNPJ>12345678000199</CNPJ><xNome>Fornecedor Teste</xNome></emit>
    <det nItem="1"><prod><cProd>ABC1</cProd><xProd>Produto XML</xProd><qCom>2.0000</qCom><uCom>UN</uCom><vUnCom>12.50</vUnCom><NCM>12345678</NCM><CFOP>5102</CFOP><CEST>0100100</CEST><cEAN>7890000000000</cEAN></prod></det>
  </infNFe></NFe>
</nfeProc>'''


class NFeXMLServiceTests(unittest.TestCase):
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
            self.assertEqual(doc.itens[0].preco_por_margem(30), 16.25)

    def test_rejeita_xml_sem_nfe(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "invalido.xml"
            arquivo.write_text("<raiz/>", encoding="utf-8")
            with self.assertRaises(ValueError):
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
