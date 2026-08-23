from __future__ import annotations

from enum import Enum

from .models import LicenseDecision, LicenseState


class Capability(str, Enum):
    ACTIVATE = "activate"
    DIAGNOSTIC = "diagnostic"
    BACKUP = "backup"
    EXPORT = "export"
    LEGACY = "legacy"
    QT = "qt"
    COMMERCIAL_WRITE = "commercial_write"
    FINANCIAL_WRITE = "financial_write"
    ADMIN_WRITE = "admin_write"
    FISCAL_WORKER = "fiscal_worker"
    FISCAL_WRITE = "fiscal_write"


class LicenseGate:
    RESTRICTED = {
        Capability.ACTIVATE, Capability.DIAGNOSTIC, Capability.BACKUP, Capability.EXPORT,
    }
    FEATURE_MAP = {
        Capability.LEGACY: "legacy",
        Capability.QT: "qt",
        Capability.COMMERCIAL_WRITE: "commercial",
        Capability.FINANCIAL_WRITE: "financial",
        Capability.ADMIN_WRITE: "admin",
        Capability.FISCAL_WORKER: "fiscal",
        Capability.FISCAL_WRITE: "fiscal",
    }

    def __init__(self, decision: LicenseDecision) -> None:
        self.decision = decision

    def allows(self, capability: Capability) -> bool:
        if capability in self.RESTRICTED:
            return True
        if not self.decision.operational or self.decision.payload is None:
            return False
        feature = self.FEATURE_MAP.get(capability)
        return feature is None or feature in self.decision.payload.features

    def require(self, capability: Capability) -> None:
        if not self.allows(capability):
            raise PermissionError(
                f"Licença {self.decision.state.value}: operação {capability.value} bloqueada."
            )

    @property
    def must_block_workers(self) -> bool:
        return not self.allows(Capability.FISCAL_WORKER)
