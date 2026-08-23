from __future__ import annotations

import unittest

from assistant_nabi import (
    AssistantActor,
    AdminAssistantAuditAdapter,
    CapabilityLevel,
    CurrentSessionPermissionAdapter,
    ParameterDefinition,
    ParameterType,
    ReadOnlyToolRegistry,
    ToolDefinition,
    ToolKind,
    ToolRequest,
    ToolSchema,
)


class Permissions:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.calls = []

    def allows(self, actor, module, action):
        self.calls.append((actor.username, module, action))
        return self.allowed


class Audit:
    def __init__(self):
        self.events = []

    def record(self, **event):
        self.events.append(event)


class Reader:
    def __init__(self, result=None, error=None):
        self.result = result or {"items": []}
        self.error = error
        self.calls = []

    def execute(self, request, *, actor):
        self.calls.append((request, actor))
        if self.error:
            raise self.error
        return self.result


class NabiPhaseZeroTests(unittest.TestCase):
    def setUp(self):
        self.actor = AssistantActor("operador", "OPERADOR", "sessao-1")
        self.permissions = Permissions()
        self.audit = Audit()
        self.registry = ReadOnlyToolRegistry(
            permissions=self.permissions, audit=self.audit
        )
        self.definition = ToolDefinition(
            "produtos.pesquisar", ToolKind.READ, CapabilityLevel.READ,
            "produtos", "view", ToolSchema((
                ParameterDefinition("term", ParameterType.TEXT, max_length=100),
                ParameterDefinition("limit", ParameterType.INTEGER),
            )),
        )

    def test_executa_somente_consulta_registrada_permitida_e_audita(self):
        reader = Reader({"items": [{"product_id": 7}]})
        self.registry.register(self.definition, reader)
        request = ToolRequest("produtos.pesquisar", {"term": "cafe"}, "req-1")
        result = self.registry.execute(request, actor=self.actor)
        self.assertTrue(result.success)
        self.assertEqual(result.payload["items"][0]["product_id"], 7)
        self.assertEqual(self.permissions.calls[-1], ("operador", "produtos", "view"))
        self.assertEqual(len(reader.calls), 1)
        self.assertEqual(len(self.audit.events), 1)

    def test_ferramenta_desconhecida_falha_fechada_e_e_auditada(self):
        result = self.registry.execute(
            ToolRequest("sistema.executar_sql", {}, "req-2"), actor=self.actor
        )
        self.assertFalse(result.success)
        self.assertEqual(result.message, "Ferramenta não registrada.")
        self.assertEqual(len(self.audit.events), 1)

    def test_permissao_negada_nao_chama_ferramenta(self):
        self.permissions.allowed = False
        reader = Reader()
        self.registry.register(self.definition, reader)
        result = self.registry.execute(
            ToolRequest("produtos.pesquisar", {}, "req-3"), actor=self.actor
        )
        self.assertFalse(result.success)
        self.assertEqual(result.message, "Permissão insuficiente.")
        self.assertEqual(reader.calls, [])
        self.assertEqual(len(self.audit.events), 1)

    def test_fase_zero_recusa_ferramenta_mutavel(self):
        definition = ToolDefinition(
            "vendas.confirmar", ToolKind.MUTATION,
            CapabilityLevel.REINFORCED_CONFIRMATION, "vendas", "create",
        )
        with self.assertRaisesRegex(ValueError, "somente ferramentas de leitura"):
            self.registry.register(definition, Reader())

    def test_falha_interna_nao_vaza_detalhes_e_e_auditada(self):
        self.registry.register(self.definition, Reader(error=RuntimeError("segredo interno")))
        result = self.registry.execute(
            ToolRequest("produtos.pesquisar", {}, "req-4"), actor=self.actor
        )
        self.assertFalse(result.success)
        self.assertNotIn("segredo", result.message)
        self.assertEqual(len(self.audit.events), 1)

    def test_parametros_sao_imutaveis(self):
        request = ToolRequest("produtos.pesquisar", {"term": "cafe"})
        with self.assertRaises(TypeError):
            request.parameters["term"] = "alterado"

    def test_definicao_inconsistente_e_rejeitada(self):
        with self.assertRaisesRegex(ValueError, "capacidade READ"):
            ToolDefinition(
                "produtos.pesquisar", ToolKind.READ, CapabilityLevel.DRAFT, "produtos"
            )

    def test_schema_rejeita_campo_inventado_antes_do_servico(self):
        reader = Reader()
        self.registry.register(self.definition, reader)
        result = self.registry.execute(
            ToolRequest("produtos.pesquisar", {"sql": "DROP TABLE produtos"}),
            actor=self.actor,
        )
        self.assertFalse(result.success)
        self.assertEqual(result.message, "Parâmetro não permitido: sql.")
        self.assertEqual(reader.calls, [])
        self.assertEqual(len(self.audit.events), 1)

    def test_schema_rejeita_tipo_e_tamanho_incorretos(self):
        reader = Reader()
        self.registry.register(self.definition, reader)
        wrong_type = self.registry.execute(
            ToolRequest("produtos.pesquisar", {"limit": "30"}), actor=self.actor
        )
        too_long = self.registry.execute(
            ToolRequest("produtos.pesquisar", {"term": "x" * 101}), actor=self.actor
        )
        self.assertFalse(wrong_type.success)
        self.assertFalse(too_long.success)
        self.assertEqual(reader.calls, [])

    def test_schema_exige_parametro_obrigatorio_e_recusa_duplicado(self):
        schema = ToolSchema((ParameterDefinition(
            "customer_id", ParameterType.INTEGER, required=True
        ),))
        with self.assertRaisesRegex(ValueError, "obrigatório ausente"):
            schema.validate({})
        with self.assertRaisesRegex(ValueError, "duplicados"):
            ToolSchema((
                ParameterDefinition("term", ParameterType.TEXT),
                ParameterDefinition("term", ParameterType.TEXT),
            ))

    def test_decimal_deve_ser_textual_finito(self):
        parameter = ParameterDefinition("amount", ParameterType.DECIMAL_TEXT)
        parameter.validate("10,50")
        for invalid in (10.5, "NaN", "Infinity", "texto"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "decimal"):
                    parameter.validate(invalid)


class SecurityUser:
    def __init__(self, username="operador", profile="OPERADOR", active=True):
        self.username = username
        self.profile = profile
        self.active = active


class SecuritySession:
    def __init__(self, user=None):
        self.user = user or SecurityUser()


class Security:
    def __init__(self):
        self.session = SecuritySession()
        self.expired = False
        self.allowed = True
        self.require_calls = []

    def is_expired(self):
        return self.expired

    def require(self, module, action):
        self.require_calls.append((module, action))
        return self.allowed


class ExistingAuditService:
    def __init__(self):
        self.events = []

    def record_event(self, *args, **kwargs):
        self.events.append((args, kwargs))


class NabiAdapterTests(unittest.TestCase):
    def test_identidade_e_derivada_da_sessao_real(self):
        security = Security()
        adapter = CurrentSessionPermissionAdapter(security, session_id="sessao-qt-1")
        actor = adapter.current_actor()
        self.assertEqual(actor, AssistantActor("operador", "OPERADOR", "sessao-qt-1"))
        self.assertTrue(adapter.allows(actor, "produtos", "view"))
        self.assertEqual(security.require_calls, [("produtos", "view")])

    def test_identidade_forjada_sessao_expirada_e_usuario_inativo_falham_fechado(self):
        security = Security()
        adapter = CurrentSessionPermissionAdapter(security, session_id="sessao-real")
        forged = AssistantActor("admin", "ADMIN", "sessao-falsa")
        self.assertFalse(adapter.allows(forged, "produtos", "view"))
        self.assertEqual(security.require_calls, [])

        security.expired = True
        self.assertFalse(
            adapter.allows(
                AssistantActor("operador", "OPERADOR", "sessao-real"),
                "produtos",
                "view",
            )
        )
        security.expired = False
        security.session.user.active = False
        with self.assertRaisesRegex(PermissionError, "inativo"):
            adapter.current_actor()

    def test_negacao_do_security_service_e_respeitada(self):
        security = Security()
        security.allowed = False
        adapter = CurrentSessionPermissionAdapter(security, session_id="sessao-real")
        self.assertFalse(adapter.allows(adapter.current_actor(), "clientes", "view"))

    def test_auditoria_nao_grava_parametros_payload_ou_segredos(self):
        service = ExistingAuditService()
        adapter = AdminAssistantAuditAdapter(service)
        actor = AssistantActor("operador", "OPERADOR", "sessao-1")
        request = ToolRequest(
            "clientes.pesquisar", {"term": "CPF-SECRETO"}, "req-10"
        )
        result = self._result(request)
        adapter.record(actor=actor, request=request, result=result)
        args, kwargs = service.events[0]
        serialized = repr((args, kwargs))
        self.assertIn("req-10", serialized)
        self.assertNotIn("CPF-SECRETO", serialized)
        self.assertNotIn("resultado sensível", serialized)

    @staticmethod
    def _result(request):
        from assistant_nabi import ToolResult

        return ToolResult(
            request.request_id,
            request.tool_name,
            True,
            {"customer_name": "resultado sensível"},
        )


if __name__ == "__main__":
    unittest.main()
