from __future__ import annotations

from types import SimpleNamespace

import pytest

from assistant_nabi.technical_onboarding import NabiTechnicalOnboardingService
from licensing.gate import LicenseGate
from licensing.models import LicenseDecision, LicenseState


class Readiness:
    def __init__(self, value): self.value = value; self.calls = 0
    def snapshot(self): self.calls += 1; return self.value


def gate(*, operational=True, features=("assistant",)):
    payload = SimpleNamespace(features=features) if operational else None
    state = LicenseState.ACTIVE if operational else LicenseState.INVALID
    return LicenseGate(LicenseDecision(state, "TEST", "NABI2-TEST", payload))


def complete_snapshot(*, fiscal_enabled=False, fiscal_ready=False):
    return {
        "company": {"confirmed": True, "cnpj": "12.345.678/0001-90"},
        "tax_regime": {"confirmed": True, "value": "SIMPLES_NACIONAL"},
        "users": {"admin_ready": True, "access_reviewed": True},
        "cash": {"configured": True},
        "printing": {"configured": True, "test_confirmed": True},
        "backup": {"destination_configured": True, "restore_test_confirmed": True},
        "fiscal": {
            "profile_enabled": fiscal_enabled,
            "readiness_checked": fiscal_ready,
            "ready": fiscal_ready,
        },
    }


def test_onboarding_nao_inicia_antes_da_licenca_nem_sem_recurso_nabi():
    for actual_gate in (gate(operational=False), gate(features=("commercial",))):
        readiness = Readiness(complete_snapshot())
        with pytest.raises(PermissionError):
            NabiTechnicalOnboardingService(actual_gate, readiness).checklist()
        assert readiness.calls == 0


def test_roteiro_deterministico_funciona_sem_modelo_gguf_e_pula_fiscal_desabilitado():
    readiness = Readiness(complete_snapshot())
    service = NabiTechnicalOnboardingService(gate(), readiness)
    first = service.checklist()
    second = service.checklist()
    assert first == second
    assert first.completed is True
    assert first.model_required is False
    assert first.deterministic is True
    assert first.mutation_performed is False
    assert first.fiscal_release_authorized is False
    assert first.steps[-1].status == "SKIPPED"


def test_roteiro_ordena_empresa_regime_usuarios_caixa_impressao_backup_e_so_checklist_fiscal():
    snapshot = complete_snapshot(fiscal_enabled=True, fiscal_ready=False)
    snapshot["company"]["confirmed"] = False
    checklist = NabiTechnicalOnboardingService(gate(), Readiness(snapshot)).checklist()
    assert tuple(step.step_id for step in checklist.steps) == (
        "EMPRESA", "REGIME", "USUARIOS", "CAIXA", "IMPRESSAO", "BACKUP",
        "FISCAL_READINESS",
    )
    assert checklist.next_step_id == "EMPRESA"
    assert checklist.completed is False
    fiscal = checklist.steps[-1]
    assert fiscal.status == "PENDING"
    assert fiscal.human_confirmation_required is True
    assert checklist.fiscal_release_authorized is False

    ready = NabiTechnicalOnboardingService(
        gate(), Readiness(complete_snapshot(fiscal_enabled=True, fiscal_ready=True))
    ).checklist()
    assert ready.steps[-1].status == "READY"
    assert ready.completed is True
    assert ready.fiscal_release_authorized is False


def test_regime_nao_reconhecido_nunca_e_inferido_como_pronto():
    snapshot = complete_snapshot()
    snapshot["tax_regime"] = {"confirmed": True, "value": "INFERIDO_PELA_IA"}
    checklist = NabiTechnicalOnboardingService(gate(), Readiness(snapshot)).checklist()
    regime = next(step for step in checklist.steps if step.step_id == "REGIME")
    assert regime.status == "PENDING"
    assert "não o infere" in regime.guidance


def test_snapshot_invalido_falha_fechado():
    with pytest.raises(TypeError):
        NabiTechnicalOnboardingService(gate(), Readiness(["não", "é", "mapa"])).checklist()
