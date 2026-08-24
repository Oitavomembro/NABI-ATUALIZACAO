from __future__ import annotations

from datetime import date

from .contracts import (
    CapabilityLevel, ParameterDefinition, ParameterType, ToolDefinition,
    ToolKind, ToolRequest, ToolSchema,
)


REPORT_INDICATORS = ToolDefinition(
    "relatorios.consultar_indicadores",
    ToolKind.READ,
    CapabilityLevel.READ,
    "relatorios",
    "view",
    ToolSchema((
        ParameterDefinition("start_date", ParameterType.TEXT, required=True, max_length=10),
        ParameterDefinition("end_date", ParameterType.TEXT, required=True, max_length=10),
    )),
)


def _period(parameters) -> tuple[date, date]:
    values = []
    for key, label in (("start_date", "Data inicial"), ("end_date", "Data final")):
        raw = parameters[key]
        try:
            parsed = date.fromisoformat(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} deve usar AAAA-MM-DD.") from exc
        if raw != parsed.isoformat():
            raise ValueError(f"{label} deve usar AAAA-MM-DD.")
        values.append(parsed)
    start, end = values
    if end < start:
        raise ValueError("A data final não pode ser anterior à inicial.")
    if (end - start).days > 366:
        raise ValueError("O período máximo de consulta é 366 dias.")
    return start, end


class ReportIndicatorsTool:
    def __init__(self, report_service) -> None:
        self._reports = report_service

    def execute(self, request: ToolRequest, *, actor) -> dict:
        start, end = _period(request.parameters)
        indicators = self._reports.indicators(start.isoformat(), end.isoformat())
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "sales_total": format(indicators.sales_total, "f"),
            "receivable_open": format(indicators.receivable_open, "f"),
            "payable_open": format(indicators.payable_open, "f"),
            "low_stock": indicators.low_stock,
            "active_customers": indicators.active_customers,
        }


def register_report_read_tools(registry, report_service) -> None:
    if report_service is not None:
        registry.register(REPORT_INDICATORS, ReportIndicatorsTool(report_service))
