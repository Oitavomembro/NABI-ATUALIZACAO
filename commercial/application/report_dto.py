from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ReportOption:
    report_id: str
    title: str

    def __post_init__(self) -> None:
        if not self.report_id.strip() or not self.title.strip():
            raise ValueError("Relatório disponível inválido.")


@dataclass(frozen=True, slots=True)
class ReportQuery:
    report_id: str
    start_date: str = ""
    end_date: str = ""
    search: str = ""
    status: str = ""
    user: str = ""
    limit: int = 5000

    def __post_init__(self) -> None:
        report_id = self.report_id.strip().lower()
        if not report_id:
            raise ValueError("Selecione um relatório.")
        limit = int(self.limit)
        if not 1 <= limit <= 50_000:
            raise ValueError("Limite do relatório inválido.")
        object.__setattr__(self, "report_id", report_id)
        object.__setattr__(self, "limit", limit)
        for name in ("start_date", "end_date", "search", "status", "user"):
            object.__setattr__(self, name, str(getattr(self, name) or "").strip())


@dataclass(frozen=True, slots=True)
class ReportDocument:
    report_id: str
    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    filters: tuple[tuple[str, object], ...]
    generated_at: str

    def __post_init__(self) -> None:
        if not self.report_id or not self.title or not self.generated_at:
            raise ValueError("Documento de relatório inválido.")
        width = len(self.columns)
        if any(len(row) != width for row in self.rows):
            raise ValueError("Linhas do relatório não correspondem às colunas.")

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True, slots=True)
class ReportSummary:
    quantity: int
    value_total: Decimal


@dataclass(frozen=True, slots=True)
class ReportIndicators:
    sales_total: Decimal
    receivable_open: Decimal
    payable_open: Decimal
    low_stock: int
    active_customers: int
