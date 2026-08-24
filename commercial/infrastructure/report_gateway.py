from __future__ import annotations

from decimal import Decimal

from commercial.application.report_dto import (
    ReportDocument, ReportIndicators, ReportOption, ReportQuery, ReportSummary,
)
from services.report_service import ReportResult, ReportService


class NabiCodeReportGateway:
    """Adapta o serviço oficial existente à fronteira Commercial imutável."""

    def __init__(self, service: ReportService) -> None:
        self.service = service

    def available_reports(self) -> tuple[ReportOption, ...]:
        return tuple(
            ReportOption(report_id, title)
            for report_id, title in self.service.available_reports().items()
            if report_id != "nfe"
        )

    def generate(self, query: ReportQuery, *, actor: str) -> ReportDocument:
        result = self.service.generate(
            query.report_id, start_date=query.start_date, end_date=query.end_date,
            search=query.search, status=query.status, user=query.user,
            limit=query.limit, actor=actor,
        )
        return self._document(result)

    def summary(self, document: ReportDocument) -> ReportSummary:
        result = self._result(document)
        summary = self.service.result_summary(result)
        return ReportSummary(
            quantity=int(summary["quantidade"]),
            value_total=Decimal(str(summary["valor_total"])),
        )

    def indicators(self, start_date: str, end_date: str) -> ReportIndicators:
        values = self.service.indicators(start_date=start_date, end_date=end_date)
        return ReportIndicators(
            sales_total=Decimal(str(values["vendas_total"])),
            receivable_open=Decimal(str(values["receber_aberto"])),
            payable_open=Decimal(str(values["pagar_aberto"])),
            low_stock=int(values["estoque_baixo"]),
            active_customers=int(values["clientes_ativos"]),
        )

    def export(
        self, document: ReportDocument, fmt: str, destination: str, *, actor: str
    ) -> str:
        return str(self.service.export(self._result(document), fmt, destination, actor=actor))

    @staticmethod
    def _document(result: ReportResult) -> ReportDocument:
        return ReportDocument(
            report_id=result.report_id, title=result.title,
            columns=tuple(result.columns), rows=tuple(tuple(row) for row in result.rows),
            filters=tuple(sorted(dict(result.filters).items())),
            generated_at=result.generated_at,
        )

    @staticmethod
    def _result(document: ReportDocument) -> ReportResult:
        return ReportResult(
            report_id=document.report_id, title=document.title,
            columns=document.columns, rows=document.rows,
            filters=dict(document.filters), generated_at=document.generated_at,
        )
