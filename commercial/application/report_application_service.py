from __future__ import annotations

from pathlib import Path

from .ports import ReportReadPort
from .report_dto import ReportDocument, ReportIndicators, ReportOption, ReportPage, ReportQuery, ReportSummary


class ReportApplicationService:
    """Fachada Qt/Commercial sem banco, SQL ou dependência de interface."""

    FORMATS = ("CSV", "XLSX", "PDF")

    def __init__(self, reports: ReportReadPort) -> None:
        self._reports = reports

    def available_reports(self) -> tuple[ReportOption, ...]:
        return self._reports.available_reports()

    def generate(self, query: ReportQuery, *, actor: str) -> ReportDocument:
        if not str(actor or "").strip():
            raise PermissionError("Sessão necessária para gerar relatório.")
        return self._reports.generate(query, actor=str(actor).strip())

    def load_page(self, query: ReportQuery, *, limit: int = 100, offset: int = 0, actor: str) -> ReportPage:
        if not str(actor or "").strip():
            raise PermissionError("Sessão necessária para gerar relatório.")
        return self._reports.load_page(query, limit=limit, offset=offset, actor=str(actor).strip())

    def summary(self, document: ReportDocument) -> ReportSummary:
        return self._reports.summary(document)

    def indicators(self, start_date: str, end_date: str) -> ReportIndicators:
        return self._reports.indicators(start_date, end_date)

    def export(
        self, document: ReportDocument, fmt: str, destination: str | Path, *, actor: str
    ) -> str:
        normalized = str(fmt or "").strip().upper()
        if normalized not in self.FORMATS:
            raise ValueError("Formato de exportação inválido.")
        if not str(actor or "").strip():
            raise PermissionError("Sessão necessária para exportar relatório.")
        return self._reports.export(
            document, normalized, str(destination), actor=str(actor).strip()
        )

    def export_query(self, query: ReportQuery, fmt: str, destination: str | Path, *, actor: str) -> str:
        normalized = str(fmt or "").strip().upper()
        if normalized not in self.FORMATS:
            raise ValueError("Formato de exportação inválido.")
        if not str(actor or "").strip():
            raise PermissionError("Sessão necessária para exportar relatório.")
        return self._reports.export_query(query, normalized, str(destination), actor=str(actor).strip())
