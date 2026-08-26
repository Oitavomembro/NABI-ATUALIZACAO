from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


MONEY = Decimal("0.01")
RATE = Decimal("0.000001")


def _decimal(value: Decimal | int | str, *, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{field} inválido.") from exc
    if not result.is_finite():
        raise ValueError(f"{field} deve ser finito.")
    return result


@dataclass(frozen=True)
class TaxProjectionRule:
    """Parâmetros externos confirmados para uma segregação do Simples.

    A regra não decide enquadramento, anexo ou tratamento tributário. Esses dados
    precisam vir de uma configuração versionada e confirmada pela contabilidade.
    """

    rule_id: str
    version: str
    annex: str
    nominal_rate_percent: Decimal
    deduction: Decimal
    effective_from: date
    effective_until: date | None
    source: str
    confirmed_by: str
    confirmed_at: datetime


@dataclass(frozen=True)
class TaxRevenueSegment:
    code: str
    description: str
    revenue: Decimal
    rule: TaxProjectionRule


@dataclass(frozen=True)
class TaxSegmentProjection:
    code: str
    description: str
    annex: str
    revenue: Decimal
    nominal_rate_percent: Decimal
    deduction: Decimal
    effective_rate_percent: Decimal
    estimated_tax: Decimal
    rule_id: str
    rule_version: str
    source: str


@dataclass(frozen=True)
class MonthlyTaxProjection:
    regime: str
    recognition_basis: str
    period_start: date
    period_end: date
    calculated_through: date
    rbt12: Decimal
    revenue_to_date: Decimal
    estimated_tax_to_date: Decimal
    projected_month_revenue: Decimal
    projected_month_tax: Decimal
    recommended_reserve: Decimal
    weighted_effective_rate_percent: Decimal
    segments: tuple[TaxSegmentProjection, ...]
    warnings: tuple[str, ...]
    generated_at: datetime
    official_assessment: bool = False


class TaxProjectionService:
    """Projeção gerencial auditável, sem declarar nem transmitir tributos."""

    SUPPORTED_REGIME = "SIMPLES_NACIONAL"
    VALID_RECOGNITION = {"CAIXA", "COMPETENCIA"}

    def project_simple_national(
        self,
        *,
        period_start: date,
        period_end: date,
        calculated_through: date,
        rbt12: Decimal | int | str,
        segments: Iterable[TaxRevenueSegment],
        recognition_basis: str,
        reserve_margin_percent: Decimal | int | str = Decimal("5"),
    ) -> MonthlyTaxProjection:
        if period_start > period_end:
            raise ValueError("O início do período deve anteceder o fim.")
        if not period_start <= calculated_through <= period_end:
            raise ValueError("A data da consulta deve pertencer ao período.")
        recognition = str(recognition_basis or "").strip().upper()
        if recognition not in self.VALID_RECOGNITION:
            raise ValueError("Regime de reconhecimento deve ser CAIXA ou COMPETENCIA.")
        accumulated = _decimal(rbt12, field="RBT12")
        if accumulated < 0:
            raise ValueError("RBT12 não pode ser negativo.")
        margin = _decimal(reserve_margin_percent, field="Margem de reserva")
        if margin < 0 or margin > 100:
            raise ValueError("Margem de reserva deve ficar entre 0% e 100%.")

        rows = tuple(segments)
        if not rows:
            raise ValueError("Informe ao menos uma segregação de receita.")
        projected_segments: list[TaxSegmentProjection] = []
        warnings = [
            "Projeção gerencial: não substitui a apuração oficial no PGDAS-D nem a revisão contábil."
        ]
        if accumulated == 0:
            warnings.append(
                "RBT12 igual a zero: foi usado denominador 1; confirme a regra de início de atividade."
            )
        denominator = accumulated if accumulated > 0 else Decimal("1")

        seen_codes: set[str] = set()
        for item in rows:
            code = str(item.code or "").strip().upper()
            if not code or code in seen_codes:
                raise ValueError("Cada segregação precisa de código único.")
            seen_codes.add(code)
            revenue = _decimal(item.revenue, field=f"Receita {code}")
            if revenue < 0:
                raise ValueError(f"Receita {code} não pode ser negativa.")
            rule = item.rule
            self._validate_rule(rule, calculated_through)
            nominal = _decimal(rule.nominal_rate_percent, field=f"Alíquota nominal {code}")
            deduction = _decimal(rule.deduction, field=f"Parcela a deduzir {code}")
            effective_fraction = (
                (denominator * nominal / Decimal("100")) - deduction
            ) / denominator
            if effective_fraction < 0 or effective_fraction > 1:
                raise ValueError(
                    f"A regra {rule.rule_id} produziu alíquota efetiva fora de 0% a 100%."
                )
            estimated = (revenue * effective_fraction).quantize(MONEY, rounding=ROUND_HALF_UP)
            projected_segments.append(TaxSegmentProjection(
                code=code,
                description=str(item.description or "").strip(),
                annex=str(rule.annex).strip().upper(),
                revenue=revenue.quantize(MONEY, rounding=ROUND_HALF_UP),
                nominal_rate_percent=nominal,
                deduction=deduction.quantize(MONEY, rounding=ROUND_HALF_UP),
                effective_rate_percent=(effective_fraction * Decimal("100")).quantize(
                    RATE, rounding=ROUND_HALF_UP
                ),
                estimated_tax=estimated,
                rule_id=str(rule.rule_id).strip(),
                rule_version=str(rule.version).strip(),
                source=str(rule.source).strip(),
            ))

        revenue_to_date = sum((row.revenue for row in projected_segments), Decimal("0"))
        tax_to_date = sum((row.estimated_tax for row in projected_segments), Decimal("0"))
        elapsed_days = Decimal((calculated_through - period_start).days + 1)
        period_days = Decimal((period_end - period_start).days + 1)
        factor = period_days / elapsed_days
        projected_revenue = (revenue_to_date * factor).quantize(MONEY, rounding=ROUND_HALF_UP)
        projected_tax = (tax_to_date * factor).quantize(MONEY, rounding=ROUND_HALF_UP)
        reserve = (projected_tax * (Decimal("1") + margin / Decimal("100"))).quantize(
            MONEY, rounding=ROUND_HALF_UP
        )
        weighted_rate = (
            (tax_to_date / revenue_to_date * Decimal("100"))
            if revenue_to_date else Decimal("0")
        ).quantize(RATE, rounding=ROUND_HALF_UP)
        if calculated_through < period_end:
            warnings.append(
                "Projeção de fechamento usa a média diária até a consulta e pode mudar com o faturamento."
            )
        warnings.append(
            "Tratamentos como ST, monofásico, alíquota zero, isenção, retenções e devoluções "
            "devem estar segregados em regras confirmadas."
        )
        return MonthlyTaxProjection(
            regime=self.SUPPORTED_REGIME,
            recognition_basis=recognition,
            period_start=period_start,
            period_end=period_end,
            calculated_through=calculated_through,
            rbt12=accumulated.quantize(MONEY, rounding=ROUND_HALF_UP),
            revenue_to_date=revenue_to_date.quantize(MONEY, rounding=ROUND_HALF_UP),
            estimated_tax_to_date=tax_to_date.quantize(MONEY, rounding=ROUND_HALF_UP),
            projected_month_revenue=projected_revenue,
            projected_month_tax=projected_tax,
            recommended_reserve=reserve,
            weighted_effective_rate_percent=weighted_rate,
            segments=tuple(projected_segments),
            warnings=tuple(warnings),
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _validate_rule(rule: TaxProjectionRule, on_date: date) -> None:
        required = {
            "identificador": rule.rule_id,
            "versão": rule.version,
            "anexo": rule.annex,
            "fonte": rule.source,
            "responsável pela confirmação": rule.confirmed_by,
        }
        missing = [label for label, value in required.items() if not str(value or "").strip()]
        if missing:
            raise ValueError("Regra tributária incompleta: " + ", ".join(missing) + ".")
        if rule.confirmed_at.tzinfo is None:
            raise ValueError("A confirmação da regra precisa de fuso horário.")
        if on_date < rule.effective_from or (
            rule.effective_until is not None and on_date > rule.effective_until
        ):
            raise ValueError(f"A regra {rule.rule_id} não está vigente na data consultada.")
        nominal = _decimal(rule.nominal_rate_percent, field="Alíquota nominal")
        deduction = _decimal(rule.deduction, field="Parcela a deduzir")
        if nominal < 0 or nominal > 100 or deduction < 0:
            raise ValueError("Parâmetros da regra tributária são inválidos.")
