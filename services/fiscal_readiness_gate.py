from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FiscalReadinessResult:
    problems: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.problems


class FiscalReadinessGate:
    """Portão único, local e fail-closed para operações fiscais oficiais."""

    def __init__(
        self, fiscal_service: Any, catalog_service: Any | None = None,
        regulatory_service: Any | None = None,
    ) -> None:
        self.fiscal_service = fiscal_service
        self.catalog_service = catalog_service
        self.regulatory_service = regulatory_service

    def evaluate(
        self, *, operation: str, model: str, password: str,
        series: int | None = None, require_catalog: bool = False,
        require_numbering: bool = False, check_revocation: bool = True,
    ) -> FiscalReadinessResult:
        service = self.fiscal_service
        config = service.load_config()
        problems = list(service.validate_ready(operation=operation, model=model))
        if self.regulatory_service is None:
            problems.append("O catálogo regulatório fiscal não está configurado.")
        else:
            regulatory = self.regulatory_service.audit(
                environment=str(config.get("environment") or "HOMOLOGACAO")
            )
            problems.extend(regulatory.problems)
        certificate_path = str(config.get("certificate_path") or "").strip()
        try:
            certificate = service.inspect_certificate(certificate_path, password)
            configured = service._normalize_cnpj(config.get("cnpj"))
            if certificate.expired:
                problems.append("O certificado A1 está expirado ou ainda não é válido.")
            if not certificate.document:
                problems.append("O CNPJ não foi identificado no certificado A1.")
            elif configured and certificate.document != configured:
                problems.append("O CNPJ do certificado A1 não corresponde ao emitente configurado.")
            trust = service.validate_certificate_trust(certificate_path, password)
            if not trust.trusted:
                problems.append(f"Cadeia ICP-Brasil não confirmada: {trust.message}")
            if check_revocation:
                revocation = service.check_certificate_revocation(certificate_path, password)
                if not revocation.good:
                    problems.append(f"Situação de revogação não confirmada: {revocation.message}")
        except Exception as exc:
            problems.append(str(exc))

        if require_numbering:
            if series is None:
                problems.append("A série fiscal é obrigatória para validar a numeração.")
            else:
                try:
                    validate_series = getattr(service, "validate_taxpayer_series", None)
                    if validate_series is not None:
                        validate_series(int(series), model=model)
                    elif not 0 <= int(series) <= 999:
                        raise ValueError("Série fiscal inválida.")
                except (TypeError, ValueError) as exc:
                    problems.append(str(exc))
                else:
                    scope = service.numbering_scope(
                        model=model, series=int(series), environment=config.get("environment")
                    )
                    if not scope.get("initialized"):
                        problems.append(
                            "A numeração fiscal ainda não foi inicializada para este ambiente, modelo e série."
                        )

        if require_catalog:
            if self.catalog_service is None:
                problems.append("O auditor de prontidão do catálogo fiscal não está configurado.")
            else:
                crt = service.TAX_REGIME_CODES.get(
                    str(config.get("tax_regime") or "").upper(), 0
                )
                report = self.catalog_service.audit(crt=crt)
                if not report.total:
                    problems.append("O catálogo não possui mercadorias fiscais ativas.")
                elif report.blocked:
                    problems.append(
                        f"O catálogo possui {report.blocked} produto(s) com pendência fiscal."
                    )
        return FiscalReadinessResult(tuple(dict.fromkeys(p for p in problems if p)))

    def require(self, **kwargs: Any) -> None:
        result = self.evaluate(**kwargs)
        if not result.ready:
            raise ValueError("; ".join(result.problems))
