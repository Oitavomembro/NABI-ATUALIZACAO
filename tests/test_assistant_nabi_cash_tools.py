from decimal import Decimal
from types import SimpleNamespace

from assistant_nabi import AssistantActor, ReadOnlyToolRegistry, ToolRequest
from assistant_nabi.cash_tools import register_cash_read_tools


class Permissions:
    def __init__(self, allowed=True): self.allowed = allowed
    def allows(self, actor, module, action):
        return self.allowed and module == "caixa" and action == "view"


class Audit:
    def record(self, **event): pass


class Service:
    def current(self):
        session = SimpleNamespace(
            id=7, opened_at="2026-08-24 08:00:00", opening_balance=Decimal("100")
        )
        return SimpleNamespace(
            session=session, is_open=True, expected_cash=Decimal("180"),
            cash_sales=Decimal("50"), pix_sales=Decimal("20"),
            card_sales=Decimal("10"), other_sales=Decimal("0"),
            cash_receipts=Decimal("15"), supplies=Decimal("5"),
            withdrawals=Decimal("20"), movements=(SimpleNamespace(note="segredo"),),
        )


def make_registry(factory, *, allowed=True):
    registry = ReadOnlyToolRegistry(permissions=Permissions(allowed), audit=Audit())
    register_cash_read_tools(registry, factory)
    return registry


def test_caixa_atual_usa_ator_autenticado_e_minimiza_payload():
    seen = []
    registry = make_registry(lambda actor: seen.append(actor) or Service())
    actor = AssistantActor("maria", "OPERADOR", "sessao-real")
    result = registry.execute(ToolRequest("caixa.consultar_atual", {}), actor=actor)
    assert result.success
    assert seen == [actor]
    assert result.payload["session_id"] == 7
    assert result.payload["expected_cash"] == "180.00"
    assert "movements" not in result.payload
    assert "segredo" not in str(result.payload)


def test_caixa_permissao_negada_nao_cria_servico():
    calls = []
    registry = make_registry(lambda actor: calls.append(actor) or Service(), allowed=False)
    result = registry.execute(
        ToolRequest("caixa.consultar_atual", {}),
        actor=AssistantActor("maria", "OPERADOR", "sessao-real"),
    )
    assert not result.success
    assert calls == []


def test_caixa_ausente_nao_registra_ferramenta():
    registry = make_registry(None)
    result = registry.execute(
        ToolRequest("caixa.consultar_atual", {}),
        actor=AssistantActor("maria", "OPERADOR", "sessao-real"),
    )
    assert not result.success
    assert result.message == "Ferramenta não registrada."


def test_ferramenta_caixa_nao_expoe_mutacoes_ou_observacoes():
    source = __import__("pathlib").Path("assistant_nabi/cash_tools.py").read_text("utf-8")
    for forbidden in (".open(", ".close(", "register_movement", "movements", "note"):
        assert forbidden not in source
