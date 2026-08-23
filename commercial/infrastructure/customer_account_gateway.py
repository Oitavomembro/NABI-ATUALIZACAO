from __future__ import annotations

from datetime import date
from decimal import Decimal

from commercial.application.customer_dto import (
    CustomerDetails, CustomerInstallment, CustomerReceiptSummary,
    CustomerStatement, CustomerStatementEntry,
)
from commercial.domain.money import MoneyCodec
from repositories.decimal_storage import DecimalStorage


class NabiCodeCustomerAccountGateway:
    """Projeção da ficha usando o schema atual sem expor linhas SQLite."""

    def __init__(self, *, database, financeiro_repository) -> None:
        self.database = database
        self.financeiro_repository = financeiro_repository

    def details(self, customer_id: int) -> CustomerDetails | None:
        columns = {str(row[1]) for row in self.database.fetch_all("PRAGMA table_info(clientes)")}
        limit_canonical = "limite_decimal" if "limite_decimal" in columns else "NULL"
        balance_canonical = (
            "saldo_devedor_decimal" if "saldo_devedor_decimal" in columns else "NULL"
        )
        row = self.database.fetch_one(
            f"""SELECT id,codigo,numero_ficha,nome,cpf,rg,telefone,endereco,observacoes,
                       limite,saldo_devedor,{limit_canonical},{balance_canonical}
                  FROM clientes WHERE id=?""",
            (int(customer_id),),
        )
        if row is None:
            return None
        limit = DecimalStorage.read(row[11], row[9] or 0, field="limite")
        balance = DecimalStorage.read(row[12], row[10] or 0, field="saldo devedor")
        return CustomerDetails(
            customer_id=int(row[0]), code=str(row[1] or ""),
            record_number=int(row[2]) if row[2] not in (None, "") else None,
            name=str(row[3] or ""), cpf=str(row[4] or ""), rg=str(row[5] or ""),
            phone=str(row[6] or ""), address=str(row[7] or ""), notes=str(row[8] or ""),
            credit_limit=limit, debt_balance=balance,
            available_credit=max(MoneyCodec.ZERO, limit - balance),
        )

    def details_many(self, customer_ids: tuple[int, ...]) -> tuple[CustomerDetails, ...]:
        ids = tuple(dict.fromkeys(int(value) for value in customer_ids if int(value) > 0))
        if not ids:
            return ()
        columns = {str(row[1]) for row in self.database.fetch_all("PRAGMA table_info(clientes)")}
        limit_canonical = "limite_decimal" if "limite_decimal" in columns else "NULL"
        balance_canonical = (
            "saldo_devedor_decimal" if "saldo_devedor_decimal" in columns else "NULL"
        )
        placeholders = ",".join("?" for _ in ids)
        rows = self.database.fetch_all(
            f"""SELECT id,codigo,numero_ficha,nome,cpf,rg,telefone,endereco,observacoes,
                       limite,saldo_devedor,{limit_canonical},{balance_canonical}
                  FROM clientes WHERE id IN ({placeholders})""",
            ids,
        )
        details_by_id = {}
        for row in rows:
            limit = DecimalStorage.read(row[11], row[9] or 0, field="limite")
            balance = DecimalStorage.read(row[12], row[10] or 0, field="saldo devedor")
            details_by_id[int(row[0])] = CustomerDetails(
                customer_id=int(row[0]), code=str(row[1] or ""),
                record_number=int(row[2]) if row[2] not in (None, "") else None,
                name=str(row[3] or ""), cpf=str(row[4] or ""), rg=str(row[5] or ""),
                phone=str(row[6] or ""), address=str(row[7] or ""), notes=str(row[8] or ""),
                credit_limit=limit, debt_balance=balance,
                available_credit=max(MoneyCodec.ZERO, limit - balance),
            )
        return tuple(details_by_id[value] for value in ids if value in details_by_id)

    def open_installments(self, customer_id: int) -> tuple[CustomerInstallment, ...]:
        today = date.today()
        result = []
        for row in self.financeiro_repository.listar_parcelas_abertas_cliente(int(customer_id)):
            due_text = str(row.get("vencimento") or "")[:10]
            try:
                due = date.fromisoformat(due_text) if due_text else None
            except ValueError:
                due = None
            amount = row["valor_parcela"]
            paid = row["valor_pago"]
            open_amount = max(MoneyCodec.ZERO, amount - paid)
            result.append(CustomerInstallment(
                installment_id=int(row["id"]), sale_id=int(row["movimentacao_id"]),
                number=int(row.get("numero_parcela") or 0), amount=amount,
                paid_amount=paid, open_amount=open_amount, due_date=due,
                status=str(row.get("status") or "PENDENTE"),
                overdue=bool(due and due < today and open_amount > 0),
            ))
        return tuple(result)

    def receipts(self, customer_id: int) -> tuple[CustomerReceiptSummary, ...]:
        rows = self.database.fetch_all(
            """SELECT id,data,valor,forma_pagamento,descricao
                 FROM movimentacoes
                WHERE cliente_id=? AND tipo IN ('PAGAMENTO','ABATIMENTO')
                  AND UPPER(COALESCE(status_pagamento,''))<>'CANCELADO'
                ORDER BY id DESC""",
            (int(customer_id),),
        )
        return tuple(CustomerReceiptSummary(
            movement_id=int(row[0]), occurred_at=str(row[1] or ""),
            amount=DecimalStorage.to_decimal(row[2] or 0, field="recebimento"),
            payment_method=str(row[3] or ""), description=str(row[4] or ""),
        ) for row in rows)

    def statement(self, customer_id: int) -> CustomerStatement:
        customer = self.details(customer_id)
        if customer is None:
            raise ValueError("Cliente não encontrado.")
        rows = self.database.fetch_all(
            """SELECT id,data,tipo,descricao,valor,status_pagamento
                 FROM movimentacoes WHERE cliente_id=? ORDER BY id,data""",
            (int(customer_id),),
        )
        entries = []
        for row in rows:
            movement_type = str(row[2] or "").upper()
            status = str(row[5] or "")
            value = DecimalStorage.to_decimal(row[4] or 0, field="lançamento")
            cancelled = status.upper() == "CANCELADO"
            debit = value if movement_type == "COMPRA" and not cancelled else MoneyCodec.ZERO
            credit = value if movement_type in {"PAGAMENTO", "ABATIMENTO"} and not cancelled else MoneyCodec.ZERO
            entries.append(CustomerStatementEntry(
                movement_id=int(row[0]), occurred_at=str(row[1] or ""),
                movement_type=movement_type, description=str(row[3] or ""),
                reference=str(row[0]), debit=debit, credit=credit,
                financial_effect=(debit - credit).quantize(MoneyCodec.CENT), status=status,
            ))
        installments = self.open_installments(customer_id)
        return CustomerStatement(
            customer=customer, entries=tuple(entries), installments=installments,
            receipts=self.receipts(customer_id), pending_amount=customer.debt_balance,
            overdue_amount=sum((item.open_amount for item in installments if item.overdue), MoneyCodec.ZERO),
            historical_running_balance_available=False,
        )
