from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from database import DatabaseManager
from helpers.value_parsing import parse_system_date
from repositories.decimal_storage import DecimalStorage


@dataclass(frozen=True)
class ClientHistoryData:
    client: tuple[Any, ...]
    transactions: list[tuple[Any, ...]]
    stats: tuple[Any, ...]
    purchase_summary: dict[str, Any]
    events: list[tuple[Any, ...]]


class ClientHistoryRepository:
    """Leitura consolidada do histórico do cliente e análise de atrasos."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    parse_date = staticmethod(parse_system_date)

    def load(self, client_id: int) -> ClientHistoryData | None:
        client_id = int(client_id)
        if client_id <= 0:
            raise ValueError("Cliente inválido.")

        with self.database.session() as connection:
            # Um snapshot curto por abertura do histórico: o saldo vem diretamente
            # de clientes.saldo_devedor após o commit do Financeiro e não é recalculado.
            connection.execute("BEGIN")
            client_row = connection.execute(
                "SELECT numero_ficha, nome, limite, saldo_devedor, observacoes FROM clientes WHERE id=?",
                (client_id,),
            ).fetchone()
            if not client_row:
                return None

            transactions = connection.execute(
                """SELECT id,tipo,descricao,valor,data FROM movimentacoes
                   WHERE cliente_id=? ORDER BY id DESC LIMIT 12""",
                (client_id,),
            ).fetchall()
            stats_row = connection.execute(
                """SELECT COUNT(*),
                          COALESCE(SUM(CASE WHEN tipo='COMPRA' THEN valor ELSE 0 END),0),
                          COALESCE(SUM(CASE WHEN tipo IN ('PAGAMENTO','ABATIMENTO') THEN valor ELSE 0 END),0)
                   FROM movimentacoes WHERE cliente_id=?""",
                (client_id,),
            ).fetchone()
            purchase_rows = connection.execute(
                """SELECT m.id, m.descricao, m.valor, m.data, m.total_parcelas,
                          p.numero_parcela, p.valor_parcela, p.vencimento, p.status,
                          COALESCE(p.valor_pago,0), COALESCE(p.data_pagamento,''),
                          COALESCE(p.atraso_registrado,0), COALESCE(p.dados_confiaveis,1)
                   FROM movimentacoes m
                   LEFT JOIN parcelas p ON p.movimentacao_id=m.id
                   WHERE m.cliente_id=? AND m.tipo='COMPRA'
                   ORDER BY m.id DESC, p.numero_parcela ASC""",
                (client_id,),
            ).fetchall()
            events = connection.execute(
                """SELECT evento,detalhes,data FROM historico_clientes
                   WHERE cliente_id=? ORDER BY id DESC LIMIT 20""",
                (client_id,),
            ).fetchall()

        return ClientHistoryData(
            client=tuple(client_row),
            transactions=[tuple(row) for row in transactions],
            stats=tuple(stats_row) if stats_row else (0, 0.0, 0.0),
            purchase_summary=self._purchase_summary([tuple(row) for row in purchase_rows]),
            events=[tuple(row) for row in events],
        )

    def _purchase_summary(self, rows: list[tuple[Any, ...]]) -> dict[str, Any]:
        today = datetime.now().date()
        purchases: dict[int, dict[str, Any]] = {}
        for row in rows:
            (
                movement_id,
                description,
                value,
                purchase_date,
                total_installments,
                number,
                installment_value,
                due_date,
                status,
                paid_value,
                payment_date,
                saved_delay,
                trustworthy,
            ) = row
            purchase = purchases.setdefault(
                int(movement_id),
                {
                    "id": int(movement_id),
                    "descricao": description or "Compra sem descrição",
                    "valor": DecimalStorage.to_decimal(value or 0, field="valor da compra"),
                    "data": purchase_date or "",
                    "total_previsto": int(total_installments or 1),
                    "parcelas": [],
                },
            )
            if number is None:
                continue

            due_dt = self.parse_date(due_date)
            paid_dt = self.parse_date(payment_date)
            paid = str(status or "").upper() == "PAGO"
            delayed = bool(saved_delay)
            if trustworthy:
                if paid and due_dt and paid_dt and paid_dt.date() > due_dt.date():
                    delayed = True
                elif not paid and due_dt and due_dt.date() < today:
                    delayed = True
            purchase["parcelas"].append(
                {
                    "numero": int(number or 0),
                    "valor": DecimalStorage.to_decimal(installment_value or 0, field="valor da parcela"),
                    "vencimento": due_date or "",
                    "status": status or "PENDENTE",
                    "valor_pago": DecimalStorage.to_decimal(paid_value or 0, field="valor pago da parcela"),
                    "data_pagamento": payment_date or "",
                    "atrasada": delayed,
                    "confiavel": bool(trustworthy),
                }
            )

        bands: Counter[Any] = Counter()
        issued = paid_on_time = paid_late = overdue_open = unknown = 0
        first = last = None
        for purchase in purchases.values():
            purchase_dt = self.parse_date(purchase["data"])
            if purchase_dt:
                first = purchase_dt if first is None or purchase_dt < first else first
                last = purchase_dt if last is None or purchase_dt > last else last

            reliable = [item for item in purchase["parcelas"] if item["confiavel"]]
            unknown += sum(1 for item in purchase["parcelas"] if not item["confiavel"])
            issued += len(reliable)
            delays = 0
            for installment in reliable:
                paid = str(installment["status"]).upper() == "PAGO"
                if paid and installment["atrasada"]:
                    paid_late += 1
                    delays += 1
                elif paid:
                    paid_on_time += 1
                elif installment["atrasada"]:
                    overdue_open += 1
                    delays += 1
            if reliable:
                bands[delays if delays < 4 else 4] += 1
            else:
                bands["sem_dados"] += 1
            purchase["atrasos"] = delays
            purchase["confiavel"] = bool(reliable)

        return {
            "compras": list(purchases.values()),
            "total_compras": len(purchases),
            "faixas": bands,
            "parcelas_emitidas": issued,
            "pagas_prazo": paid_on_time,
            "pagas_atraso": paid_late,
            "vencidas_aberto": overdue_open,
            "parcelas_sem_dados": unknown,
            "primeira_compra": first.strftime("%d/%m/%Y") if first else "—",
            "ultima_compra": last.strftime("%d/%m/%Y") if last else "—",
        }
