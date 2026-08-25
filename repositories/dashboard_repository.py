from __future__ import annotations

import sqlite3
import re
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
class ClientSegmentPage:
    ids: tuple[int, ...]
    total_records: int
    limit: int
    offset: int


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


@dataclass(frozen=True)
class DayHistoryPage:
    movements: tuple[DayMovement, ...]
    sales_total: Decimal
    received_total: Decimal
    total_records: int
    limit: int
    offset: int


@dataclass(frozen=True)
class DashboardDetailRow:
    record_id: int
    occurred_at: str
    subject: str
    description: str
    value: Decimal
    status: str


@dataclass(frozen=True)
class DashboardDetailPage:
    kind: str
    rows: tuple[DashboardDetailRow, ...]
    total_records: int
    total_value: Decimal
    limit: int
    offset: int


class DashboardRepository:
    """Consultas consolidadas do dashboard e dos resumos da tela de clientes."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    @staticmethod
    def _public_movement_description(value: Any) -> str:
        """Remove marcadores operacionais; preserva nomes, quantidades e valores."""
        text = str(value or "")
        text = re.sub(
            r"\s*\[(?:AVULSO\s*/\s*SEM\s+ESTOQUE|ESTOQUE\s+NEGATIVO\s+AUTORIZADO)\]\s*",
            " ", text, flags=re.IGNORECASE,
        )
        return re.sub(r"\s+", " ", text).strip()

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
        return self.client_segment_page(
            segment, term, limit=limit, offset=0, now=now
        ).ids

    def client_segment_page(
        self, segment: str, term: str = "", *, limit: int = 200,
        offset: int = 0, now: datetime | None = None,
    ) -> ClientSegmentPage:
        """Retorna uma página limitada e o total completo do segmento."""
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
        where_params: list[Any] = []
        order_params: list[Any] = []
        reference = now or datetime.now()
        if normalized in {"owing", "alert"}:
            where_params.append((reference - timedelta(days=60)).strftime("%Y-%m-%d"))
        where = conditions[normalized]
        if clean_term:
            search = f"%{clean_term}%"
            where += """ AND (
                LOWER(CAST(c.numero_ficha AS TEXT)) LIKE ? OR LOWER(COALESCE(c.codigo,'')) LIKE ?
                OR LOWER(COALESCE(c.nome,'')) LIKE ? OR LOWER(COALESCE(c.cpf,'')) LIKE ?
                OR LOWER(COALESCE(c.rg,'')) LIKE ? OR LOWER(COALESCE(c.telefone,'')) LIKE ?
                OR LOWER(COALESCE(c.endereco,'')) LIKE ?)
            """
            where_params.extend([search] * 7)
            order = """CASE
                WHEN CAST(COALESCE(c.numero_ficha,'') AS TEXT)=? THEN 0
                WHEN LOWER(TRIM(COALESCE(c.nome,'')))=? THEN 1
                WHEN LOWER(TRIM(COALESCE(c.nome,''))) LIKE ? THEN 2
                WHEN INSTR(' ' || LOWER(TRIM(COALESCE(c.nome,''))), ' ' || ?) > 0 THEN 3
                ELSE 4 END, c.nome COLLATE NOCASE, c.numero_ficha"""
            order_params.extend([clean_term, clean_term, f"{clean_term}%", clean_term])
        else:
            order = "(c.numero_ficha IS NULL), c.numero_ficha, c.nome COLLATE NOCASE, c.id"
        safe_limit = max(1, min(int(limit), 500))
        safe_offset = max(0, int(offset))
        cte = """WITH primeiro_vencimento AS (
                    SELECT cliente_id, MIN(NULLIF(vencimento,'')) AS vencimento
                    FROM movimentacoes WHERE status_pagamento='PENDENTE' GROUP BY cliente_id
                )"""
        with self.database.session() as connection:
            connection.execute("BEGIN")
            total_row = connection.execute(
                f"""{cte}
                SELECT COUNT(*) FROM clientes c
                LEFT JOIN primeiro_vencimento pv ON pv.cliente_id=c.id
                WHERE {where}""",
                tuple(where_params),
            ).fetchone()
            rows = connection.execute(
                f"""{cte}
                SELECT c.id FROM clientes c
                LEFT JOIN primeiro_vencimento pv ON pv.cliente_id=c.id
                WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?""",
                (*where_params, *order_params, safe_limit, safe_offset),
            ).fetchall()
        return ClientSegmentPage(
            ids=tuple(int(row[0]) for row in rows),
            total_records=int((total_row[0] if total_row else 0) or 0),
            limit=safe_limit,
            offset=safe_offset,
        )

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

    def detail_page(
        self, kind: str, *, now: datetime | None = None,
        limit: int = 50, offset: int = 0,
    ) -> DashboardDetailPage:
        """Detalhe paginado com o mesmo predicado dos quatro cartões."""
        normalized = str(kind or "").strip().lower()
        if normalized not in {"sales", "receipts", "overdue", "products"}:
            raise ValueError("Detalhe do Dashboard inválido.")
        reference = now or datetime.now()
        safe_limit = max(1, min(int(limit), 100))
        safe_offset = max(0, int(offset))
        if normalized in {"sales", "receipts"}:
            movement_type = "COMPRA" if normalized == "sales" else "PAGAMENTO"
            day_prefix = reference.strftime("%d/%m/%Y") + "%"
            rows = self.database.fetch_all(
                """SELECT m.id,m.data,COALESCE(c.nome,'Cliente não encontrado'),
                          COALESCE(m.descricao,''),m.valor,COALESCE(m.status_pagamento,'')
                   FROM movimentacoes m LEFT JOIN clientes c ON c.id=m.cliente_id
                   WHERE m.data LIKE ? AND m.tipo=?
                   ORDER BY m.id DESC LIMIT ? OFFSET ?""",
                (day_prefix, movement_type, safe_limit, safe_offset),
            )
            totals = self.database.fetch_one(
                "SELECT COUNT(*),COALESCE(SUM(valor),0) FROM movimentacoes WHERE data LIKE ? AND tipo=?",
                (day_prefix, movement_type),
            )
        elif normalized == "overdue":
            today = reference.strftime("%Y-%m-%d")
            rows = self.database.fetch_all(
                """SELECT m.id,m.vencimento,COALESCE(c.nome,'Cliente não encontrado'),
                          COALESCE(m.descricao,''),m.valor_aberto,'VENCIDA'
                   FROM movimentacoes m LEFT JOIN clientes c ON c.id=m.cliente_id
                   WHERE m.status_pagamento='PENDENTE' AND NULLIF(m.vencimento,'') IS NOT NULL
                     AND m.vencimento < ? ORDER BY m.vencimento,m.id LIMIT ? OFFSET ?""",
                (today, safe_limit, safe_offset),
            )
            totals = self.database.fetch_one(
                """SELECT COUNT(*),COALESCE(SUM(valor_aberto),0) FROM movimentacoes
                   WHERE status_pagamento='PENDENTE' AND NULLIF(vencimento,'') IS NOT NULL
                     AND vencimento < ?""",
                (today,),
            )
        else:
            rows = self.database.fetch_all(
                """SELECT id,COALESCE(atualizado_em,''),nome,codigo,
                          COALESCE(NULLIF(TRIM(preco_venda_decimal),''),CAST(preco_venda AS TEXT)),'ATIVO'
                   FROM produtos WHERE ativo=1 ORDER BY nome COLLATE NOCASE,id LIMIT ? OFFSET ?""",
                (safe_limit, safe_offset),
            )
            totals = self.database.fetch_one(
                """SELECT COUNT(*),COALESCE(SUM(
                       CAST(COALESCE(NULLIF(TRIM(preco_venda_decimal),''),CAST(preco_venda AS TEXT)) AS REAL)
                   ),0) FROM produtos WHERE ativo=1"""
            )
        detail_rows = tuple(DashboardDetailRow(
            int(row[0]), str(row[1] or ""), str(row[2] or ""), self._public_movement_description(row[3]),
            DecimalStorage.to_decimal(row[4] or 0, field="valor do detalhe"), str(row[5] or ""),
        ) for row in rows)
        return DashboardDetailPage(
            normalized, detail_rows, int((totals[0] if totals else 0) or 0),
            DecimalStorage.to_decimal((totals[1] if totals else 0) or 0, field="total do detalhe"),
            safe_limit, safe_offset,
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
                    description=self._public_movement_description(row[4]),
                    value=value,
                )
            )
            if movement_type == "COMPRA":
                sales_total += value
            elif movement_type == "PAGAMENTO":
                received_total += value
        return DayHistory(movements=movements, sales_total=sales_total, received_total=received_total)

    def day_history_page(
        self, *, day: datetime | None = None, limit: int = 50, offset: int = 0
    ) -> DayHistoryPage:
        """Página limitada e totais do dia calculados no banco, sem carregar tudo."""
        reference = day or datetime.now()
        day_prefix = reference.strftime("%d/%m/%Y") + "%"
        safe_limit = max(1, min(int(limit), 200))
        safe_offset = max(0, int(offset))
        rows = self.database.fetch_all(
            """
            SELECT m.id, m.data, c.nome, m.tipo, m.descricao, m.valor
            FROM movimentacoes m
            LEFT JOIN clientes c ON m.cliente_id = c.id
            WHERE m.data LIKE ?
            ORDER BY m.id DESC LIMIT ? OFFSET ?
            """,
            (day_prefix, safe_limit, safe_offset),
        )
        totals = self.database.fetch_one(
            """
            SELECT COUNT(*) AS quantidade,
                   COALESCE(SUM(CASE WHEN tipo='COMPRA' THEN valor ELSE 0 END),0) AS vendas,
                   COALESCE(SUM(CASE WHEN tipo='PAGAMENTO' THEN valor ELSE 0 END),0) AS recebimentos
            FROM movimentacoes WHERE data LIKE ?
            """,
            (day_prefix,),
        )
        movements = tuple(DayMovement(
            movement_id=int(row[0]), timestamp=str(row[1] or ""),
            customer_name=str(row[2] or "Cliente não encontrado"),
            movement_type=str(row[3] or ""),
            description=self._public_movement_description(row[4]),
            value=DecimalStorage.to_decimal(row[5] or 0, field="valor da movimentação"),
        ) for row in rows)
        return DayHistoryPage(
            movements=movements,
            sales_total=DecimalStorage.to_decimal((totals[1] if totals else 0) or 0, field="vendas do dia"),
            received_total=DecimalStorage.to_decimal((totals[2] if totals else 0) or 0, field="recebimentos do dia"),
            total_records=int((totals[0] if totals else 0) or 0),
            limit=safe_limit, offset=safe_offset,
        )
