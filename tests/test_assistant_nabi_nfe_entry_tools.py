from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from assistant_nabi import CapabilityLevel, ModelReply, NFeEntryDraftService, ToolRequest
from assistant_nabi import create_draft_assistant
from assistant_nabi.nfe_entry_gateway import NabiCodeNFeEntryAssistantGateway

XML = """<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe>
<infNFe Id="NFe35123456789012345678901234567890123456789012">
<ide><nNF>123</nNF></ide><emit><CNPJ>12345678000199</CNPJ><xNome>Fornecedor</xNome></emit>
<dest><CNPJ>99887766000155</CNPJ><xNome>Empresa Teste</xNome></dest>
<det nItem="1"><prod><cProd>ABC</cProd><cEAN>7891</cEAN><xProd>Café</xProd>
<uCom>UN</uCom><qCom>2</qCom><vUnCom>10.50</vUnCom><vProd>21.00</vProd></prod></det>
<total><ICMSTot><vNF>21.00</vNF></ICMSTot></total></infNFe></NFe>
<protNFe><infProt><cStat>100</cStat></infProt></protNFe></nfeProc>"""


class Security:
    session = SimpleNamespace(user=SimpleNamespace(username="op", profile="OPERADOR", active=True))
    def is_expired(self): return False
    def require(self, module, action): return (module, action) in {
        ("compras", "create"), ("produtos", "view"), ("clientes", "view"),
        ("vendas", "create"),
    }


class Audit:
    def record_event(self, *args, **kwargs): return None


class CommercialQueries:
    def search_products(self, term, *, limit): return ()
    def search_customers(self, term, *, limit): return ()


class Imports:
    def __init__(self): self.calls = []
    def validar_nao_importada(self, document): return None
    def analisar(self, document):
        return [SimpleNamespace(
            index=0, item=document.itens[0], produto_id=5, status="VINCULAR",
            criterio="CÓDIGO", candidatos=(SimpleNamespace(
                produto_id=5, codigo="ABC", nome="CAFÉ", criterio="CÓDIGO",
                similaridade=100.0,
            ),),
        )]
    def importar_atomicamente(self, document, **kwargs):
        self.calls.append((document, kwargs))
        return {"importacao_id": 12, "itens_vinculados": 1}


class Model:
    def __init__(self, review_id): self.review_id = review_id
    def respond(self, message, *, available_tools):
        return ModelReply("Entrada preparada.", (ToolRequest(
            "compras.preparar_entrada_nfe_exata", {
                "review_draft_id": self.review_id,
                "conversion_factors": ["1"],
            }
        ),))


class NFeEntryToolTests(unittest.TestCase):
    def test_prepara_revisa_confirma_e_executa_sem_sefaz(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "nota.xml"
            path.write_text(XML, encoding="utf-8")
            imports = Imports()
            drafts = NFeEntryDraftService(imports)
            review = drafts.prepare_selected_file(path)
            assistant = create_draft_assistant(
                model=Model(review.draft_id), query_service=CommercialQueries(),
                security_service=Security(), audit_service=Audit(), session_id="sessao-real",
                nfe_entry_draft_service=drafts,
                nfe_entry_executor=NabiCodeNFeEntryAssistantGateway(drafts, imports),
            )
            result = assistant.ask("Lance esta nota com fator um").tool_results[0]
            self.assertTrue(result.success)
            self.assertEqual(result.payload["operation_kind"], "NFE_ENTRY_IMPORT")
            self.assertFalse(result.payload["persisted"])
            self.assertFalse(result.payload["sefaz_access"])
            challenge = assistant.review_draft(
                result.payload["draft_id"], result.payload["fingerprint"]
            )
            self.assertIs(challenge.required_capability, CapabilityLevel.REINFORCED_CONFIRMATION)
            executed, authorization = assistant.confirm_and_execute_nfe_entry(
                challenge.token, result.payload["draft_id"], result.payload["fingerprint"]
            )
            self.assertEqual(executed["importacao_id"], 12)
            with self.assertRaisesRegex(PermissionError, "já foi utilizada"):
                authorization.consume(
                    drafts.get(result.payload["draft_id"]),
                    operation="NFE_ENTRY_IMPORT",
                )
            self.assertEqual(len(imports.calls), 1)


if __name__ == "__main__": unittest.main()
