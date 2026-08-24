from __future__ import annotations

import hashlib
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from assistant_nabi import AssistantActor, DraftConfirmationService
from assistant_nabi.nfe_entry_drafts import NFeEntryImportDraft, NFeEntryImportDraftItem
from assistant_nabi.nfe_entry_gateway import NabiCodeNFeEntryAssistantGateway


class Imports:
    def __init__(self): self.calls = []
    def importar_atomicamente(self, document, **kwargs):
        self.calls.append((document, kwargs))
        return {"importacao_id": 7, "itens_vinculados": 1}


class Drafts:
    def __init__(self, document): self.document = document
    def document_for(self, draft_id): return self.document


class NFeEntryGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "nota.xml"
        self.path.write_text("<xml />", encoding="utf-8")
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        item = NFeEntryImportDraftItem(
            0, 9, "ABC", "Produto", Decimal("2.0000"), Decimal("3.0000"),
            Decimal("6.0000"), "CX", Decimal("10.50"),
        )
        self.draft = NFeEntryImportDraft(
            "d1", "a" * 64, "r1", str(self.path), digest, "chave", "1",
            "Fornecedor", "123", "100", Decimal("21.00"),
            "Empresa", "99887766000155", (item,),
        )
        self.imports = Imports()
        self.gateway = NabiCodeNFeEntryAssistantGateway(Drafts("documento"), self.imports)
        self.broker = DraftConfirmationService()
        self.actor = AssistantActor("Operador", "OPERADOR", "sessao-1")

    def authorization(self):
        challenge = self.broker.issue(self.draft, actor=self.actor)
        return self.broker.confirm(
            token=challenge.token, draft=self.draft, actor=self.actor
        )

    def tearDown(self): self.temp.cleanup()

    def test_executa_servico_oficial_com_vinculo_real_e_idempotencia(self):
        result = self.gateway.execute(self.draft, self.authorization())
        self.assertEqual(result["importacao_id"], 7)
        document, call = self.imports.calls[0]
        self.assertEqual(document, "documento")
        self.assertEqual(call["itens"][0]["produto_id"], 9)
        self.assertEqual(call["itens"][0]["fator"], "3.0000")
        self.assertEqual(call["expected_actor"], "Operador")
        self.assertEqual(call["idempotency_key"], "nabi:nfe:d1")
        self.assertEqual(call["operation_fingerprint"], "a" * 64)

    def test_recusa_autorizacao_divergente_e_xml_alterado(self):
        bad = SimpleNamespace(draft_id="d1", fingerprint="b" * 64)
        with self.assertRaisesRegex(PermissionError, "broker"):
            self.gateway.execute(self.draft, bad)
        self.path.write_text("<alterado />", encoding="utf-8")
        with self.assertRaisesRegex(PermissionError, "mudou"):
            self.gateway.execute(self.draft, self.authorization())
        self.assertEqual(self.imports.calls, [])


if __name__ == "__main__": unittest.main()
