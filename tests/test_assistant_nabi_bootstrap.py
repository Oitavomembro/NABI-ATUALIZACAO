from __future__ import annotations

import unittest
from dataclasses import dataclass

from assistant_nabi import ModelReply, ToolRequest, create_read_only_assistant


@dataclass(frozen=True)
class User:
    username: str = "operador"
    profile: str = "OPERADOR"
    active: bool = True


@dataclass
class Session:
    user: User


class Security:
    def __init__(self, *, authenticated=True, allowed=True):
        self.session = Session(User()) if authenticated else None
        self.allowed = allowed

    def is_expired(self):
        return self.session is None

    def require(self, module, action):
        return self.allowed and module in {"produtos", "clientes"} and action == "view"


class Audit:
    def __init__(self):
        self.events = []

    def record_event(self, module, action, **details):
        self.events.append((module, action, details))


class Queries:
    def __init__(self):
        self.calls = []

    def search_products(self, term, *, limit):
        self.calls.append(("products", term, limit))
        return ()

    def search_customers(self, term, *, limit):
        self.calls.append(("customers", term, limit))
        return ()

    def product_stock(self, product_id):
        raise AssertionError("não usado neste teste")


class Model:
    def __init__(self):
        self.calls = []

    def respond(self, message, *, available_tools):
        self.calls.append((message, tuple(tool.name for tool in available_tools)))
        return ModelReply(
            "Consulta concluída.",
            (ToolRequest("produtos.pesquisar", {"term": "café"}, "req-1"),),
        )


class NabiBootstrapTests(unittest.TestCase):
    def create(self, *, authenticated=True, allowed=True):
        model = Model()
        queries = Queries()
        audit = Audit()
        service = create_read_only_assistant(
            model=model,
            query_service=queries,
            security_service=Security(authenticated=authenticated, allowed=allowed),
            audit_service=audit,
            session_id="qt-session-1",
        )
        return service, model, queries, audit

    def test_compoe_consulta_com_permissao_e_auditoria_oficiais(self):
        service, model, queries, audit = self.create()
        turn = service.ask("Procure café")
        self.assertFalse(turn.safe_failure)
        self.assertTrue(turn.tool_results[0].success)
        self.assertEqual(queries.calls, [("products", "café", 20)])
        self.assertEqual(model.calls[0][1], (
            "produtos.pesquisar",
            "produtos.consultar_estoque",
            "clientes.pesquisar",
        ))
        self.assertEqual(audit.events[0][0:2], ("IA_NABI", "CONSULTA_FERRAMENTA"))
        self.assertIn("session_id=qt-session-1", audit.events[0][2]["details"])

    def test_sem_sessao_modelo_nao_e_chamado(self):
        service, model, queries, audit = self.create(authenticated=False)
        turn = service.ask("Procure café")
        self.assertTrue(turn.safe_failure)
        self.assertEqual(model.calls, [])
        self.assertEqual(queries.calls, [])
        self.assertEqual(audit.events, [])

    def test_sem_permissao_modelo_nao_recebe_ferramentas_e_nao_consulta(self):
        service, model, queries, audit = self.create(allowed=False)
        turn = service.ask("Procure café")
        self.assertFalse(turn.safe_failure)
        self.assertEqual(model.calls[0][1], ())
        self.assertFalse(turn.tool_results[0].success)
        self.assertEqual(queries.calls, [])
        self.assertEqual(audit.events[0][2]["result"], "NEGADO_OU_FALHA")

    def test_recusa_dependencias_ausentes_e_sessao_sem_identificador(self):
        base = {
            "model": Model(),
            "query_service": Queries(),
            "security_service": Security(),
            "audit_service": Audit(),
            "session_id": "sessao",
        }
        for name in ("model", "query_service", "security_service", "audit_service"):
            parameters = dict(base)
            parameters[name] = None
            with self.subTest(name=name), self.assertRaises(ValueError):
                create_read_only_assistant(**parameters)
        base["session_id"] = "  "
        with self.assertRaisesRegex(ValueError, "sessão"):
            create_read_only_assistant(**base)


if __name__ == "__main__":
    unittest.main()
