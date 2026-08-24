from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from commercial.application.report_application_service import ReportApplicationService
from commercial.application.report_dto import (
    ReportDocument, ReportIndicators, ReportOption, ReportQuery, ReportSummary,
)


class Reports:
    def __init__(self):
        self.calls = []

    def available_reports(self):
        return (ReportOption("vendas", "Vendas"),)

    def generate(self, query, *, actor):
        self.calls.append(("generate", query, actor))
        return ReportDocument(
            "vendas", "Vendas", ("id", "valor_total"), ((1, "12.50"),),
            (("search", query.search),), datetime.now().isoformat(),
        )

    def summary(self, document):
        return ReportSummary(document.row_count, Decimal("12.50"))

    def indicators(self, start_date, end_date):
        self.calls.append(("indicators", start_date, end_date))
        return ReportIndicators(Decimal("12.50"), Decimal("5"), Decimal("2"), 3, 4)

    def export(self, document, fmt, destination, *, actor):
        self.calls.append(("export", document, fmt, destination, actor))
        return destination


def test_fachada_preserva_consulta_imutavel_e_usuario_real():
    reports = Reports(); application = ReportApplicationService(reports)
    query = ReportQuery(" VENDAS ", search=" mesa ")
    document = application.generate(query, actor="operador")
    assert document.rows == ((1, "12.50"),)
    assert reports.calls[0] == ("generate", query, "operador")
    assert query.report_id == "vendas" and query.search == "mesa"


def test_fachada_recusa_ator_ausente_e_formato_inventado(tmp_path):
    application = ReportApplicationService(Reports())
    with pytest.raises(PermissionError):
        application.generate(ReportQuery("vendas"), actor="")
    document = application.generate(ReportQuery("vendas"), actor="operador")
    with pytest.raises(ValueError):
        application.export(document, "HTML", tmp_path / "x.html", actor="operador")


def test_documento_recusa_linha_com_largura_inconsistente():
    with pytest.raises(ValueError):
        ReportDocument("vendas", "Vendas", ("a", "b"), ((1,),), (), "agora")


def test_exportacao_transporta_mesmo_documento_revisado(tmp_path):
    reports = Reports(); application = ReportApplicationService(reports)
    document = application.generate(ReportQuery("vendas"), actor="operador")
    path = tmp_path / "vendas.csv"
    assert application.export(document, "csv", path, actor="operador") == str(path)
    assert reports.calls[-1] == ("export", document, "CSV", str(path), "operador")
