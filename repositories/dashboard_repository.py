from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from database import DatabaseManager
from repositories.decimal_storage import DecimalStorage


@dataclass(frozen=True)
class ClientSummary:
    total_records: int
    current_count: int
    owing_count: int
    owing_value: Decimal
    alert_count: int
    alert_value: Decimal


@dataclass(frozen=True)
class DashboardIndicators:
    overdue_count: int
    overdue_value: Decimal
    active_products: int | None


@dataclass(frozen=True)
class DayMovement:
    movement_id: int
    timestamp: str
    customer_name: str
    movement_type: str
    description: str
    value: Decimal


@dataclass(frozen=True)
class DayHistory:
    movements: list[DayMovement]
    sales_total: Decimal
    received_total: Decimal

    @property
    def movement_total(self) -> Decimal:
        return self.sales_total + self.received_total


class DashboardRepository:
    """Consultas consolidadas do dashboard e dos resumos da tela de clientes."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def client_summary(self, *, now: datetime | None = None) -> ClientSummary:
        reference = now or datetime.now()
        alert_limit = (reference - timedelta(days=60)).strftime("%Y-%m-%d")
        row = self.database.fetch_one(
            """
            WITH primeiro_vencimento AS (
                SELECT cliente_id, MIN(NULLIF(vencimento, '')) AS vencimento
                FROM movimentacoes
                WHERE status_pagamento = 'PENDENTE'
                GROUP BY cliente_id
            )
            SELECT
                COUNT(c.id) AS total_fichas,
                SUM(CASE WHEN COALESCE(c.saldo_devedor, 0) > 0
                          AND (pv.vencimento IS NULL OR pv.vencimento > ?) THEN 1 ELSE 0 END) AS qtd_devendo,
                SUM(CASE WHEN COALESCE(c.saldo_devedor, 0) > 0
                          AND (pv.vencimento IS NULL OR pv.vencimento > ?) THEN COALESCE(c.saldo_devedor, 0) ELSE 0 END) AS val_devendo,
                SUM(CASE WHEN COALESCE(c.saldo_devedor, 0) > 0
                          AND pv.vencimento IS NOT NULL
                          AND pv.vencimento <= ? THEN 1 ELSE 0 END) AS qtd_alerta,
                SUM(CASE WHEN COALESCE(c.saldo_devedor, 0) > 0
                          AND pv.vencimento IS NOT NULL
                          AND pv.vencimento <= ? THEN COALESCE(c.saldo_devedor, 0) ELSE 0 END) AS val_alerta
            FROM clientes c
            LEFT JOIN primeiro_vencimento pv ON pv.cliente_id = c.id
            """,
            (alert_limit, alert_limit, alert_limit, alert_limit),
        )
        values: tuple[Any, ...] = tuple(row) if row is not None else (0, 0, 0.0, 0, 0.0)
        total = int(values[0] or 0)
        owing_count = int(values[1] or 0)
        alert_count = int(values[3] or 0)
        return ClientSummary(
            total_records=total,
            current_count=max(0, total - owing_count - alert_count),
            owing_count=owing_count,
            owing_value=DecimalStorage.to_decimal(values[2] or 0, field="total de clientes devendo"),
            alert_count=alert_count,
            alert_value=DecimalStorage.to_decimal(values[4] or 0, field="total de clientes em alerta"),
        )

    def client_segment_ids(
        self, segment: str, term: str = "", *, limit: int = 200,
        now: datetime | None = None,
    ) -> tuple[int, ...]:
        normalized = str(segment or "").strip().lower()
        conditions = {
            "all": "1=1",
            "current": "COALESCE(c.saldo_devedor,0) <= 0",
            "owing": (
                "COALESCE(c.saldo_devedor,0) > 0 AND "
                "(pv.vencimento IS NULL OR pv.vencimento > ?)"
            ),
            "alert": (
                "COALESCE(c.saldo_devedor,0) > 0 AND pv.vencimento IS NOT NULL "
                "AND pv.vencimento <= ?"
            ),
            "debt": "COALESCE(c.saldo_devedor,0) > 0",
        }
        if normalized not in conditions:
            raise ValueError("Segmento de clientes inválido.")
        clean_term = " ".join(str(term or "").strip().casefold().split())
        params: list[Any] = []
        reference = now or datetime.now()
        if normalized in {"owing", "alert"}:
            params.append((reference - timedelta(days=60)).strftime("%Y-%m-%d"))
        where = conditions[normalized]
        if clean_term:
            search = f"%{clean_term}%"
            where += """ AND (
                LOWER(CAST(c.numero_ficha AS TEXT)) LIKE ? OR LOWER(COALESCE(c.codigo,'')) LIKE ?
                OR LOWER(COALESCE(c.nome,'')) LIKE ? OR LOWER(COALESCE(c.cpf,'')) LIKE ?
                OR LOWER(COALESCE(c.rg,'')) LIKE ? OR LOWER(COALESCE(c.telefone,'')) LIKE ?
                OR LOWER(COALESCE(c.endereco,'')) LIKE ?)
            """
            params.extend([search] * 7)
            order = """CASE
                WHEN CAST(COALESCE(c.numero_ficha,'') AS TEXT)=? THEN 0
                WHEN LOWER(TRIM(COALESCE(c.nome,'')))=? THEN 1
                WHEN LOWER(TRIM(COALESCE(c.nome,''))) LIKE ? THEN 2
                WHEN INSTR(' ' || LOWER(TRIM(COALESCE(c.nome,''))), ' ' || ?) > 0 THEN 3
                ELSE 4 END, c.nome COLLATE NOCASE, c.numero_ficha"""
            params.extend([clean_term, clean_term, f"{clean_term}%", clean_term])
        else:
            order = "CASE WHEN c.numero_ficha IS NULL THEN 1 ELSE 0 END, c.numero_ficha, c.nome COLLATE NOCASE"
        rows = self.database.fetch_all(
            f"""WITH primeiro_vencimento AS (
                    SELECT cliente_id, MIN(NULLIF(vencimento,'')) AS vencimento
                    FROM movimentacoes WHERE status_pagamento='PENDENTE' GROUP BY cliente_id
                )
                SELECT c.id FROM clientes c
                LEFT JOIN primeiro_vencimento pv ON pv.cliente_id=c.id
                WHERE {where} ORDER BY {order} LIMIT ?""",
            (*params, max(1, min(int(limit), 500))),
        )
        return tuple(int(row[0]) for row in rows)

    def indicators(self, *, now: datetime | None = None) -> DashboardIndicators:
        reference = now or datetime.now()
        today = reference.strftime("%Y-%m-%d")
        overdue = self.database.fetch_one(
            """
            SELECT COUNT(*) AS quantidade, COALESCE(SUM(valor_aberto), 0) AS valor
            FROM movimentacoes
            WHERE status_pagamento='PENDENTE'
              AND NULLIF(vencimento, '') IS NOT NULL
              AND vencimento < ?
            """,
            (today,),
        )
        active_products: int | None
        try:
            product_row = self.database.fetch_one("SELECT COUNT(*) AS quantidade FROM produtos WHERE ativo=1")
            active_products = int((product_row["quantidade"] if product_row else 0) or 0)
        except sqlite3.Error:
            active_products = None
        return DashboardIndicators(
            overdue_count=int((overdue["quantidade"] if overdue else 0) or 0),
            overdue_value=DecimalStorage.to_decimal((overdue["valor"] if overdue else 0) or 0, field="total vencido"),
            active_products=active_products,
        )

    def day_history(self, *, day: datetime | None = None) -> DayHistory:
        reference = day or datetime.now()
        day_prefix = reference.strftime("%d/%m/%Y") + "%"
        rows = self.database.fetch_all(
            """
            SELECT m.id, m.data, c.nome, m.tipo, m.descricao, m.valor
            FROM movimentacoes m
            LEFT JOIN clientes c ON m.cliente_id = c.id
            WHERE m.data LIKE ?
            ORDER BY m.id DESC
            """,
            (day_prefix,),
        )
        movements: list[DayMovement] = []
        sales_total = Decimal("0")
        received_total = Decimal("0")
        for row in rows:
            value = DecimalStorage.to_decimal(row[5] or 0, field="valor da movimentação")
            movement_type = str(row[3] or "")
            movements.append(
                DayMovement(
                    movement_id=int(row[0]),
                    timestamp=str(row[1] or ""),
                    customer_name=str(row[2] or "Cliente não encontrado"),
                    movement_type=movement_type,
                    description=str(row[4] or ""),
                    value=value,
                )
            )
            if movement_type == "COMPRA":
                sales_total += value
            elif movement_type == "PAGAMENTO":
                received_total += value
        return DayHistory(movements=movements, sales_total=sales_total, received_total=received_total)
