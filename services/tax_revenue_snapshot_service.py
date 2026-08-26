from __future__ import annotations

import calendar
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable

from repositories.decimal_storage import DecimalStorage


@dataclass(frozen=True)
class TaxRevenueSnapshot:
    period_start: date
    calculated_through: date
    rbt12_start: date
    rbt12_end: date
    revenue_to_date: Decimal
    rbt12_revenue: Decimal
    included_sales: int
    cancelled_sales: int
    mirrored_rows: int
    invalid_date_rows: int
    warnings: tuple[str, ...]


class TaxRevenueSnapshotService:
    """Lê evidência de faturamento sem classificar tratamento tributário."""

    SALE_TYPES = {"COMPRA", "VENDA", "VENDA_HISTORICA"}
    MIRROR_ORIGINS = {"FINANCEIRO", "TITULO_FINANCEIRO"}

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]) -> None:
        self.connection_factory = connection_factory

    def read_competence_month(
        self, *, period_start: date, calculated_through: date
    ) -> TaxRevenueSnapshot:
        if period_start.day != 1:
            raise ValueError("O período mensal deve começar no primeiro dia do mês.")
        period_end = date(
            period_start.year, period_start.month,
            calendar.monthrange(period_start.year, period_start.month)[1],
        )
        if not period_start <= calculated_through <= period_end:
            raise ValueError("A data da consulta deve pertencer ao mês informado.")
        rbt12_start = period_start.replace(year=period_start.year - 1)
        rbt12_end = period_start - timedelta(days=1)

        connection = self.connection_factory()
        try:
            columns = {
                str(row[1]).casefold()
                for row in connection.execute("PRAGMA table_info(movimentacoes)").fetchall()
            }
            required = {"tipo", "data", "valor", "status_pagamento"}
            if not required.issubset(columns):
                raise RuntimeError("O banco não possui a evidência mínima de faturamento.")
            value_column = "valor_decimal" if "valor_decimal" in columns else "valor"
            origin_expr = "origem_sistema" if "origem_sistema" in columns else "''"
            rows = connection.execute(
                f"SELECT tipo,data,{value_column} AS valor,status_pagamento,"
                f"{origin_expr} AS origem_sistema FROM movimentacoes"
            ).fetchall()
        finally:
            connection.close()

        current_total = Decimal("0")
        accumulated = Decimal("0")
        included = cancelled = mirrored = invalid_dates = 0
        for row in rows:
            kind = str(row["tipo"] or "").strip().upper()
            if kind not in self.SALE_TYPES:
                continue
            if str(row["origem_sistema"] or "").strip().upper() in self.MIRROR_ORIGINS:
                mirrored += 1
                continue
            if str(row["status_pagamento"] or "").strip().upper() == "CANCELADO":
                cancelled += 1
                continue
            occurred = self._parse_date(row["data"])
            if occurred is None:
                invalid_dates += 1
                continue
            amount = DecimalStorage.to_decimal(row["valor"] or 0, field="faturamento")
            if amount < 0:
                raise ValueError("Venda com valor negativo exige revisão antes da projeção.")
            if period_start <= occurred <= calculated_through:
                current_total += amount
                included += 1
            if rbt12_start <= occurred <= rbt12_end:
                accumulated += amount

        warnings = [
            "Snapshot por competência: ainda não segrega receitas por tratamento tributário."
        ]
        if invalid_dates:
            warnings.append(
                f"{invalid_dates} venda(s) possuem data inválida e ficaram fora do cálculo."
            )
        if mirrored:
            warnings.append(
                f"{mirrored} espelho(s) financeiro(s) foram excluídos para evitar duplicidade."
            )
        return TaxRevenueSnapshot(
            period_start=period_start,
            calculated_through=calculated_through,
            rbt12_start=rbt12_start,
            rbt12_end=rbt12_end,
            revenue_to_date=current_total,
            rbt12_revenue=accumulated,
            included_sales=included,
            cancelled_sales=cancelled,
            mirrored_rows=mirrored,
            invalid_date_rows=invalid_dates,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _parse_date(value: object) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None
        normalized = text.replace("T", " ").split(" ", 1)[0]
        for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(normalized, pattern).date()
            except ValueError:
                continue
        return None
