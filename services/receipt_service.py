from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Mapping, Sequence, Any

from database import DatabaseManager
from helpers.value_parsing import format_date_br
from repositories.receipt_repository import ReceiptRepository
from validators import ReceiptValidator


@dataclass(frozen=True)
class ReceiptCustomer:
    name: str
    code: str
    record_number: str
    phone: str
    address: str


class ReceiptService:
    """Monta comprovantes textuais do PDV sem depender da interface gráfica."""

    def __init__(
        self,
        database: DatabaseManager,
        *,
        config_getter: Callable[[str], str],
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._database = database
        self._repository = ReceiptRepository(database)
        self._config_getter = config_getter
        self._now = now

    _date_br = staticmethod(format_date_br)

    def customer(self, customer_id: int | None) -> ReceiptCustomer:
        if customer_id in (None, "", 0, "0"):
            return ReceiptCustomer("CONSUMIDOR FINAL", "", "", "", "")
        try:
            normalized_id = int(customer_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Cliente inválido para emissão do comprovante.") from exc
        if normalized_id <= 0:
            raise ValueError("Cliente inválido para emissão do comprovante.")

        row = self._repository.customer(normalized_id)
        if not row:
            raise ValueError("Cliente não encontrado para emissão do comprovante.")
        return ReceiptCustomer(
            name=str(row[0] or "Cliente"),
            code=str(row[1] or ""),
            record_number=str(row[2] or ""),
            phone=str(row[3] or ""),
            address=str(row[4] or ""),
        )

    def build_payment_text(
        self,
        movement_id: int,
        allocations: Sequence[Mapping[str, Any]] | None = None,
        *,
        balance_before: Any | None = None,
        balance_after: Any | None = None,
    ) -> str:
        """Monta recibo textual detalhado para impressão direta em cupom/A4."""
        payment = self._repository.payment(int(movement_id))
        if not payment:
            raise ValueError("Pagamento não encontrado para emissão do recibo.")

        (
            _customer_id, customer_name, customer_code, record_number,
            description, value, date, payment_method, responsible,
        ) = payment
        allocations = list(allocations or [])
        reconciled_balance_before = float(balance_before) if balance_before is not None else None
        reconciled_balance_after = float(balance_after) if balance_after is not None else None
        width = 42
        lines = [
            self._config_getter("nome_loja") or "NabiCode",
            "RECIBO DE PAGAMENTO",
            "=" * width,
            f"Recibo: {movement_id}",
            f"Data: {date}",
            f"Cliente: {customer_name}",
            f"Código: {customer_code or '-'}   Ficha: {record_number or '-'}",
            f"Forma: {payment_method or 'Não informada'}",
        ]
        if responsible:
            lines.append(f"Responsável: {responsible}")
        if description:
            lines.append(f"Obs.: {description}")
        lines.extend([
            "-" * width,
            f"VALOR RECEBIDO: R$ {float(value or 0):.2f}",
        ])
        if reconciled_balance_before is not None:
            lines.append(f"Saldo antes: R$ {reconciled_balance_before:.2f}")
        if reconciled_balance_after is not None:
            lines.append(f"Saldo depois: R$ {reconciled_balance_after:.2f}")

        if allocations:
            lines.extend(["-" * width, "DISTRIBUIÇÃO DO PAGAMENTO"])
            for position, allocation in enumerate(allocations, 1):
                if allocation.get("tipo") == "SALDO_LEGADO":
                    lines.append(f"{position}. Saldo histórico migrado")
                    lines.append(
                        f"   Aplicado agora: R$ {float(allocation.get('valor_aplicado') or 0):.2f}"
                    )
                    lines.append(
                        f"   Saldo: R$ {float(allocation.get('saldo_antes') or 0):.2f}"
                        f" -> R$ {float(allocation.get('saldo_depois') or 0):.2f}"
                    )
                    continue
                sale_id = int(allocation.get("venda_id") or 0)
                sale = self._repository.sale_allocation(sale_id)
                lines.append(f"{position}. Venda #{sale_id}")
                if sale:
                    sale_date, sale_description, sale_value, _sale_open, total_installments, sale_status = sale
                    lines.append(f"   Data: {sale_date or '-'}")
                    lines.append(f"   {sale_description or 'Venda'}")
                    lines.append(f"   Valor da venda: R$ {float(sale_value or 0):.2f}")
                    lines.append(f"   Situação: {sale_status or '-'}")
                    lines.append(f"   Parcelas: {int(total_installments or 1)}")
                lines.append(
                    f"   Aplicado agora: R$ {float(allocation.get('valor_aplicado') or 0):.2f}"
                )
                lines.append(
                    f"   Saldo: R$ {float(allocation.get('saldo_antes') or 0):.2f}"
                    f" -> R$ {float(allocation.get('saldo_depois') or 0):.2f}"
                )
                parcelas_aplicadas={int(item.get("parcela_id")) for item in allocation.get("parcelas_aplicadas",[]) if item.get("parcela_id")}
                parcels = self._repository.parcels(sale_id)
                for parcel_id, number, amount, due, status, paid, paid_at in parcels:
                    destaque="PAGA NESTE RECEBIMENTO - " if int(parcel_id) in parcelas_aplicadas else ""
                    parcel_line = (
                        f"   {destaque}P{number}: venc {due or '-'} | "
                        f"R$ {float(amount or 0):.2f} | pago R$ {float(paid or 0):.2f} | {status}"
                    )
                    if paid_at:
                        parcel_line += f" em {paid_at}"
                    lines.append(parcel_line)
        else:
            lines.append("Pagamento aplicado ao saldo geral da ficha.")

        lines.append("=" * width)
        footer = (self._config_getter("rodape_cupom") or "").strip()
        if footer:
            lines.extend([footer, ""])
        lines.extend(["", "Assinatura: __________________________", "", ""])
        return "\n".join(lines) + "\n"

    def build_sale_text(
        self,
        customer_id: int,
        items: Sequence[Mapping[str, Any]],
        total: float,
        document_type: str,
        sale_id: int | None = None,
    ) -> str:
        customer = self.customer(customer_id)
        kind, normalized_total = ReceiptValidator.sale_header(document_type, items, total)

        width = 42
        title = {
            "ENTREGA": "CUPOM DE ENTREGA",
            "ORCAMENTO": "ORÇAMENTO — SEM VALOR FISCAL",
        }.get(kind, "COMPROVANTE DE VENDA")
        lines = [
            self._config_getter("nome_loja") or "NabiCode",
            title,
            "=" * width,
            f"Data: {self._now():%d/%m/%Y %H:%M:%S}",
            f"Cliente: {customer.name}",
        ]
        final_consumer = str(customer.code or "").strip().upper() == "CONSUMIDOR_FINAL"
        if not final_consumer:
            lines.append(
                f"Código: {customer.code or '-'}   Ficha: {customer.record_number or '-'}"
            )
        if kind == "ENTREGA":
            lines.extend(
                [
                    f"Telefone: {customer.phone or '-'}",
                    f"Endereço: {customer.address or '-'}",
                ]
            )
        if sale_id:
            sale = self._repository.sale_payment_plan(int(sale_id))
            if sale:
                forma,qtd,aberto,status=sale; lines.extend([f"Venda: #{sale_id}",f"Pagamento: {forma or 'Não informado'}"])
                financed = (
                    float(aberto or 0) > 0
                    and str(status).upper() in {"PENDENTE", "PARCIAL"}
                )
                if financed:
                    total_parcelas = int(qtd or 1)
                    lines.append(f"Compra a prazo: {total_parcelas} parcela(s)")
                    for numero, valor, venc, _status in self._repository.payment_plan_parcels(int(sale_id)):
                        lines.append(
                            f"{int(numero):02d}/{total_parcelas:02d}  "
                            f"R$ {float(valor or 0):.2f}  {self._date_br(venc)}"
                        )
                    lines.append(f"Saldo financiado: R$ {float(aberto or 0):.2f}")
        lines.append("-" * width)
        calculated_total = 0.0
        for item in items:
            name, quantity, price, subtotal = ReceiptValidator.sale_item(item)
            calculated_total += subtotal
            lines.append(f"{quantity:g}x {name}")
            lines.append(f"  R$ {price:.2f}  =  R$ {subtotal:.2f}")

        ReceiptValidator.matching_total(calculated_total, normalized_total)
        lines.extend(["-" * width, f"TOTAL: R$ {normalized_total:.2f}", "=" * width])
        footer = (self._config_getter("rodape_cupom") or "").strip()
        if footer:
            lines.extend([footer, ""])
        return "\n".join(lines) + "\n\n\n"
