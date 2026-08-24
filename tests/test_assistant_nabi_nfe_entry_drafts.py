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
    <dest><CNPJ>99887766000155</CNPJ><xNome>Empresa Teste</xNome></dest>
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

    def test_prepara_entrada_exata_com_fator_explicito_sem_persistir(self):
        review = self.service.prepare_selected_file(self.path)
        draft = self.service.prepare_exact_import(review.draft_id, ["12"])
        self.assertEqual(draft.operation_kind, "NFE_ENTRY_IMPORT")
        self.assertTrue(draft.executable)
        self.assertFalse(draft.persisted)
        self.assertEqual(draft.items[0].product_id, 5)
        self.assertEqual(str(draft.items[0].stock_quantity), "24.0000")
        self.assertEqual(self.imports.mutations, 0)

    def test_nabi_expoe_sugestao_de_embalagem_sem_confirmar_por_conta_propria(self):
        self.path.write_text(XML.replace("<xProd>Café</xProd>", "<xProd>ITALAQUINHO 27X200ML</xProd>"), encoding="utf-8")
        draft = self.service.prepare_selected_file(self.path)
        item = draft.items[0]
        self.assertEqual(item.suggested_conversion_factor, "27")
        self.assertEqual(item.factor_confidence, "ALTA")
        self.assertIn("27X200ML", item.factor_evidence)
        self.assertFalse(draft.executable)

    def test_bloqueia_fator_omitido_xml_alterado_e_vinculo_nao_exato(self):
        review = self.service.prepare_selected_file(self.path)
        with self.assertRaisesRegex(ValueError, "todos os itens"):
            self.service.prepare_exact_import(review.draft_id, [])
        self.path.write_text(XML.replace("<qCom>2</qCom>", "<qCom>3</qCom>"), encoding="utf-8")
        with self.assertRaisesRegex(PermissionError, "mudou"):
            self.service.prepare_exact_import(review.draft_id, ["1"])
        self.path.write_text(XML, encoding="utf-8")
        self.imports.analisar = lambda document: [SimpleNamespace(
            index=0, item=document.itens[0], produto_id=5, status="REVISAR",
            criterio="NOME", candidatos=(),
        )]
        ambiguous = self.service.prepare_selected_file(self.path)
        with self.assertRaisesRegex(ValueError, "conferência humana"):
            self.service.prepare_exact_import(ambiguous.draft_id, ["1"])

    def test_bloqueia_codigo_exato_duplicado_em_mais_de_um_produto(self):
        self.imports.analisar = lambda document: [SimpleNamespace(
            index=0, item=document.itens[0], produto_id=5, status="VINCULAR",
            criterio="CÓDIGO", candidatos=(
                SimpleNamespace(produto_id=5, codigo="ABC", nome="CAFÉ A", criterio="CÓDIGO", similaridade=100),
                SimpleNamespace(produto_id=6, codigo="ABC", nome="CAFÉ B", criterio="CÓDIGO", similaridade=100),
            ),
        )]
        review = self.service.prepare_selected_file(self.path)
        with self.assertRaisesRegex(ValueError, "conferência humana"):
            self.service.prepare_exact_import(review.draft_id, ["1"])

    def test_automacao_bloqueia_cstat_desconhecido_e_destinatario_sem_documento(self):
        self.path.write_text(XML.replace("<cStat>100</cStat>", "<cStat>204</cStat>"), encoding="utf-8")
        review = self.service.prepare_selected_file(self.path)
        with self.assertRaisesRegex(ValueError, "cStat 100"):
            self.service.prepare_exact_import(review.draft_id, ["1"])
        self.path.write_text(
            XML.replace("<CNPJ>99887766000155</CNPJ>", ""), encoding="utf-8"
        )
        missing_recipient = self.service.prepare_selected_file(self.path)
        with self.assertRaisesRegex(ValueError, "destinatário"):
            self.service.prepare_exact_import(missing_recipient.draft_id, ["1"])


if __name__ == "__main__": unittest.main()
