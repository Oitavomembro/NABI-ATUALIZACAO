from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable

from repositories.decimal_storage import DecimalStorage


@dataclass(frozen=True)
class FinalizedSale:
    sale_id: int
    total: Decimal
    payment_description: str
    change: Decimal
    status: str


class PDVTransactionService:
    """Persiste e cancela vendas do PDV sem depender da interface gráfica."""

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        *,
        estoque_service: Any,
        financeiro_service: Any,
        pdv_service: Any,
    ) -> None:
        self.connection_factory = connection_factory
        self.estoque_service = estoque_service
        self.financeiro_service = financeiro_service
        self.pdv_service = pdv_service

    def finalize_sale(
        self,
        *,
        customer_id: int,
        customer_name: str,
        items: list[dict[str, Any]],
        payments: list[dict[str, Any]],
        received: Any,
        change: Any,
        user: str,
        now: datetime | None = None,
        after_sale_in_transaction: Callable[[Any, int], None] | None = None,
    ) -> FinalizedSale:
        if int(customer_id) <= 0:
            raise ValueError("Cliente inválido para finalizar a venda.")
        if not items:
            raise ValueError("O carrinho de compras está vazio.")

        total = self.pdv_service.totalizar(items)
        validated_received, validated_change = self.pdv_service.validar_pagamentos(total, payments)
        received_decimal = DecimalStorage.to_decimal(received, field="valor recebido").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        change_decimal = DecimalStorage.to_decimal(change, field="troco").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if received_decimal != validated_received or change_decimal != validated_change:
            raise ValueError("Os valores recebidos não correspondem aos pagamentos informados.")

        normalized_user = str(user or "Sistema").strip() or "Sistema"
        current = now or datetime.now()
        date_text = current.strftime("%d/%m/%Y %H:%M:%S")
        credit_payment = next((p for p in payments if str(p.get("forma", "")).strip().upper() == "CREDIARIO"), None)
        credit = credit_payment is not None
        financed_value = self.pdv_service._money(credit_payment.get("valor", 0), field="valor financiado") if credit else Decimal("0.00")
        installment_count = max(1, int(credit_payment.get("parcelas", 1))) if credit else 1
        first_due_text = str(credit_payment.get("primeiro_vencimento", "")).strip() if credit else ""
        if first_due_text:
            try:
                first_due = datetime.strptime(first_due_text[:10], "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError("Primeiro vencimento inválido para o crediário.") from exc
        else:
            first_due = current + timedelta(days=30)
        due_date = first_due.strftime("%Y-%m-%d")
        payment_status = "PENDENTE" if credit else "PAGO"
        open_value = financed_value if credit else Decimal("0.00")
        payment_description = " + ".join(
            f"{str(payment['forma']).strip().upper()} R$ {self.pdv_service._money(payment['valor'], field='valor do pagamento'):.2f}"
            for payment in payments
        )
        description = " | ".join(
            f"{float(item['qtd']):g}x {item['item']}"
            f"{' [AVULSO/SEM ESTOQUE]' if item.get('item_avulso') else ''}"
            f"{' [ESTOQUE NEGATIVO AUTORIZADO]' if item.get('estoque_override') else ''}"
            f" (R$ {self.pdv_service._money(item['subtotal'], field='subtotal do item'):.2f})"
            for item in items
        )

        conn = self.connection_factory()
        try:
            conn.execute("BEGIN")
            movement_columns = {str(row[1]).casefold() for row in conn.execute("PRAGMA table_info(movimentacoes)").fetchall()}
            if {"valor_decimal", "valor_aberto_decimal"}.issubset(movement_columns):
                cursor = conn.execute(
                    """
                    INSERT INTO movimentacoes
                        (cliente_id, tipo, descricao, valor, valor_decimal, data, vencimento,
                         status_pagamento, valor_aberto, valor_aberto_decimal, forma_pagamento)
                    VALUES (?, 'COMPRA', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(customer_id), description, DecimalStorage.legacy_real(total, field="total da venda"), DecimalStorage.canonical(total, field="total da venda"), date_text, due_date,
                        payment_status, DecimalStorage.legacy_real(open_value, field="valor em aberto"), DecimalStorage.canonical(open_value, field="valor em aberto"), payment_description,
                    ),
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO movimentacoes
                        (cliente_id, tipo, descricao, valor, data, vencimento,
                         status_pagamento, valor_aberto, forma_pagamento)
                    VALUES (?, 'COMPRA', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (int(customer_id), description, DecimalStorage.legacy_real(total, field="total da venda"), date_text, due_date, payment_status, DecimalStorage.legacy_real(open_value, field="valor em aberto"), payment_description),
                )
            sale_id = int(cursor.lastrowid)
            installment_total = financed_value if credit else total
            base_value = (installment_total / Decimal(installment_count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            accumulated = Decimal("0")
            for installment_number in range(1, installment_count + 1):
                installment_value = (
                    (installment_total - accumulated).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if installment_number == installment_count
                    else base_value
                )
                accumulated += installment_value
                installment_due = (first_due + timedelta(days=30 * (installment_number - 1))).strftime("%Y-%m-%d")
                parcel_columns = {str(row[1]).casefold() for row in conn.execute("PRAGMA table_info(parcelas)").fetchall()}
                paid_value = installment_value if payment_status == "PAGO" else Decimal("0")
                if {"valor_parcela_decimal", "valor_pago_decimal"}.issubset(parcel_columns):
                    conn.execute(
                        """
                        INSERT INTO parcelas
                            (movimentacao_id, numero_parcela, valor_parcela, valor_parcela_decimal, vencimento,
                             status, valor_pago, valor_pago_decimal, data_pagamento, atraso_registrado, dados_confiaveis)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
                        """,
                        (sale_id, installment_number, DecimalStorage.legacy_real(installment_value, field="valor da parcela"), DecimalStorage.canonical(installment_value, field="valor da parcela"), installment_due, payment_status, DecimalStorage.legacy_real(paid_value, field="valor pago da parcela"), DecimalStorage.canonical(paid_value, field="valor pago da parcela"), date_text if payment_status == "PAGO" else ""),
                    )
                else:
                    conn.execute(
                        """INSERT INTO parcelas
                           (movimentacao_id, numero_parcela, valor_parcela, vencimento, status, valor_pago, data_pagamento, atraso_registrado, dados_confiaveis)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1)""",
                        (sale_id, installment_number, DecimalStorage.legacy_real(installment_value, field="valor da parcela"), installment_due, payment_status, DecimalStorage.legacy_real(paid_value, field="valor pago da parcela"), date_text if payment_status == "PAGO" else ""),
                    )
            if credit:
                colunas_movimentacoes = {
                    str(row[1]).casefold()
                    for row in conn.execute("PRAGMA table_info(movimentacoes)").fetchall()
                }
                if "total_parcelas" in colunas_movimentacoes:
                    conn.execute(
                        "UPDATE movimentacoes SET total_parcelas=? WHERE id=?",
                        (installment_count, sale_id),
                    )
            if credit:
                customer_columns = {str(row[1]).casefold() for row in conn.execute("PRAGMA table_info(clientes)").fetchall()}
                if "saldo_devedor_decimal" in customer_columns:
                    current = conn.execute("SELECT saldo_devedor,saldo_devedor_decimal FROM clientes WHERE id=?", (int(customer_id),)).fetchone()
                    new_balance = DecimalStorage.read(current[1] if current else None, current[0] if current else 0, field="saldo devedor") + financed_value
                    conn.execute("UPDATE clientes SET saldo_devedor=?, saldo_devedor_decimal=? WHERE id=?", (DecimalStorage.legacy_real(new_balance, field="saldo devedor"), DecimalStorage.canonical(new_balance, field="saldo devedor"), int(customer_id)))
                else:
                    conn.execute("UPDATE clientes SET saldo_devedor = saldo_devedor + ? WHERE id = ?", (DecimalStorage.legacy_real(financed_value, field="saldo devedor"), int(customer_id)))
                self.financeiro_service.registrar_venda_crediario_transacao(
                    conn,
                    venda_id=sale_id,
                    cliente_id=int(customer_id),
                    cliente_nome=str(customer_name or "").strip(),
                    valor=DecimalStorage.canonical(total, field="total da venda"),
                    data_vencimento=due_date,
                    descricao=f"Venda a crediário #{sale_id} em {installment_count} parcela(s)",
                    usuario=normalized_user,
                )
            self.pdv_service.registrar_pagamentos_transacao(
                conn,
                sale_id,
                payments,
                total=total,
                recebido=validated_received,
                troco=validated_change,
            )
            self.estoque_service.baixar_itens_venda_na_transacao(
                conn,
                [dict(item) for item in items],
                venda_id=sale_id,
                usuario=normalized_user,
            )
            if after_sale_in_transaction is not None:
                after_sale_in_transaction(conn, sale_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return FinalizedSale(
            sale_id=sale_id,
            total=total,
            payment_description=payment_description,
            change=validated_change,
            status=payment_status,
        )

    def list_cancellable_sales(self, *, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 100))
        conn = self.connection_factory()
        try:
            columns = {str(row[1]).casefold() for row in conn.execute("PRAGMA table_info(movimentacoes)").fetchall()}
            canonical_expr = "valor_decimal" if "valor_decimal" in columns else "NULL"
            rows = conn.execute(
                f"""
                SELECT id, descricao, valor, {canonical_expr}, data, cliente_id, status_pagamento
                  FROM movimentacoes
                 WHERE tipo='COMPRA' AND COALESCE(status_pagamento,'')!='CANCELADO'
                 ORDER BY id DESC
                 LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "id": int(row[0]),
                "descricao": str(row[1] or ""),
                "valor": DecimalStorage.read(row[3], row[2], field="valor da venda"),
                "data": str(row[4] or ""),
                "cliente_id": int(row[5]) if row[5] is not None else None,
                "status_pagamento": str(row[6] or ""),
            }
            for row in rows
        ]

    def cancel_sale(self, sale_id: int, *, user: str) -> None:
        normalized_id = int(sale_id)
        if normalized_id <= 0:
            raise ValueError("Venda inválida para cancelamento.")
        normalized_user = str(user or "Sistema").strip() or "Sistema"
        conn = self.connection_factory()
        try:
            conn.execute("BEGIN")
            movement_columns = {str(row[1]).casefold() for row in conn.execute("PRAGMA table_info(movimentacoes)").fetchall()}
            sale = conn.execute(
                "SELECT valor, "
                + ("valor_decimal" if "valor_decimal" in movement_columns else "NULL")
                + ", cliente_id, status_pagamento, "
                + ("valor_aberto" if "valor_aberto" in movement_columns else "0")
                + ", "
                + ("valor_aberto_decimal" if "valor_aberto_decimal" in movement_columns else "NULL")
                + " FROM movimentacoes WHERE id=? AND tipo='COMPRA'",
                (normalized_id,),
            ).fetchone()
            if not sale:
                raise ValueError("Venda não encontrada.")
            if str(sale[3] or "").upper() == "CANCELADO":
                raise ValueError("A venda já está cancelada.")
            open_value = DecimalStorage.read(sale[5], sale[4], field="valor em aberto")

            self.estoque_service.estornar_venda_na_transacao(
                conn, normalized_id, usuario=normalized_user
            )
            self.financeiro_service.cancelar_titulos_origem_transacao(
                conn,
                tipo="RECEBER",
                origem="VENDA",
                origem_id=normalized_id,
                usuario=normalized_user,
            )
            if "valor_aberto_decimal" in movement_columns:
                conn.execute("UPDATE movimentacoes SET status_pagamento='CANCELADO', valor_aberto=0, valor_aberto_decimal='0' WHERE id=?", (normalized_id,))
            else:
                conn.execute("UPDATE movimentacoes SET status_pagamento='CANCELADO', valor_aberto=0 WHERE id=?", (normalized_id,))
            parcel_columns = {str(row[1]).casefold() for row in conn.execute("PRAGMA table_info(parcelas)").fetchall()}
            if "valor_pago_decimal" in parcel_columns:
                conn.execute("UPDATE parcelas SET status='CANCELADO', valor_pago=0, valor_pago_decimal='0' WHERE movimentacao_id=?", (normalized_id,))
            else:
                conn.execute("UPDATE parcelas SET status='CANCELADO', valor_pago=0 WHERE movimentacao_id=?", (normalized_id,))
            customer_id = sale[2]
            if customer_id is not None:
                customer_columns = {str(row[1]).casefold() for row in conn.execute("PRAGMA table_info(clientes)").fetchall()}
                if "saldo_devedor_decimal" in customer_columns:
                    current = conn.execute(
                        "SELECT saldo_devedor, saldo_devedor_decimal FROM clientes WHERE id=?",
                        (int(customer_id),),
                    ).fetchone()
                    current_balance = DecimalStorage.read(
                        current[1] if current else None,
                        current[0] if current else 0,
                        field="saldo devedor",
                    )
                    new_balance = max(Decimal("0"), current_balance - open_value)
                    conn.execute(
                        "UPDATE clientes SET saldo_devedor=?, saldo_devedor_decimal=? WHERE id=?",
                        (
                            DecimalStorage.legacy_real(new_balance, field="saldo devedor"),
                            DecimalStorage.canonical(new_balance, field="saldo devedor"),
                            int(customer_id),
                        ),
                    )
                else:
                    conn.execute(
                        "UPDATE clientes SET saldo_devedor=MAX(0, saldo_devedor-?) WHERE id=?",
                        (DecimalStorage.legacy_real(open_value, field="saldo devedor"), int(customer_id)),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
