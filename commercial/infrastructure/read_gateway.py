from __future__ import annotations

from datetime import date, datetime

from commercial.application.query_dto import (
    CancelledSaleSummary, DailyMovementSummary, DailySaleSummary,
    OverdueChargeSummary, ReceiptSummary,
)
from repositories.decimal_storage import DecimalStorage


class NabiCodeCommercialReadGateway:
    """Converte consultas confiáveis existentes em DTOs comerciais imutáveis."""

    def __init__(self, *, transaction_service, financeiro_repository, cobranca_service, dashboard_repository) -> None:
        self.transaction_service = transaction_service
        self.financeiro_repository = financeiro_repository
        self.cobranca_service = cobranca_service
        self.dashboard_repository = dashboard_repository

    def sales_for_day(self, day: date) -> tuple[DailySaleSummary, ...]:
        rows = self.transaction_service.list_sales_for_day(
            day=datetime.combine(day, datetime.min.time())
        )
        return tuple(
            DailySaleSummary(
                sale_id=row["id"], customer_id=row.get("cliente_id"),
                description=row.get("descricao", ""), total=row["valor"],
                occurred_at=row.get("data", ""), status=row.get("status_pagamento", ""),
                cancelled=str(row.get("status_pagamento", "")).upper() == "CANCELADO",
                fiscal_status=str(row.get("fiscal_status") or ""),
                fiscal_model=str(row.get("fiscal_model") or ""),
                access_key=str(row.get("access_key") or ""),
                protocol=str(row.get("protocol") or ""),
                fiscal_environment=str(row.get("fiscal_environment") or ""),
                fiscal_authorized_at=str(row.get("fiscal_authorized_at") or ""),
            )
            for row in rows
        )

    def receipts_for_day(self, day: date) -> tuple[ReceiptSummary, ...]:
        start = day.isoformat()
        rows = self.financeiro_repository.listar_pagamentos_periodo(
            start, f"{start} 23:59:59"
        )
        return tuple(
            ReceiptSummary(
                payment_id=int(row["id"]), title_id=int(row["titulo_id"]),
                amount=row["valor"], payment_method=str(row.get("forma_pagamento") or ""),
                paid_at=str(row.get("data_pagamento") or ""),
                customer_name=str(row.get("pessoa_nome") or ""),
            )
            for row in rows
        )

    def overdue_charges(self) -> tuple[OverdueChargeSummary, ...]:
        return tuple(
            OverdueChargeSummary(
                installment_id=int(row["parcela_id"]), customer_id=int(row["cliente_id"]),
                customer_name=str(row.get("nome") or ""),
                installment_number=int(row.get("numero_parcela") or 0),
                open_amount=DecimalStorage.to_decimal(row.get("valor_aberto") or 0, field="valor vencido"),
                due_date=date.fromisoformat(str(row["vencimento"])[:10]),
            )
            for row in self.cobranca_service.listar_atrasadas()
        )

    def cancelled_sales_for_day(self, day: date) -> tuple[CancelledSaleSummary, ...]:
        return tuple(
            CancelledSaleSummary(
                sale_id=sale.sale_id, customer_id=sale.customer_id,
                description=sale.description, total=sale.total, occurred_at=sale.occurred_at,
            )
            for sale in self.sales_for_day(day) if sale.cancelled
        )

    def movements_for_day(self, day: date) -> tuple[DailyMovementSummary, ...]:
        history = self.dashboard_repository.day_history(
            day=datetime.combine(day, datetime.min.time())
        )
        return tuple(
            DailyMovementSummary(
                movement_id=row.movement_id, occurred_at=row.timestamp,
                customer_name=row.customer_name, movement_type=row.movement_type,
                description=row.description, amount=row.value,
            )
            for row in history.movements
        )
