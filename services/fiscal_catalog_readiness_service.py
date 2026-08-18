from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from services.fiscal_operation_resolver import FiscalOperationResolver
from services.fiscal_product_profile import FiscalProductProfile
from services.fiscal_rtc_resolver import FiscalRtcResolver


@dataclass(frozen=True)
class FiscalCatalogIssue:
    product_id: int
    code: str
    name: str
    message: str


@dataclass(frozen=True)
class FiscalCatalogReport:
    total: int
    ready: int
    issues: tuple[FiscalCatalogIssue, ...]
    ready_product_ids: tuple[int, ...] = ()

    @property
    def blocked(self) -> int:
        return len(self.issues)

    @property
    def is_ready(self) -> bool:
        return self.total > 0 and not self.issues


class FiscalCatalogReadinessService:
    """Audita o catálogo fiscal inteiro sem alterar produtos ou configurações."""

    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self.connection_factory = connection_factory

    def audit(self, *, crt: int) -> FiscalCatalogReport:
        if int(crt) not in {1, 2, 3, 4}:
            raise ValueError("Regime tributário inválido para conferir o catálogo.")
        connection = self.connection_factory()
        try:
            cursor = connection.execute(
                """SELECT id,codigo,nome,ncm,cest,cfop,
                          fiscal_origin,fiscal_csosn,fiscal_icms_cst,fiscal_icms_rate,
                          fiscal_pis_cst,fiscal_pis_rate,fiscal_cofins_cst,fiscal_cofins_rate,
                          fiscal_profile_source,ibs_cbs_cst,ibs_cbs_class,
                          ibs_uf_rate,ibs_city_rate,cbs_rate
                     FROM produtos
                    WHERE COALESCE(ativo,1)=1 AND COALESCE(participa_xml,1)=1
                      AND UPPER(COALESCE(tipo_produto,'MERCADORIA'))<>'SERVICO'
                    ORDER BY nome,id"""
            )
            columns = [column[0] for column in cursor.description]
            products = [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            connection.close()

        issues: list[FiscalCatalogIssue] = []
        ready_product_ids: list[int] = []
        for product in products:
            try:
                profile = FiscalProductProfile.validate_for_regime(
                    product, crt=int(crt), require_rtc=False
                )
                for destination in (1, 2):
                    FiscalOperationResolver.resolve_sale(
                        profile["cfop"], destination=destination, crt=int(crt),
                        csosn=profile["fiscal_csosn"], icms_cst=profile["fiscal_icms_cst"],
                    )
                    FiscalRtcResolver.resolve(profile, destination=destination)
                ready_product_ids.append(int(product["id"]))
            except ValueError as exc:
                issues.append(FiscalCatalogIssue(
                    product_id=int(product["id"]),
                    code=str(product.get("codigo") or product["id"]),
                    name=str(product.get("nome") or "PRODUTO"),
                    message=str(exc),
                ))
        return FiscalCatalogReport(
            total=len(products), ready=len(products) - len(issues), issues=tuple(issues),
            ready_product_ids=tuple(ready_product_ids),
        )
