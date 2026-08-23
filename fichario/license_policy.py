from __future__ import annotations

from dataclasses import dataclass

from licensing.models import LicenseDecision, LicenseEdition


@dataclass(frozen=True, slots=True)
class FicharioLicensePolicy:
    """Valida somente declaracoes assinadas; configuracao local nao concede acesso."""

    REQUIRED_FEATURES = frozenset({"fichario", "qt", "commercial", "financial"})
    decision: LicenseDecision

    @property
    def operational(self) -> bool:
        payload = self.decision.payload
        return bool(
            self.decision.operational
            and payload is not None
            and payload.edition is LicenseEdition.FICHARIO
            and self.REQUIRED_FEATURES.issubset(payload.features)
            and "fiscal" not in payload.features
        )

    def require(self) -> None:
        if not self.operational:
            raise PermissionError(self.message)

    @property
    def message(self) -> str:
        payload = self.decision.payload
        if not self.decision.operational or payload is None:
            reasons = {
                "LICENSE_MISSING": "Nenhuma licença foi instalada.",
                "LICENSE_INVALID": "A licença instalada é inválida.",
                "MACHINE_MISMATCH": "A licença pertence a outra máquina.",
                "EXPIRED": "A licença e o prazo de tolerância venceram.",
                "CLOCK_ROLLBACK": "O relógio da máquina precisa ser verificado.",
            }
            return reasons.get(
                self.decision.reason,
                "A licença FICHÁRIO não está disponível para uso.",
            )
        if payload.edition is not LicenseEdition.FICHARIO:
            return "Esta instalacao exige uma licenca assinada da edicao FICHARIO."
        if self.REQUIRED_FEATURES.difference(payload.features):
            return "A licenca FICHARIO nao possui todos os recursos assinados obrigatorios."
        if "fiscal" in payload.features:
            return "A edicao FICHARIO nao aceita capacidade fiscal."
        return "Licenca FICHARIO valida."
