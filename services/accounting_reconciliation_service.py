from __future__ import annotations

import csv
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class ReconciliationEntry:
    relation: str
    source_id: str
    target_id: str
    classification: str
    competence_date: str
    cash_date: str
    competence_amount: Decimal
    cash_amount: Decimal
    detail: str


@dataclass(frozen=True)
class MonthlyReconciliation:
    layout: str
    period_start: str
    period_end: str
    entries: tuple[ReconciliationEntry, ...]
    limitations: tuple[str, ...]

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        totals: dict[str, dict[str, Decimal]] = {}
        for entry in self.entries:
            counts[entry.classification] = counts.get(entry.classification, 0) + 1
            relation = totals.setdefault(
                entry.relation, {"competence": Decimal("0.00"), "cash": Decimal("0.00")}
            )
            relation["competence"] += entry.competence_amount
            relation["cash"] += entry.cash_amount
        return {
            "layout": self.layout,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "counts": counts,
            "totals_by_relation": {
                relation: {
                    "competence": values["competence"].quantize(Decimal("0.01")),
                    "cash": values["cash"].quantize(Decimal("0.01")),
                }
                for relation, values in sorted(totals.items())
            },
            "entries": len(self.entries),
        }


class AccountingReconciliationService:
    """Diagnóstico mensal somente leitura; não cria lançamentos contábeis."""

    LAYOUT = "nabicode.accounting-reconciliation.v1"
    VALID = {
        "CONCILIADO", "PENDENTE_DADO_EXTERNO", "DIVERGENTE",
        "LEGADO_NAO_PROVAVEL", "NAO_APLICAVEL",
    }
    LIMITATIONS = (
        "Pagamentos de vendas são preservados em JSON de configurações, não em linhas canônicas.",
        "Vendas e recebimentos não possuem cash_session_id; caixa é apenas inferido.",
        "Itens antigos podem existir somente em descrição textual, sem itens canônicos.",
        "NF-e importada não possui vínculo inequívoco com pedido/recebimento de compra.",
        "Este diagnóstico separa competência e caixa e não substitui escrituração contábil.",
    )

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]) -> None:
        self.connection_factory = connection_factory

    def reconcile(self, *, start_date: str, end_date: str) -> MonthlyReconciliation:
        start = self._date(start_date)
        end = self._date(end_date)
        if start > end:
            raise ValueError("A data inicial não pode ser posterior à data final.")
        connection = self.connection_factory()
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            entries: list[ReconciliationEntry] = []
            sales = self._period_rows(connection, "movimentacoes", ("data",), start, end)
            sales = [row for row in sales if str(row.get("tipo") or "").upper() in {"VENDA", "COMPRA"}]
            sale_ids = {str(row["id"]) for row in sales}
            for sale in sales:
                self._sale_entries(connection, sale, entries)
            self._orphan_fiscal_entries(connection, sale_ids, start, end, entries)
            self._purchase_entries(connection, start, end, entries)
            self._orphan_financial_entries(connection, start, end, entries)
            self._dfe_entries(connection, start, end, entries)
            entries.sort(key=lambda row: (row.relation, row.source_id, row.target_id, row.detail))
            return MonthlyReconciliation(
                self.LAYOUT, start.isoformat(), end.isoformat(), tuple(entries), self.LIMITATIONS,
            )
        finally:
            connection.close()

    def export_csv(self, result: MonthlyReconciliation, output_path: str | Path) -> Path:
        if result.layout != self.LAYOUT:
            raise ValueError("Layout de reconciliação incompatível.")
        path = Path(output_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(("layout", result.layout))
            writer.writerow(("periodo", result.period_start, result.period_end))
            summary = result.summary()
            for classification, count in sorted(summary["counts"].items()):
                writer.writerow(("resumo_classificacao", classification, count))
            for relation, totals in summary["totals_by_relation"].items():
                writer.writerow(("resumo_relacao", relation, format(totals["competence"], ".2f"), format(totals["cash"], ".2f")))
            for limitation in result.limitations:
                writer.writerow(("limitacao", limitation))
            writer.writerow((
                "relacao", "origem_id", "destino_id", "classificacao",
                "data_competencia", "data_caixa", "valor_competencia", "valor_caixa", "detalhe",
            ))
            for item in result.entries:
                writer.writerow((
                    item.relation, item.source_id, item.target_id, item.classification,
                    item.competence_date, item.cash_date,
                    format(item.competence_amount, ".2f"), format(item.cash_amount, ".2f"), item.detail,
                ))
        temporary.replace(path)
        return path

    def _sale_entries(self, connection: sqlite3.Connection, sale: dict[str, Any], entries: list[ReconciliationEntry]) -> None:
        sale_id = str(sale["id"])
        occurred = self._iso_date(sale.get("data"))
        total = self._money(sale.get("valor_decimal", sale.get("valor", 0)))
        canceled = str(sale.get("status_pagamento") or "").upper() == "CANCELADO"
        documents = self._where(connection, "fiscal_sale_documents", "sale_id", sale_id)
        if len(documents) > 1:
            fiscal_status, fiscal_target, fiscal_detail = "DIVERGENTE", "", "Mais de um documento fiscal para a venda."
        elif not documents:
            fiscal_status, fiscal_target, fiscal_detail = (
                "PENDENTE_DADO_EXTERNO", "", "Não é possível provar pelo banco se esta venda exigia documento fiscal."
            )
        else:
            document = documents[0]
            fiscal_target = str(document.get("id") or "")
            status = str(document.get("status") or "").upper()
            coherent = (canceled and status == "CANCELADO") or (not canceled and status != "CANCELADO")
            fiscal_status = "CONCILIADO" if coherent else "DIVERGENTE"
            fiscal_detail = f"Documento {status or 'SEM_STATUS'}; chave={document.get('access_key') or '-'}"
        entries.append(self._entry("VENDA_FISCAL", sale_id, fiscal_target, fiscal_status, occurred, "", total, 0, fiscal_detail))

        payment_key = f"pdv_pagamentos_venda_{sale_id}"
        payment = self._configuration(connection, payment_key)
        if payment is None:
            payment_status, payment_total, payment_detail = (
                "LEGADO_NAO_PROVAVEL", Decimal("0"), "Configuração JSON de pagamentos ausente."
            )
        elif not isinstance(payment, dict) or not isinstance(payment.get("pagamentos"), list):
            payment_status, payment_total, payment_detail = "DIVERGENTE", Decimal("0"), "JSON de pagamentos inválido."
        else:
            try:
                payment_total = sum((self._money(row.get("valor")) for row in payment["pagamentos"]), Decimal("0"))
                declared = self._money(payment.get("total"))
                payment_status = "CONCILIADO" if declared == total and payment_total >= total else "DIVERGENTE"
                payment_detail = f"total_venda={total:.2f}; declarado={declared:.2f}; pagamentos={payment_total:.2f}"
            except (AttributeError, InvalidOperation, ValueError):
                payment_status, payment_total, payment_detail = "DIVERGENTE", Decimal("0"), "JSON de pagamentos contém valores inválidos."
        entries.append(self._entry("VENDA_PAGAMENTOS", sale_id, payment_key, payment_status, occurred, occurred, total, payment_total, payment_detail))

        form = str(sale.get("forma_pagamento") or "").upper()
        titles = [row for row in self._where(connection, "titulos_financeiros", "origem_id", sale_id)
                  if str(row.get("origem") or "").upper() == "VENDA" and str(row.get("tipo") or "").upper() == "RECEBER"]
        parcels = self._where(connection, "parcelas", "movimentacao_id", sale_id)
        credit = "CREDIARIO" in form
        if credit and len(titles) == 1 and parcels:
            title_value = self._money(titles[0].get("valor_original_decimal", titles[0].get("valor_original", 0)))
            parcel_value = sum((self._money(row.get("valor_parcela_decimal", row.get("valor_parcela", 0))) for row in parcels), Decimal("0"))
            expected = self._money(sale.get("valor_aberto_decimal", sale.get("valor_aberto", 0)))
            status = "CONCILIADO" if title_value == expected and parcel_value == expected else "DIVERGENTE"
            detail = f"financiado={expected:.2f}; titulo={title_value:.2f}; parcelas={parcel_value:.2f}"
        elif credit:
            status, detail = "DIVERGENTE", f"Crediário exige um título e parcelas; titulos={len(titles)}; parcelas={len(parcels)}."
        elif titles:
            status, detail = "DIVERGENTE", "Venda não crediária possui título a receber vinculado."
        else:
            status, detail = "NAO_APLICAVEL", "Venda sem crediário não exige título a receber."
        entries.append(self._entry("VENDA_TITULO_PARCELAS", sale_id, ",".join(str(row.get("id")) for row in titles), status, occurred, "", total if credit else 0, 0, detail))

        cash_class = "NAO_APLICAVEL" if canceled else "PENDENTE_DADO_EXTERNO"
        entries.append(self._entry(
            "VENDA_CAIXA_INFERIDO", sale_id, "", cash_class, occurred, occurred,
            Decimal("0"), payment_total if not canceled else Decimal("0"),
            "Sem cash_session_id; valor de caixa é inferido do JSON e não conciliado.",
        ))

        if canceled:
            stock = [row for row in self._where(connection, "estoque_movimentacoes", "origem_id", sale_id)
                     if str(row.get("origem") or "").upper() == "ESTORNO_VENDA"]
            title_ok = all(str(row.get("status") or "").upper() == "CANCELADO" for row in titles)
            status = "CONCILIADO" if stock and title_ok else "DIVERGENTE"
            entries.append(self._entry("VENDA_CANCELAMENTO_ESTORNO", sale_id, "", status, occurred, "", -total, 0,
                                       f"estoques_estornados={len(stock)}; titulos_cancelados={title_ok}"))

    def _orphan_fiscal_entries(self, connection, sale_ids: set[str], start: date, end: date, entries: list[ReconciliationEntry]) -> None:
        for row in self._period_rows(connection, "fiscal_sale_documents", ("created_at",), start, end):
            sale_id = str(row.get("sale_id") or "")
            if sale_id not in sale_ids and not self._exists(connection, "movimentacoes", "id", sale_id):
                entries.append(self._entry("DOCUMENTO_FISCAL_VENDA", str(row.get("id") or ""), sale_id, "DIVERGENTE",
                                           self._iso_date(row.get("created_at")), "", 0, 0, "Documento fiscal aponta para venda inexistente."))

    def _purchase_entries(self, connection, start: date, end: date, entries: list[ReconciliationEntry]) -> None:
        for order in self._period_rows(connection, "pedidos_compra", ("criado_em", "atualizado_em"), start, end):
            order_id = str(order.get("id") or "")
            receipts = self._where(connection, "recebimentos_compra", "pedido_id", order_id)
            canceled = str(order.get("status") or "").upper() == "CANCELADO"
            classification = "NAO_APLICAVEL" if canceled else (
                "CONCILIADO" if receipts else "PENDENTE_DADO_EXTERNO"
            )
            entries.append(self._entry(
                "PEDIDO_RECEBIMENTO", order_id,
                ",".join(str(row.get("id") or "") for row in receipts), classification,
                self._iso_date(order.get("criado_em")), "", 0, 0,
                "Pedido cancelado." if canceled else f"recebimentos={len(receipts)}; parcial permitido",
            ))
        for receipt in self._period_rows(connection, "recebimentos_compra", ("data_recebimento",), start, end):
            receipt_id, order_id = str(receipt.get("id") or ""), str(receipt.get("pedido_id") or "")
            order_exists = self._exists(connection, "pedidos_compra", "id", order_id)
            items = self._where(connection, "recebimento_compra_itens", "recebimento_id", receipt_id)
            stock = []
            if self._table(connection, "estoque_movimentacoes"):
                stock = [dict(row) for row in connection.execute(
                    "SELECT * FROM estoque_movimentacoes WHERE UPPER(COALESCE(origem,''))='COMPRA' "
                    "AND origem_id LIKE ?", (f"{order_id}:%",),
                ).fetchall()]
            item_products = {str(row.get("produto_id") or "") for row in items}
            stock_products = {str(row.get("produto_id") or "") for row in stock}
            status = "CONCILIADO" if order_exists and items and item_products <= stock_products else "DIVERGENTE"
            value = sum((self._money(row.get("valor_total")) for row in items), Decimal("0"))
            entries.append(self._entry("COMPRA_RECEBIMENTO_ESTOQUE", order_id, receipt_id, status,
                                       self._iso_date(receipt.get("data_recebimento")), "", value, 0,
                                       f"itens={len(items)}; movimentos_estoque={len(stock)}; recebimento_parcial_permitido"))
            titles = [row for row in self._where(connection, "titulos_financeiros", "origem_id", receipt_id)
                      if str(row.get("origem") or "").upper() == "RECEBIMENTO_COMPRA" and str(row.get("tipo") or "").upper() == "PAGAR"]
            if len(titles) > 1:
                title_status = "DIVERGENTE"
            elif not titles:
                title_status = "PENDENTE_DADO_EXTERNO"
            else:
                title_status = "CONCILIADO" if self._money(titles[0].get("valor_original_decimal", titles[0].get("valor_original"))) == value else "DIVERGENTE"
            entries.append(self._entry("RECEBIMENTO_COMPRA_TITULO", receipt_id,
                                       ",".join(str(row.get("id")) for row in titles), title_status,
                                       self._iso_date(receipt.get("data_recebimento")), "", value, 0,
                                       "Conta a pagar é opcional no recebimento; ausência exige confirmação externa."))
        for stock in self._period_rows(connection, "estoque_movimentacoes", ("data",), start, end):
            if str(stock.get("origem") or "").upper() != "COMPRA":
                continue
            origin = str(stock.get("origem_id") or "")
            order_id = origin.split(":", 1)[0]
            if not order_id.isdigit() or not self._exists(connection, "pedidos_compra", "id", order_id):
                entries.append(self._entry(
                    "ESTOQUE_COMPRA_ORIGEM", str(stock.get("id") or ""), origin,
                    "DIVERGENTE", self._iso_date(stock.get("data")), "", 0, 0,
                    "Movimento de estoque possui origem COMPRA inválida ou órfã.",
                ))

    def _orphan_financial_entries(self, connection, start: date, end: date, entries: list[ReconciliationEntry]) -> None:
        for payment in self._period_rows(connection, "pagamentos_titulos", ("data_pagamento",), start, end):
            title_id = str(payment.get("titulo_id") or "")
            exists = self._exists(connection, "titulos_financeiros", "id", title_id)
            entries.append(self._entry("PAGAMENTO_TITULO", str(payment.get("id") or ""), title_id,
                                       "CONCILIADO" if exists else "DIVERGENTE", "",
                                       self._iso_date(payment.get("data_pagamento")), 0,
                                       self._money(payment.get("valor_decimal", payment.get("valor"))),
                                       "Pagamento possui título." if exists else "Pagamento órfão sem título."))
        for title in self._period_rows(connection, "titulos_financeiros", ("data_emissao", "criado_em"), start, end):
            origin = str(title.get("origem") or "").upper()
            origin_id = str(title.get("origem_id") or "")
            if origin in {"VENDA", "RECEBIMENTO_COMPRA"} and not origin_id:
                entries.append(self._entry("TITULO_ORIGEM", str(title.get("id") or ""), "", "DIVERGENTE",
                                           self._iso_date(title.get("data_emissao")), "",
                                           self._money(title.get("valor_original_decimal", title.get("valor_original"))), 0,
                                           f"Título de origem {origin} sem origem_id."))
            elif origin not in {"", "MANUAL", "VENDA", "RECEBIMENTO_COMPRA", "RECORRENTE"}:
                entries.append(self._entry(
                    "TITULO_ORIGEM", str(title.get("id") or ""), origin_id, "DIVERGENTE",
                    self._iso_date(title.get("data_emissao")), "",
                    self._money(title.get("valor_original_decimal", title.get("valor_original"))), 0,
                    f"Origem de título não reconhecida: {origin}.",
                ))
        if self._table(connection, "configuracoes"):
            for row in connection.execute(
                "SELECT chave FROM configuracoes WHERE chave LIKE 'pdv_pagamentos_venda_%'"
            ).fetchall():
                key = str(row[0])
                sale_id = key.removeprefix("pdv_pagamentos_venda_")
                if not sale_id.isdigit() or not self._exists(connection, "movimentacoes", "id", sale_id):
                    entries.append(self._entry(
                        "PAGAMENTO_CONFIG_VENDA", key, sale_id, "DIVERGENTE", "", "", 0, 0,
                        "Configuração de pagamento aponta para venda inexistente ou inválida.",
                    ))

    def _dfe_entries(self, connection, start: date, end: date, entries: list[ReconciliationEntry]) -> None:
        for imported in self._period_rows(connection, "nfe_importacoes", ("data_importacao",), start, end):
            entries.append(self._entry(
                "DFE_COMPRA", str(imported.get("id") or ""), "", "LEGADO_NAO_PROVAVEL",
                self._iso_date(imported.get("data_importacao")), "", self._money(imported.get("valor_total")), 0,
                f"Chave {imported.get('chave') or '-'} sem pedido_id/recebimento_id; correspondência textual não é aceita.",
            ))

    @classmethod
    def _entry(cls, relation: str, source: str, target: str, classification: str,
               competence_date: str, cash_date: str, competence_amount: Any,
               cash_amount: Any, detail: str) -> ReconciliationEntry:
        if classification not in cls.VALID:
            raise ValueError("Classificação de reconciliação inválida.")
        return ReconciliationEntry(relation, source, target, classification, competence_date, cash_date,
                                   cls._money(competence_amount), cls._money(cash_amount), detail)

    @staticmethod
    def _table(connection: sqlite3.Connection, name: str) -> bool:
        return connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

    @classmethod
    def _all(cls, connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
        if not cls._table(connection, table):
            return []
        if not re.fullmatch(r"[a-z_]+", table):
            raise ValueError("Tabela de reconciliação inválida.")
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table}").fetchall()]

    @classmethod
    def _where(cls, connection: sqlite3.Connection, table: str, column: str, value: str) -> list[dict[str, Any]]:
        if not cls._table(connection, table):
            return []
        columns = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            return []
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table} WHERE CAST({column} AS TEXT)=?", (value,)).fetchall()]

    @classmethod
    def _exists(cls, connection: sqlite3.Connection, table: str, column: str, value: str) -> bool:
        return bool(cls._where(connection, table, column, value))

    @classmethod
    def _period_rows(cls, connection: sqlite3.Connection, table: str, date_columns: Iterable[str], start: date, end: date) -> list[dict[str, Any]]:
        if not cls._table(connection, table):
            return []
        columns = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
        usable = [column for column in date_columns if column in columns]
        if not usable:
            return []
        found: dict[str, dict[str, Any]] = {}
        end_exclusive = end + timedelta(days=1)
        for column in usable:
            if not re.fullmatch(r"[a-z_]+", column):
                raise ValueError("Coluna de reconciliação inválida.")
            queries = (
                (
                    f"SELECT * FROM {table} WHERE instr(COALESCE({column},''),'/')=0 "
                    f"AND {column}>=? AND {column}<?",
                    (start.isoformat(), end_exclusive.isoformat()),
                ),
                (
                    f"SELECT * FROM {table} WHERE instr(COALESCE({column},''),'/')=3 "
                    f"AND (substr({column},7,4)||'-'||substr({column},4,2)||'-'||substr({column},1,2)) BETWEEN ? AND ?",
                    (start.isoformat(), end.isoformat()),
                ),
            )
            for sql, params in queries:
                for row in connection.execute(sql, params).fetchall():
                    data = dict(row)
                    identity = str(data.get("id") or json.dumps(data, sort_keys=True, default=str))
                    found[identity] = data
        def order_key(value: str) -> tuple[int, Any]:
            return (0, int(value)) if value.isdigit() else (1, value)
        return [found[key] for key in sorted(found, key=order_key)]

    @classmethod
    def _configuration(cls, connection: sqlite3.Connection, key: str) -> Any:
        if not cls._table(connection, "configuracoes"):
            return None
        row = connection.execute("SELECT valor FROM configuracoes WHERE chave=?", (key,)).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            return "__INVALID_JSON__"

    @staticmethod
    def _money(value: Any) -> Decimal:
        if value in (None, ""):
            return Decimal("0.00")
        return Decimal(str(value).replace(",", ".")).quantize(Decimal("0.01"))

    @classmethod
    def _date(cls, value: str) -> date:
        parsed = cls._try_date(value)
        if parsed is None:
            raise ValueError("Data de reconciliação inválida.")
        return parsed

    @staticmethod
    def _try_date(value: Any) -> date | None:
        text = str(value or "").strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(text[:10], fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None

    @classmethod
    def _iso_date(cls, value: Any) -> str:
        parsed = cls._try_date(value)
        return parsed.isoformat() if parsed else ""
