from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from assistant_nabi import (
    CapabilityLevel, ModelReply, ToolRequest, create_draft_assistant,
    create_financial_assistant_components,
)
from database import DatabaseManager
from database.schema_initializer import initialize_database
from commercial.infrastructure.runtime import create_commercial_container
from commercial.application.action_dto import ActionContext, ActionOrigin
from commercial.application.financial_dto import CreateFinancialTitleCommand
from commercial.application.financial_action_service import FinancialActionService


class _Audit:
    def record_event(self, *args, **kwargs): pass


class _Queries:
    def search_products(self, term, *, limit): return ()
    def search_customers(self, term, *, limit): return ()


class _Security:
    def __init__(self, permissions):
        self.permissions = set(permissions)
        self.session = SimpleNamespace(
            user=SimpleNamespace(username="financeiro-real", profile="ADMIN", active=True)
        )
    def is_expired(self): return False
    def require(self, module, action): return (module, action) in self.permissions


class _Model:
    def __init__(self, tool_name, parameters):
        self.tool_name, self.parameters = tool_name, parameters
    def respond(self, message, *, available_tools):
        return ModelReply("Rascunho preparado.", (
            ToolRequest(self.tool_name, self.parameters),
        ))


class AssistantFinancialActionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db = DatabaseManager(root / "nabicode.db")
        initialize_database(
            db_name=str(root / "nabicode.db"), backup_dir=str(root / "backups"),
            pdf_dir=str(root / "pdfs"), schema_version=20,
            last_database_update={"executada": False, "de": 0, "para": 20, "backup": ""},
            network_mode=False, network_role="local", connect=self.db.connect,
            read_existing_version=lambda: 0, backup_before_update=lambda *_: "",
        )
        self.container = create_commercial_container(self.db)
        self.finance = self.container.financial_actions._gateway.service
        self.drafts, self.executor = create_financial_assistant_components(
            self.container, self.finance
        )

    def tearDown(self): self.temp.cleanup()

    def _assistant(self, model, permissions=(("financeiro", "create"), ("financeiro", "pay"))):
        return create_draft_assistant(
            model=model, query_service=_Queries(), security_service=_Security(permissions),
            audit_service=_Audit(), session_id="sessao-financeira-real",
            financial_draft_service=self.drafts, financial_executor=self.executor,
        )

    def _prepare_and_confirm(self, assistant, message="Prepare"):
        result = assistant.ask(message).tool_results[0]
        self.assertTrue(result.success)
        self.assertFalse(result.payload["persisted"])
        challenge = assistant.review_draft(
            result.payload["draft_id"], result.payload["fingerprint"]
        )
        self.assertIs(challenge.required_capability, CapabilityLevel.REINFORCED_CONFIRMATION)
        confirmed, _ = assistant.confirm_and_execute_financial(
            challenge.token, result.payload["draft_id"], result.payload["fingerprint"]
        )
        return result, confirmed

    def test_cria_receber_e_pagar_somente_depois_da_confirmacao(self):
        for kind in ("RECEBER", "PAGAR"):
            assistant = self._assistant(_Model("financeiro.preparar_titulo", {
                "title_type": kind, "amount": "125.50", "due_date": "2026-09-10",
                "party_name": "PARTE REAL", "description": "SERVICO",
            }))
            prepared = assistant.ask("Prepare").tool_results[0]
            self.assertTrue(prepared.success)
            self.assertEqual(self.finance.listar_titulos(tipo=kind), [])
            challenge = assistant.review_draft(prepared.payload["draft_id"], prepared.payload["fingerprint"])
            result, _ = assistant.confirm_and_execute_financial(
                challenge.token, prepared.payload["draft_id"], prepared.payload["fingerprint"]
            )
            self.assertTrue(result.committed)
            self.assertEqual(result.open_amount, 125.50)

    def test_baixa_parcial_revalida_saldo_e_usa_id_real(self):
        title_id = self.finance.criar_titulo(
            tipo="RECEBER", valor="200", data_vencimento=date.today(), usuario="setup"
        )
        assistant = self._assistant(_Model("financeiro.preparar_baixa", {
            "title_type": "RECEBER", "title_id": title_id, "amount": "75.00",
            "payment_method": "PIX", "payment_date": date.today().isoformat(),
        }))
        _prepared, result = self._prepare_and_confirm(assistant)
        self.assertEqual(result.title_id, title_id)
        self.assertEqual(result.open_amount, 125.00)
        self.assertEqual(len(self.finance.listar_pagamentos(title_id)), 1)

    def test_saldo_mudou_depois_da_revisao_bloqueia_sem_segunda_baixa(self):
        title_id = self.finance.criar_titulo(
            tipo="PAGAR", valor="200", data_vencimento=date.today(), usuario="setup"
        )
        assistant = self._assistant(_Model("financeiro.preparar_baixa", {
            "title_type": "PAGAR", "title_id": title_id, "amount": "50.00",
            "payment_method": "PIX", "payment_date": date.today().isoformat(),
        }))
        prepared = assistant.ask("Prepare").tool_results[0]
        challenge = assistant.review_draft(prepared.payload["draft_id"], prepared.payload["fingerprint"])
        self.finance.pagar(title_id, "10", forma_pagamento="PIX", usuario="outro")
        with self.assertRaisesRegex(ValueError, "saldo.*mudou"):
            assistant.confirm_and_execute_financial(
                challenge.token, prepared.payload["draft_id"], prepared.payload["fingerprint"]
            )
        self.assertEqual(len(self.finance.listar_pagamentos(title_id)), 1)

    def test_permissao_real_e_token_de_uso_unico(self):
        assistant = self._assistant(_Model("financeiro.preparar_titulo", {
            "title_type": "RECEBER", "amount": "10", "due_date": "2026-09-10",
        }), permissions=())
        self.assertFalse(assistant.ask("Prepare").tool_results[0].success)

        assistant = self._assistant(_Model("financeiro.preparar_titulo", {
            "title_type": "RECEBER", "amount": "10", "due_date": "2026-09-10",
        }))
        prepared, _result = self._prepare_and_confirm(assistant)
        with self.assertRaisesRegex(PermissionError, "já foi utilizada"):
            assistant.confirm_and_execute_financial(
                "token-invalido", prepared.payload["draft_id"], prepared.payload["fingerprint"]
            )

    def test_replay_duravel_nao_duplica_e_colisao_e_bloqueada(self):
        values = dict(
            tipo="RECEBER", valor="99.90", data_vencimento="2026-09-10",
            usuario="nabi", idempotency_key="nabi:financial:duravel",
            operation_fingerprint="a" * 64,
        )
        first = self.finance.criar_titulo_assistido(**values)
        second = self.finance.criar_titulo_assistido(**values)
        self.assertEqual(first["title_id"], second["title_id"])
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(len(self.finance.listar_titulos(tipo="RECEBER")), 1)
        with self.assertRaisesRegex(PermissionError, "outro conteúdo"):
            self.finance.criar_titulo_assistido(**{**values, "operation_fingerprint": "b" * 64})

    def test_falha_no_commit_do_journal_reverte_titulo_e_pagamento(self):
        original = self.finance.operation_journal.commit
        self.finance.operation_journal.commit = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("falha journal"))
        try:
            with self.assertRaisesRegex(RuntimeError, "falha journal"):
                self.finance.criar_titulo_assistido(
                    tipo="PAGAR", valor="30", data_vencimento="2026-09-10",
                    usuario="nabi", idempotency_key="nabi:financial:rollback-create",
                    operation_fingerprint="c" * 64,
                )
            self.assertEqual(self.finance.listar_titulos(tipo="PAGAR"), [])

            title_id = self.finance.criar_titulo(
                tipo="PAGAR", valor="40", data_vencimento="2026-09-10", usuario="setup"
            )
            with self.assertRaisesRegex(RuntimeError, "falha journal"):
                self.finance.baixar_titulo_assistido(
                    title_id, "20", forma_pagamento="PIX", usuario="nabi",
                    idempotency_key="nabi:financial:rollback-pay",
                    operation_fingerprint="d" * 64,
                )
            self.assertEqual(self.finance.listar_pagamentos(title_id), [])
            self.assertEqual(self.finance.saldo_titulo(title_id), 40.00)
        finally:
            self.finance.operation_journal.commit = original

    def test_replay_duravel_da_baixa_nao_cria_segundo_pagamento(self):
        title_id = self.finance.criar_titulo(
            tipo="RECEBER", valor="80", data_vencimento="2026-09-10", usuario="setup"
        )
        values = dict(
            forma_pagamento="PIX", usuario="nabi",
            idempotency_key="nabi:financial:pay-replay",
            operation_fingerprint="e" * 64,
        )
        first = self.finance.baixar_titulo_assistido(title_id, "30", **values)
        second = self.finance.baixar_titulo_assistido(title_id, "30", **values)
        self.assertEqual(first["payment_id"], second["payment_id"])
        self.assertTrue(second["idempotent_replay"])
        self.assertEqual(len(self.finance.listar_pagamentos(title_id)), 1)
        self.assertEqual(self.finance.saldo_titulo(title_id), 50.00)
        with self.db.session() as connection:
            row = connection.execute(
                "SELECT status,operation_kind,username FROM assistant_operation_journal "
                "WHERE idempotency_key='nabi:financial:pay-replay'"
            ).fetchone()
        self.assertEqual(tuple(row), ("COMMITTED", "FINANCIAL_SETTLEMENT", "nabi"))

    def test_replay_nao_reemite_evento_pos_commit(self):
        events = SimpleNamespace(calls=[])
        events.financial_event = lambda event: events.calls.append(event)
        actions = FinancialActionService(self.container.financial_actions._gateway, events)
        context = ActionContext("nabi", ActionOrigin.AI, request_id="draft-event")
        command = CreateFinancialTitleCommand("15.00", date(2026, 9, 10))
        first = actions.create_receivable(
            command, context=context, confirmed=True, operation_fingerprint="f" * 64
        )
        second = actions.create_receivable(
            command, context=context, confirmed=True, operation_fingerprint="f" * 64
        )
        self.assertEqual(first.title_id, second.title_id)
        self.assertEqual(len(events.calls), 1)


if __name__ == "__main__": unittest.main()
