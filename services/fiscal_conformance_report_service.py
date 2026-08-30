from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

from services.fiscal_operation_resolver import FiscalOperationResolver
from services.fiscal_regulatory_catalog_service import FiscalRegulatoryCatalogService
from services.fiscal_rtc_resolver import FiscalRtcResolver
from services.fiscal_tax_rule_service import FiscalTaxRuleService


@dataclass(frozen=True, slots=True)
class FiscalConformanceReport:
    schema: str
    jurisdiction: str
    models: tuple[str, ...]
    operational_environment: str
    production_blocked: bool
    supported_operations: tuple[str, ...]
    blocked_operations: tuple[str, ...]
    automated_sale_cfops: tuple[str, ...]
    supported_icms_codes: tuple[str, ...]
    rtc_profiles: tuple[str, ...]
    mandatory_manual_gates: tuple[str, ...]
    regulatory_problems: tuple[str, ...]
    snapshot_sha256: str = ""

    @property
    def ready_for_local_homologation(self) -> bool:
        return not self.regulatory_problems


class FiscalConformanceReportService:
    """Inventaria cobertura real; não presume conformidade nem altera configuração."""

    SCHEMA = "nabicode.fiscal-conformance-report.v1"
    MANUAL_GATES = (
        "aprovação das regras por contador responsável",
        "credenciamento e autorização do contribuinte na SEFAZ",
        "certificado A1 válido e correspondente ao CNPJ",
        "execução da matriz adversarial em homologação",
        "aprovação formal do dossiê antes de produção",
    )

    def __init__(self, regulatory_service: Any | None = None) -> None:
        self.regulatory_service = regulatory_service or FiscalRegulatoryCatalogService()

    @staticmethod
    def _sale_cfops() -> tuple[str, ...]:
        return tuple(sorted(FiscalOperationResolver._BY_CFOP))

    def snapshot(self) -> FiscalConformanceReport:
        regulatory = self.regulatory_service.audit(environment="HOMOLOGACAO")
        report = FiscalConformanceReport(
            schema=self.SCHEMA,
            jurisdiction=regulatory.jurisdiction,
            models=("55", "65"),
            operational_environment="HOMOLOGACAO",
            production_blocked=not regulatory.production_approved,
            supported_operations=regulatory.supported_operations,
            blocked_operations=regulatory.unsupported_operations,
            automated_sale_cfops=self._sale_cfops(),
            supported_icms_codes=tuple(sorted(FiscalTaxRuleService.VALID_ICMS_CODES)),
            rtc_profiles=(
                f"000/{FiscalRtcResolver.REGULAR_CLASSIFICATION}:NACIONAL",
                f"410/{FiscalRtcResolver.EXPORT_CLASSIFICATION}:EXPORTACAO",
            ),
            mandatory_manual_gates=self.MANUAL_GATES,
            regulatory_problems=regulatory.problems,
        )
        payload = asdict(report)
        payload.pop("snapshot_sha256")
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return FiscalConformanceReport(
            **payload, snapshot_sha256=hashlib.sha256(canonical).hexdigest().upper()
        )

    def export_json(self) -> str:
        return json.dumps(
            asdict(self.snapshot()), ensure_ascii=False, sort_keys=True, indent=2
        )
