from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from assistant_nabi import NFeEntryDraftService


XML = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe><infNFe Id="NFe35123456789012345678901234567890123456789012">
    <ide><nNF>123</nNF><serie>1</serie><mod>55</mod></ide>
    <emit><CNPJ>12345678000199</CNPJ><xNome>Fornecedor Teste</xNome></emit>
    <det nItem="1"><prod><cProd>ABC</cProd><cEAN>7891</cEAN><xProd>Café</xProd>
      <NCM>0901</NCM><CFOP>5102</CFOP><uCom>UN</uCom><qCom>2</qCom>
      <vUnCom>10.50</vUnCom><vProd>21.00</vProd></prod></det>
    <total><ICMSTot><vNF>21.00</vNF></ICMSTot></total>
  </infNFe></NFe><protNFe><infProt><cStat>100</cStat></infProt></protNFe>
</nfeProc>"""


class Imports:
    def __init__(self): self.mutations = 0
    def validar_nao_importada(self, document): return None
    def analisar(self, document):
        return [SimpleNamespace(
            index=0, item=document.itens[0], produto_id=5, status="VINCULAR",
            criterio="EAN", candidatos=(SimpleNamespace(
                produto_id=5, codigo="P5", nome="CAFÉ", criterio="EAN",
                similaridade=100.0,
            ),),
        )]


class NFeEntryDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "nota.xml"
        self.path.write_text(XML, encoding="utf-8")
        self.imports = Imports()
        self.service = NFeEntryDraftService(self.imports)

    def tearDown(self): self.temp.cleanup()

    def test_prepara_evidencia_estruturada_sem_importar(self):
        draft = self.service.prepare_selected_file(self.path)
        self.assertEqual(draft.access_key, "35123456789012345678901234567890123456789012")
        self.assertEqual(draft.protocol_status_evidence, "100")
        self.assertEqual(draft.items[0].suggested_product_id, 5)
        self.assertEqual(draft.items[0].quantity, "2.0000")
        self.assertFalse(draft.persisted)
        self.assertFalse(draft.executable)
        self.assertEqual(self.imports.mutations, 0)
        self.assertEqual(self.service.get(draft.draft_id), draft)

    def test_rejeita_dtd_entidade_extensao_e_tamanho_antes_do_parser(self):
        malicious = Path(self.temp.name) / "malicioso.xml"
        malicious.write_text("<!DOCTYPE x [<!ENTITY a 'x'>]><x>&a;</x>", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "DTD ou entidade"):
            self.service.prepare_selected_file(malicious)
        wrong = Path(self.temp.name) / "nota.txt"
        wrong.write_text(XML, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "arquivo XML"):
            self.service.prepare_selected_file(wrong)
        tiny_limit = NFeEntryDraftService(self.imports, max_bytes=1024)
        huge = Path(self.temp.name) / "grande.xml"
        huge.write_bytes(b"<x>" + b"a" * 2000 + b"</x>")
        with self.assertRaisesRegex(ValueError, "limite seguro"):
            tiny_limit.prepare_selected_file(huge)

    def test_nao_interpreta_cstat_como_autorizacao_propria(self):
        draft = self.service.prepare_selected_file(self.path)
        self.assertEqual(draft.protocol_status_evidence, "100")
        self.assertNotIn("autoriz", draft.operation_kind.casefold())
        self.assertFalse(draft.executable)


if __name__ == "__main__": unittest.main()
