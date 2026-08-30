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


class CreditLimitExceededError(ValueError):
    def __init__(
        self,
        *,
        limit: Decimal,
        balance: Decimal,
        available: Decimal,
        financed: Decimal,
    ) -> None:
        def brl(value: Decimal) -> str:
            return f"{value:,.2f}".translate(str.maketrans({",": ".", ".": ","}))

        self.limit = limit
        self.balance = balance
        self.available = available
        self.financed = financed
        super().__init__(
            "Limite de crédito insuficiente.\n\n"
            f"Limite: R$ {brl(limit)}\n"
            f"Saldo devedor: R$ {brl(balance)}\n"
            f"Crédito disponível: R$ {brl(available)}\n"
            f"Valor financiado: R$ {brl(financed)}"
        )


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

    @staticmethod
    def _credit_customer(
        connection: Any, customer_id: int, financed_value: Decimal,
        *, allow_limit_override: bool = False,
    ) -> dict[str, Any]:
        columns = {
            str(row[1]).casefold()
            for row in connection.execute("PRAGMA table_info(clientes)").fetchall()
        }
        required = {"id", "codigo", "nome", "numero_ficha", "limite", "saldo_devedor"}
        if not required.issubset(columns):
            missing = ", ".join(sorted(required - columns))
            raise RuntimeError(
                f"Cadastro de clientes incompatível com a validação de crédito: {missing}."
            )
        canonical_balance = (
            "saldo_devedor_decimal" if "saldo_devedor_decimal" in columns else "NULL"
        )
        row = connection.execute(
            f"""SELECT id, numero_ficha, codigo, nome, limite,
                       saldo_devedor, {canonical_balance}
                  FROM clientes
                 WHERE id=?""",
            (int(customer_id),),
        ).fetchone()
        if row is None:
            raise ValueError("Cliente inexistente não pode utilizar crediário.")

        code = str(row[2] or "").strip().upper()
        name = str(row[3] or "").strip()
        if code == "CONSUMIDOR_FINAL" or name.upper() == "CONSUMIDOR FINAL":
            raise ValueError("Consumidor Final não pode utilizar crediário.")

        limit = DecimalStorage.to_decimal(row[4] or 0, field="limite de crédito").quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        balance = DecimalStorage.read(
            row[6], row[5] or 0, field="saldo devedor"
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        available = max(Decimal("0.00"), limit - balance).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if financed_value > available and not allow_limit_override:
            raise CreditLimitExceededError(
                limit=limit,
                balance=balance,
                available=available,
                financed=financed_value,
            )
        return {
            "numero_ficha": row[1],
            "nome": name,
            "saldo_devedor": balance,
            "columns": columns,
        }

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
        allow_credit_override: bool = False,
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
            conn.execute("BEGIN IMMEDIATE" if financed_value > 0 else "BEGIN")
            credit_customer = (
                self._credit_customer(
                    conn, int(customer_id), financed_value,
                    allow_limit_override=allow_credit_override,
                )
                if financed_value > 0
                else None
            )
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
                customer_columns = credit_customer["columns"]
                new_balance = credit_customer["saldo_devedor"] + financed_value
                if "saldo_devedor_decimal" in customer_columns:
                    cursor_balance = conn.execute("UPDATE clientes SET saldo_devedor=?, saldo_devedor_decimal=? WHERE id=?", (DecimalStorage.legacy_real(new_balance, field="saldo devedor"), DecimalStorage.canonical(new_balance, field="saldo devedor"), int(customer_id)))
                else:
                    cursor_balance = conn.execute("UPDATE clientes SET saldo_devedor=? WHERE id=?", (DecimalStorage.legacy_real(new_balance, field="saldo devedor"), int(customer_id)))
                if cursor_balance.rowcount != 1:
                    raise RuntimeError("O cliente deixou de existir durante a venda a crediário.")
                self.financeiro_service.registrar_venda_crediario_transacao(
                    conn,
                    venda_id=sale_id,
                    cliente_id=int(customer_id),
                    cliente_nome=credit_customer["nome"],
                    valor=DecimalStorage.canonical(financed_value, field="valor financiado"),
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

    @staticmethod
    def consume_committed_cart(
        cart: list[dict[str, Any]], *, history_callback: Callable[[], None]
    ) -> tuple[list[dict[str, Any]], Exception | None]:
        """Invalida o carrinho confirmado antes de executar efeitos secundários."""
        committed_items = [dict(item) for item in cart]
        cart.clear()
        try:
            history_callback()
        except Exception as exc:  # a venda principal já foi confirmada
            return committed_items, exc
        return committed_items, None

    def list_sales_for_day(self, *, day: datetime | None = None) -> list[dict[str, Any]]:
        """Lista todas as vendas do dia, inclusive canceladas, com estado fiscal."""
        selected = day or datetime.now()
        return self.list_sales_for_period(
            start_date=selected.date().isoformat(), end_date=selected.date().isoformat()
        )

    def list_sales_for_period(self, *, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Lista vendas fiscais e não fiscais no período, aceitando datas legadas."""
        start = datetime.strptime(str(start_date)[:10], "%Y-%m-%d").date().isoformat()
        end = datetime.strptime(str(end_date)[:10], "%Y-%m-%d").date().isoformat()
        if start > end:
            raise ValueError("A data inicial não pode ser posterior à data final.")
        conn = self.connection_factory()
        try:
            movement_columns = {
                str(row[1]).casefold()
                for row in conn.execute("PRAGMA table_info(movimentacoes)").fetchall()
            }
            canonical_expr = "m.valor_decimal" if "valor_decimal" in movement_columns else "NULL"
            fiscal_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='fiscal_sale_documents'"
            ).fetchone()
            fiscal_join = "LEFT JOIN fiscal_sale_documents f ON f.sale_id=m.id" if fiscal_exists else ""
            fiscal_columns = {
                str(row[1]).casefold()
                for row in conn.execute("PRAGMA table_info(fiscal_sale_documents)").fetchall()
            } if fiscal_exists else set()
            fiscal_field = lambda name: f"COALESCE(f.{name},'')" if name in fiscal_columns else "''"
            fiscal_fields = ",".join(fiscal_field(name) for name in (
                "status", "model", "access_key", "protocol", "environment", "created_at",
                "last_error",
            ))
            rows = conn.execute(
                f"""
                SELECT m.id,m.descricao,m.valor,{canonical_expr},m.data,m.cliente_id,
                       COALESCE(m.status_pagamento,''),{fiscal_fields}
                  FROM movimentacoes m
                  {fiscal_join}
                 WHERE m.tipo='COMPRA' AND
                       (CASE WHEN substr(COALESCE(m.data,''),3,1)='/'
                             THEN substr(m.data,7,4)||'-'||substr(m.data,4,2)||'-'||substr(m.data,1,2)
                             ELSE substr(COALESCE(m.data,''),1,10) END) BETWEEN ? AND ?
                 ORDER BY m.id DESC
                """,
                (start, end),
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "id": int(row[0]), "descricao": str(row[1] or ""),
                "valor": DecimalStorage.read(row[3], row[2], field="valor da venda"),
                "data": str(row[4] or ""),
                "cliente_id": int(row[5]) if row[5] is not None else None,
                "status_pagamento": str(row[6] or ""),
                "fiscal_status": str(row[7] or ""), "fiscal_model": str(row[8] or ""),
                "access_key": str(row[9] or ""), "protocol": str(row[10] or ""),
                "fiscal_environment": str(row[11] or ""),
                "fiscal_authorized_at": str(row[12] or ""),
                "fiscal_last_error": str(row[13] or ""),
            }
            for row in rows
        ]

    def cancel_sale(
        self, sale_id: int, *, user: str,
        before_cancel_commit: Callable[[Any, int], None] | None = None,
    ) -> None:
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
            if before_cancel_commit is not None:
                before_cancel_commit(conn, normalized_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
