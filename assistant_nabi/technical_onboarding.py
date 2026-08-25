"""Roteiro técnico determinístico da Nabi, independente de modelo/GGUF."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from licensing.gate import Capability


@dataclass(frozen=True, slots=True)
class TechnicalOnboardingStep:
    step_id: str
    title: str
    status: str
    guidance: str
    human_confirmation_required: bool


@dataclass(frozen=True, slots=True)
class TechnicalOnboardingChecklist:
    steps: tuple[TechnicalOnboardingStep, ...]
    next_step_id: str
    completed: bool
    deterministic: bool = True
    model_required: bool = False
    mutation_performed: bool = False
    fiscal_release_authorized: bool = False


class NabiTechnicalOnboardingService:
    """Lê prontidão existente; não configura nem libera nenhum módulo."""

    _REGIMES = frozenset({
        "MEI", "SIMPLES_NACIONAL", "LUCRO_PRESUMIDO", "LUCRO_REAL", "OUTRO",
    })

    def __init__(self, license_gate, readiness_port) -> None:
        if license_gate is None or readiness_port is None:
            raise ValueError("Licença e porta de prontidão são obrigatórias.")
        self._license = license_gate
        self._readiness = readiness_port

    @staticmethod
    def _mapping(snapshot: Mapping[str, Any], key: str) -> Mapping[str, Any]:
        value = snapshot.get(key, {})
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _step(step_id: str, title: str, ready: bool, guidance: str) -> TechnicalOnboardingStep:
        return TechnicalOnboardingStep(
            step_id, title, "READY" if ready else "PENDING", guidance,
            human_confirmation_required=not ready,
        )

    def checklist(self) -> TechnicalOnboardingChecklist:
        # A porta não é sequer consultada antes de uma licença operacional com Nabi.
        self._license.require(Capability.ASSISTANT)
        snapshot = self._readiness.snapshot()
        if not isinstance(snapshot, Mapping):
            raise TypeError("A prontidão técnica retornou um formato inválido.")

        company = self._mapping(snapshot, "company")
        cnpj = "".join(character for character in str(company.get("cnpj") or "") if character.isdigit())
        company_ready = bool(company.get("confirmed")) and len(cnpj) == 14

        regime = self._mapping(snapshot, "tax_regime")
        regime_value = str(regime.get("value") or "").strip().upper()
        regime_ready = bool(regime.get("confirmed")) and regime_value in self._REGIMES

        users = self._mapping(snapshot, "users")
        cash = self._mapping(snapshot, "cash")
        printing = self._mapping(snapshot, "printing")
        backup = self._mapping(snapshot, "backup")

        steps = [
            self._step("EMPRESA", "Empresa e CNPJ", company_ready,
                       "Revise e confirme os dados reais da empresa e o CNPJ."),
            self._step("REGIME", "Regime tributário", regime_ready,
                       "Confirme o regime com a contabilidade; a Nabi não o infere."),
            self._step("USUARIOS", "Usuários e acessos",
                       bool(users.get("admin_ready")) and bool(users.get("access_reviewed")),
                       "Crie usuários individualizados e revise apenas as permissões necessárias."),
            self._step("CAIXA", "Caixa inicial", bool(cash.get("configured")),
                       "Confirme a configuração operacional do caixa antes da primeira venda."),
            self._step("IMPRESSAO", "Impressão",
                       bool(printing.get("configured")) and bool(printing.get("test_confirmed")),
                       "Selecione a impressora e confirme uma impressão local de teste."),
            self._step("BACKUP", "Backup",
                       bool(backup.get("destination_configured")) and bool(backup.get("restore_test_confirmed")),
                       "Configure um destino e confirme um teste de restauração sem usar dados reais."),
        ]

        fiscal = self._mapping(snapshot, "fiscal")
        if bool(fiscal.get("profile_enabled")):
            fiscal_ready = bool(fiscal.get("readiness_checked")) and bool(fiscal.get("ready"))
            steps.append(self._step(
                "FISCAL_READINESS", "Checklist fiscal", fiscal_ready,
                "Execute apenas o checklist local de prontidão; nenhuma autorização fiscal é liberada aqui.",
            ))
        else:
            steps.append(TechnicalOnboardingStep(
                "FISCAL_READINESS", "Checklist fiscal", "SKIPPED",
                "Perfil fiscal não habilitado; nenhuma configuração ou liberação foi tentada.", False,
            ))

        pending = next((step.step_id for step in steps if step.status == "PENDING"), "")
        return TechnicalOnboardingChecklist(
            steps=tuple(steps), next_step_id=pending, completed=not pending,
        )
