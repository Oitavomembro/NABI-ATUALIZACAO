from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from commercial.application.financial_dto import (
    CashFlowEntry, CreateFinancialTitleCommand, CustomerCollectionSummary,
    FinancialSummary, PayableSummary, PersistedFinancialAction,
    ReceivableSummary, SettleFinancialTitleCommand,
)


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


class NabiCodeFinancialGateway:
    """Adapta o Financeiro/Cobrança existente sem vazar seus registros."""

    def __init__(self, financeiro_service, financeiro_repository, cobranca_service) -> None:
        self.service = financeiro_service
        self.repository = financeiro_repository
        self.collections = cobranca_service

    @staticmethod
    def _matches(row, *, status=None, customer_id=None, due_from=None, due_to=None,
                 overdue=False, open_only=False) -> bool:
        row_status = str(row.get("status") or "").upper()
        due = _date(row["data_vencimento"])
        if status and row_status != str(status).upper():
            return False
        if open_only and row_status not in {"ABERTO", "PARCIAL"}:
            return False
        if customer_id is not None and row.get("pessoa_id") != int(customer_id):
            return False
        if due_from and due < _date(due_from):
            return False
        if due_to and due > _date(due_to):
            return False
        if overdue and not (due < date.today() and row_status in {"ABERTO", "PARCIAL"}):
            return False
        return True

    def receivables(self, **filters) -> tuple[ReceivableSummary, ...]:
        rows = self.repository.listar_titulos(tipo="RECEBER", limite=5000)
        result = []
        for row in rows:
            if not self._matches(row, **filters):
                continue
            result.append(ReceivableSummary(
                int(row["id"]), int(row["pessoa_id"]) if row.get("pessoa_id") is not None else None,
                str(row.get("pessoa_nome") or ""), str(row.get("origem") or ""),
                str(row.get("origem_id") or ""), str(row.get("documento") or ""),
                str(row.get("descricao") or ""), row["valor_original"], row["valor_pago"],
                row["saldo_aberto"], _date(row["data_emissao"]), _date(row["data_vencimento"]),
                str(row["status"]), bool(row.get("vencido")),
            ))
        return tuple(result)

    def payables(self, **filters) -> tuple[PayableSummary, ...]:
        rows = self.repository.listar_titulos(tipo="PAGAR", limite=5000)
        result = []
        for row in rows:
            if not self._matches(row, **filters):
                continue
            result.append(PayableSummary(
                int(row["id"]), int(row["pessoa_id"]) if row.get("pessoa_id") is not None else None,
                str(row.get("pessoa_nome") or ""), str(row.get("origem") or ""),
                str(row.get("origem_id") or ""), str(row.get("documento") or ""),
                str(row.get("descricao") or ""), row["valor_original"], row["valor_pago"],
                row["saldo_aberto"], _date(row["data_emissao"]), _date(row["data_vencimento"]),
                str(row["status"]), bool(row.get("vencido")), self.service.obter_centro_custo(int(row["id"])),
            ))
        return tuple(result)

    def customer_collections(self, customer_id: int | None = None) -> tuple[CustomerCollectionSummary, ...]:
        result = []
        today = date.today()
        for row in self.collections.listar_atrasadas():
            if customer_id is not None and int(row["cliente_id"]) != int(customer_id):
                continue
            due = _date(row["vencimento"])
            result.append(CustomerCollectionSummary(
                int(row["parcela_id"]), int(row["cliente_id"]), str(row.get("nome") or ""),
                str(row.get("telefone") or ""), int(row.get("numero_parcela") or 0),
                Decimal(str(row.get("valor_aberto") or 0)), due, max(0, (today - due).days),
                str(row.get("ultimo_contato") or ""), str(row.get("situacao") or ""),
            ))
        return tuple(result)

    def financial_summary(self, start_date, end_date) -> FinancialSummary:
        receivables = self.receivables(open_only=True)
        payables = self.payables(open_only=True)
        today = date.today()
        payments = self.repository.listar_pagamentos_periodo(
            _date(start_date).isoformat(), _date(end_date).isoformat()
        )
        total = lambda values: sum(values, Decimal("0.00"))
        return FinancialSummary(
            total(x.open_amount for x in receivables),
            total(x.open_amount for x in receivables if x.overdue),
            total(x.open_amount for x in payables),
            total(x.open_amount for x in payables if x.due_date == today),
            total(x["valor"] for x in payments if x["tipo"] == "RECEBER"),
            total(x["valor"] for x in payments if x["tipo"] == "PAGAR"),
        )

    def cash_flow(self, start_date, end_date) -> tuple[CashFlowEntry, ...]:
        rows = self.repository.listar_pagamentos_periodo(
            _date(start_date).isoformat(), _date(end_date).isoformat()
        )
        return tuple(CashFlowEntry(
            int(row["id"]), int(row["titulo_id"]), datetime.fromisoformat(str(row["data_pagamento"])),
            "ENTRADA" if row["tipo"] == "RECEBER" else "SAIDA", row["valor"],
            str(row.get("origem") or ""), str(row.get("descricao") or ""),
            str(row.get("documento") or row.get("origem_id") or ""),
        ) for row in rows)

    def create_title(self, title_type: str, command: CreateFinancialTitleCommand, *, user: str, idempotency_key=None, operation_fingerprint=None) -> PersistedFinancialAction:
        values = dict(
            tipo=title_type, valor=command.amount, data_vencimento=command.due_date,
            pessoa_id=command.party_id, pessoa_nome=command.party_name,
            documento=command.document, descricao=command.description,
            observacao=command.notes, data_emissao=command.issue_date, usuario=user,
        )
        if idempotency_key is not None or operation_fingerprint is not None:
            if not idempotency_key or not operation_fingerprint:
                raise ValueError("Chave e identificação idempotentes são obrigatórias juntas.")
            result = self.service.criar_titulo_assistido(
                idempotency_key=idempotency_key,
                operation_fingerprint=operation_fingerprint, **values,
            )
            return PersistedFinancialAction(
                result["title_id"], result["status"], result["open_amount"],
                result["payment_id"], bool(result["idempotent_replay"]),
            )
        title_id = self.service.criar_titulo(**values)
        title = self.service.obter_titulo(title_id)
        return PersistedFinancialAction(title_id, title["status"], title["saldo_aberto"])

    def settle(self, title_type: str, command: SettleFinancialTitleCommand, *, user: str, idempotency_key=None, operation_fingerprint=None) -> PersistedFinancialAction:
        title = self.service.obter_titulo(command.title_id)
        if str(title.get("tipo") or "").upper() != title_type:
            raise ValueError(f"O título não é do tipo {title_type}.")
        values = dict(
            forma_pagamento=command.payment_method, observacao=command.notes,
            usuario=user, data_pagamento=command.payment_date,
        )
        if idempotency_key is not None or operation_fingerprint is not None:
            if not idempotency_key or not operation_fingerprint:
                raise ValueError("Chave e identificação idempotentes são obrigatórias juntas.")
            persisted = self.service.baixar_titulo_assistido(
                command.title_id, command.amount, idempotency_key=idempotency_key,
                operation_fingerprint=operation_fingerprint, **values,
            )
            return PersistedFinancialAction(
                persisted["title_id"], persisted["status"], persisted["open_amount"],
                persisted["payment_id"], bool(persisted["idempotent_replay"]),
            )
        result = self.service.pagar(command.title_id, command.amount, **values)
        return PersistedFinancialAction(result.titulo_id, result.status, result.saldo_aberto, result.pagamento_id)

    def cancel(self, title_id: int, *, user: str) -> PersistedFinancialAction:
        self.service.cancelar(title_id, usuario=user)
        title = self.service.obter_titulo(title_id)
        return PersistedFinancialAction(title_id, title["status"], title["saldo_aberto"])

    def reverse_payment(self, payment_id: int, *, user: str) -> PersistedFinancialAction:
        result = self.service.estornar_pagamento(payment_id, usuario=user)
        return PersistedFinancialAction(result.titulo_id, result.status, result.saldo_aberto, result.pagamento_id)
