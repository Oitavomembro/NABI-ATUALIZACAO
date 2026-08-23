from __future__ import annotations

import logging
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from helpers.value_parsing import format_date_br
from repositories.decimal_storage import DecimalStorage
from services.document_rendering import (
    PDFLineRenderer,
    bold_font_name,
    config_bool,
    profile_for_pdf_model,
    wrap_lines,
)


class PDFDocumentService:
    """Gera comprovantes PDF sem depender da interface gráfica."""

    def __init__(
        self,
        *,
        connection_factory: Callable[[], Any],
        config_getter: Callable[[str], str],
        pdf_dir: str | os.PathLike[str],
        document_registrar: Callable[[int, str, str, str], Any] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._connection_factory = connection_factory
        self._config_getter = config_getter
        self._pdf_dir = Path(pdf_dir)
        self._document_registrar = document_registrar
        self._logger = logger or logging.getLogger(__name__)
        self.last_warning = ""


    @staticmethod
    def _money(value: Any, *, field: str = "valor") -> str:
        return f"{DecimalStorage.to_decimal(value or 0, field=field):.2f}"

    _date_br = staticmethod(format_date_br)

    def config_bool(self, key: str, default: bool = True) -> bool:
        return config_bool(self._config_getter(key), default)

    @staticmethod
    def _model_width_chars(model: str) -> int:
        return profile_for_pdf_model(model).pdf_width_chars

    @classmethod
    def _wrapped_line_count(cls, text: object, model: str) -> int:
        return len(wrap_lines(text, cls._model_width_chars(model)))

    def _estimate_sale_height_mm(
        self,
        *,
        model: str,
        items: Sequence[Mapping[str, Any]],
        document_type: str,
        customer: Sequence[Any],
        footer: str,
        payment_plan: Mapping[str, Any] | None,
    ) -> float:
        if model == "A4":
            return 175

        name, code, record, phone, address, reference, _balance = customer
        lines = 8
        lines += self._wrapped_line_count(f"Cliente: {name}", model)
        lines += self._wrapped_line_count(f"Código: {code or '-'}   Ficha: {record or '-'}", model)
        if document_type == "ENTREGA":
            lines += self._wrapped_line_count(f"Telefone: {phone or '-'}", model)
            lines += self._wrapped_line_count(f"Endereço: {address or '-'}", model)
            if reference:
                lines += self._wrapped_line_count(f"Referência: {reference}", model)

        for item in items:
            lines += self._wrapped_line_count(f"{float(item['qtd']):g}x {item['item']}", model)
            lines += self._wrapped_line_count(
                f"R$ {float(item['preco']):.2f} x {float(item['qtd']):g} = R$ {float(item['subtotal']):.2f}",
                model,
            )

        lines += 4
        if payment_plan:
            lines += 3
            parcelas = payment_plan.get("parcelas", [])
            if parcelas:
                lines += 2 + len(parcelas)
        if footer:
            lines += sum(self._wrapped_line_count(part, model) for part in footer.splitlines())

        reserve_mm = 58
        return max(175, lines * 5.5 + reserve_mm)


    def _render_config(self, mm: float, *, minimum_size: float = 7.0) -> tuple[float, str, float, float]:
        """Retorna parâmetros tipográficos por uma única regra documental."""
        margin = max(2.0, float(self._config_getter("impressao_margem_mm") or 7)) * mm
        font = self._config_getter("impressao_fonte") or "Helvetica"
        size = max(minimum_size, float(self._config_getter("impressao_fonte_tamanho") or 10))
        spacing = max(0.9, float(self._config_getter("impressao_espacamento") or 1.25))
        return margin, font, size, size * spacing

    def _line_renderer(
        self, canvas: Any, *, margin: float, y: float, font: str, size: float, model: str, step: float | None = None
    ) -> PDFLineRenderer:
        return PDFLineRenderer(
            canvas=canvas, margin=margin, y=y, font=font, size=size,
            width_chars=self._model_width_chars(model), step=step or size * 1.35,
        )

    def document_model(self, category: str) -> str:
        model = self._config_getter(f"modelo_{category}") or (
            "Térmica 80 mm" if category == "recibo" else "A4"
        )
        if model == "Térmica 58 mm econômica":
            return "Térmica 80 mm"
        return model

    @staticmethod
    def safe_name(text: object) -> str:
        normalized = (
            unicodedata.normalize("NFKD", str(text or "documento"))
            .encode("ascii", "ignore")
            .decode()
        )
        normalized = re.sub(r"[^A-Za-z0-9_-]+", "_", normalized).strip("_")
        return normalized[:60] or "documento"

    def store_data(self) -> dict[str, str]:
        return {
            "nome": self._config_getter("nome_loja") or "NabiCode",
            "endereco": self._config_getter("endereco"),
            "telefone": self._config_getter("telefone"),
            "cnpj": self._config_getter("cnpj"),
            "email": self._config_getter("email"),
        }

    def generate_sale(
        self,
        customer_id: int,
        items: Sequence[Mapping[str, Any]],
        total: float,
        document_type: str,
        document_id: int | None = None,
        destination: str | os.PathLike[str] | None = None,
    ) -> str:
        customer = self._customer(customer_id)
        name, code, record, phone, address, reference, balance = customer
        category = "entrega" if document_type == "ENTREGA" else "recibo"
        model = self.document_model(category)
        title = {
            "ENTREGA": "COMPROVANTE DE ENTREGA",
            "ORCAMENTO": "ORÇAMENTO — SEM VALOR FISCAL",
        }.get(document_type, "COMPROVANTE DE VENDA")
        base = (
            f"{category}_{document_id or datetime.now().strftime('%H%M%S')}_"
            f"{self.safe_name(name)}_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        )
        path = self._document_path(destination, base)
        footer = self._config_getter("rodape_cupom").strip()
        payment_plan = self._sale_payment_plan(document_id) if document_id else None
        # A altura térmica considera as quebras reais de descrição, endereço,
        # parcelas e rodapé. Isso preserva o layout e impede corte ou sobreposição
        # de QR Code e assinatura em cupons extensos.
        estimated_height = self._estimate_sale_height_mm(
            model=model,
            items=items,
            document_type=document_type,
            customer=customer,
            footer=footer,
            payment_plan=payment_plan,
        )
        canvas, (width, height), mm = self._create_canvas(path, model, estimated_height)
        margin, font, size, step = self._render_config(mm, minimum_size=7)
        y = self._draw_header(canvas, width, height - margin, mm, model, title)
        renderer = self._line_renderer(
            canvas, margin=margin, y=y, font=font, size=size, model=model, step=step
        )

        def line(text: object, bold: bool = False, centered: bool = False) -> None:
            nonlocal y
            y = renderer.draw(text, bold=bold, centered=centered, center_x=width / 2)

        line(f"Data: {datetime.now():%d/%m/%Y %H:%M:%S}")
        line(f"Documento: {document_id or '-'}")
        line(f"Cliente: {name}", True)
        line(f"Código: {code or '-'}   Ficha: {record or '-'}")
        if document_type == "ENTREGA":
            line(f"Telefone: {phone or '-'}")
            line(f"Endereço: {address or '-'}")
            if reference:
                line(f"Referência: {reference}")
        y -= 3
        canvas.line(margin, y, width - margin, y)
        y -= step
        renderer.y = y
        for item in items:
            quantity = float(item["qtd"])
            price = float(item["preco"])
            subtotal = float(item["subtotal"])
            line(f"{quantity:g}x {item['item']}", True)
            line(f"R$ {price:.2f} x {quantity:g} = R$ {subtotal:.2f}")
        y -= 3
        canvas.line(margin, y, width - margin, y)
        y -= step
        renderer.y = y
        line(f"TOTAL: R$ {self._money(total, field='total do documento')}", True)
        line(f"Saldo atual da ficha: R$ {self._money(balance, field='saldo da ficha')}")
        if payment_plan:
            y -= 3
            canvas.line(margin, y, width - margin, y)
            y -= step
            renderer.y = y
            line(f"Pagamento: {payment_plan['forma'] or 'Não informado'}", True)
            parcelas = payment_plan.get("parcelas", [])
            if parcelas:
                total_parcelas = len(parcelas)
                line(f"Parcelas: {total_parcelas}", True)
                for parcela in parcelas:
                    numero = int(parcela["numero"] or 0)
                    line(
                        f"{numero:02d}/{total_parcelas:02d}  "
                        f"R$ {self._money(parcela['valor'], field='valor da parcela')}  "
                        f"{self._date_br(parcela['vencimento'])}"
                    )
                line(
                    f"Saldo financiado: R$ {self._money(payment_plan['valor_aberto'], field='saldo financiado')}",
                    True,
                )
        if footer:
            y -= step / 2
            for part in footer.splitlines():
                line(part, centered=True)
        y = self._draw_qr_if_enabled(
            canvas, width, y, margin, mm,
            f"NABICODE|{category}|{document_id or ''}|{name}|{self._money(total, field='total do documento')}|{datetime.now():%Y-%m-%d %H:%M:%S}",
        )
        if self.config_bool("impressao_mostrar_assinatura", True):
            y = max(margin + 18 * mm, y - 18 * mm)
            canvas.line(margin, y, width - margin, y)
            canvas.setFont(font, max(7, size - 1))
            canvas.drawCentredString(width / 2, y - 11, "Assinatura do cliente / responsável")
        return self._finalize_document(
            canvas, path, destination=destination, document_id=document_id, category=category
        )


    def _sale_payment_plan(self, movement_id: int) -> dict[str, Any] | None:
        connection = self._connection_factory()
        try:
            movement_columns = {str(row[1]).casefold() for row in connection.execute("PRAGMA table_info(movimentacoes)").fetchall()}
            if not movement_columns:
                return None
            value_open_decimal = "valor_aberto_decimal" in movement_columns
            select_open = (
                "valor_aberto_decimal, valor_aberto"
                if value_open_decimal and "valor_aberto" in movement_columns
                else "NULL, valor_aberto"
                if "valor_aberto" in movement_columns
                else "NULL, 0"
            )
            select_form = "COALESCE(forma_pagamento,'')" if "forma_pagamento" in movement_columns else "''"
            select_total = "COALESCE(total_parcelas,1)" if "total_parcelas" in movement_columns else "1"
            select_status = "COALESCE(status_pagamento,'')" if "status_pagamento" in movement_columns else "''"
            row = connection.execute(
                f"""SELECT {select_form}, {select_total}, {select_open}, {select_status}
                    FROM movimentacoes WHERE id=?""",
                (int(movement_id),),
            ).fetchone()
            if not row:
                return None
            forma, total_parcelas, aberto_canonico, aberto_legado, status = row
            parcel_columns = {str(item[1]).casefold() for item in connection.execute("PRAGMA table_info(parcelas)").fetchall()}
            parcel_rows = []
            if {"movimentacao_id", "valor_parcela"}.issubset(parcel_columns):
                value_decimal = "valor_parcela_decimal" in parcel_columns
                select_value = "valor_parcela_decimal, valor_parcela" if value_decimal else "NULL, valor_parcela"
                select_number = "numero_parcela" if "numero_parcela" in parcel_columns else "id"
                select_due = "COALESCE(vencimento,'')" if "vencimento" in parcel_columns else "''"
                select_parcel_status = "COALESCE(status,'PENDENTE')" if "status" in parcel_columns else "'PENDENTE'"
                parcel_rows = connection.execute(
                    f"""SELECT {select_number}, {select_value}, {select_due}, {select_parcel_status}
                        FROM parcelas WHERE movimentacao_id=?
                        ORDER BY {select_number},id""",
                    (int(movement_id),),
                ).fetchall()
            parcelas = [
                {
                    "numero": int(number or index),
                    "valor": DecimalStorage.read(canonical, legacy, field="valor da parcela"),
                    "vencimento": due,
                    "status": parcel_status,
                }
                for index, (number, canonical, legacy, due, parcel_status) in enumerate(parcel_rows, 1)
            ]
            if not parcelas and int(total_parcelas or 1) <= 1 and str(status or '').upper() not in {"PENDENTE", "PARCIAL"}:
                return None
            return {
                "forma": str(forma or ""),
                "total_parcelas": int(total_parcelas or len(parcelas) or 1),
                "valor_aberto": DecimalStorage.read(aberto_canonico, aberto_legado, field="saldo financiado"),
                "status": str(status or ""),
                "parcelas": parcelas,
            }
        finally:
            connection.close()

    def generate_movement(
        self,
        movement_id: int,
        destination: str | os.PathLike[str] | None = None,
    ) -> str:
        row = self._movement(movement_id)
        if not row:
            raise RuntimeError("Movimentação não encontrada.")
        kind, description, value, date, payment_method, responsible, customer_name = row
        model = self.document_model("recibo")
        path = self._document_path(
            destination, f"comprovante_{movement_id}_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        )
        canvas, (width, height), mm = self._create_canvas(path, model, 150)
        margin, font, size, _step = self._render_config(mm, minimum_size=8)
        y = self._draw_header(canvas, width, height - margin, mm, model, "COMPROVANTE DE MOVIMENTAÇÃO")
        canvas.setFont(font, size)
        lines = [
            f"Documento: {movement_id}", f"Data: {date}", f"Tipo: {kind.replace('_', ' ')}",
            f"Cliente: {customer_name}", f"Descrição: {description or '-'}",
            f"Forma: {payment_method or 'Não informada'}",
            f"Responsável: {responsible or 'Não informado'}", f"VALOR: R$ {self._money(value, field='valor do comprovante')}",
        ]
        self._draw_lines(canvas, lines, margin, y, font, size, model)
        return self._finalize_document(
            canvas, path, destination=destination, document_id=movement_id, category="movimento"
        )

    def generate_customer_payment(
        self,
        movement_id: int,
        allocations: Sequence[Mapping[str, Any]] | None = None,
        destination: str | os.PathLike[str] | None = None,
        *,
        balance_before: Any | None = None,
        balance_after: Any | None = None,
    ) -> str:
        """Gera recibo detalhado do pagamento e das vendas/parcelas abatidas."""
        payment = self._payment_details(movement_id)
        if not payment:
            raise RuntimeError("Pagamento não encontrado.")

        (
            _customer_id, customer_name, customer_code, customer_record,
            description, value, date, payment_method, responsible,
        ) = payment
        allocations = list(allocations or [])
        sale_ids = [int(item["venda_id"]) for item in allocations if item.get("venda_id")]
        sales = self._sales_with_installments(sale_ids)

        model = self.document_model("recibo")
        path = self._document_path(
            destination, f"recibo_pagamento_{movement_id}_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        )

        installment_count = sum(len(item.get("parcelas", [])) for item in sales.values())
        estimated_height = max(190, 105 + len(allocations) * 34 + installment_count * 12)
        canvas, (width, height), mm = self._create_canvas(path, model, estimated_height)
        margin, font, size, step = self._render_config(mm, minimum_size=7)
        y = self._draw_header(canvas, width, height - margin, mm, model, "RECIBO DE PAGAMENTO")
        renderer = self._line_renderer(canvas, margin=margin, y=y, font=font, size=size, model=model, step=step)

        def line(text: object = "", *, bold: bool = False, indent: int = 0) -> None:
            nonlocal y
            y = renderer.draw(text, bold=bold, indent=indent)

        reconciled_balance_before = (
            DecimalStorage.to_decimal(balance_before, field="saldo anterior")
            if balance_before is not None else None
        )
        reconciled_balance_after = (
            DecimalStorage.to_decimal(balance_after, field="saldo posterior")
            if balance_after is not None else None
        )

        line(f"Recibo: {movement_id}")
        line(f"Data do pagamento: {date}")
        line(f"Cliente: {customer_name}", bold=True)
        line(f"Código: {customer_code or '-'}   Ficha: {customer_record or '-'}")
        line(f"Forma de pagamento: {payment_method or 'Não informada'}")
        if responsible:
            line(f"Responsável: {responsible}")
        if description:
            line(f"Observação: {description}")
        y -= 3
        canvas.line(margin, y, width - margin, y)
        y -= step
        renderer.y = y
        line(f"VALOR RECEBIDO: R$ {self._money(value, field='valor recebido')}", bold=True)
        if reconciled_balance_before is not None:
            line(f"Saldo antes: R$ {reconciled_balance_before:.2f}")
        if reconciled_balance_after is not None:
            line(f"Saldo depois: R$ {reconciled_balance_after:.2f}", bold=True)

        if allocations:
            y -= 3
            canvas.line(margin, y, width - margin, y)
            y -= step
            renderer.y = y
            line("COMO O PAGAMENTO FOI DISTRIBUÍDO", bold=True)

            for position, allocation in enumerate(allocations, 1):
                sale_id = int(allocation["venda_id"])
                sale = sales.get(sale_id, {})
                line(f"{position}. Venda #{sale_id}", bold=True)
                line(f"Data da venda: {sale.get('data') or '-'}", indent=2)
                line(f"Descrição: {sale.get('descricao') or 'Venda'}", indent=2)
                line(f"Valor original: R$ {self._money(sale.get('valor'), field='valor original')}", indent=2)
                line(
                    f"Aplicado neste pagamento: R$ {self._money(allocation.get('valor_aplicado'), field='valor aplicado')}",
                    indent=2,
                )
                line(
                    f"Saldo da venda: R$ {self._money(allocation.get('saldo_antes'), field='saldo anterior')} "
                    f"→ R$ {self._money(allocation.get('saldo_depois'), field='saldo posterior')}",
                    indent=2,
                )
                parcelas = sale.get("parcelas", [])
                if parcelas:
                    line(f"Parcelas ({len(parcelas)}):", indent=2)
                    for parcela in parcelas:
                        numero, valor_parcela, vencimento, status, valor_pago, data_pagamento = parcela
                        texto = (
                            f"{numero}ª | venc. {vencimento or '-'} | "
                            f"R$ {self._money(valor_parcela, field='valor da parcela')} | "
                            f"pago R$ {self._money(valor_pago, field='valor pago')} | {status or 'PENDENTE'}"
                        )
                        if data_pagamento:
                            texto += f" em {data_pagamento}"
                        line(texto, indent=4)
                y -= step * 0.35
                renderer.y = y
        else:
            line("Pagamento aplicado ao saldo geral da ficha.")

        footer = (self._config_getter("rodape_cupom") or "").strip()
        if footer:
            y -= step / 2
            renderer.y = y
            for footer_line in footer.splitlines():
                line(footer_line)

        y = self._draw_qr_if_enabled(
            canvas,
            width,
            y,
            margin,
            mm,
            f"NABICODE|PAGAMENTO|{movement_id}|{customer_name}|{self._money(value, field='valor do pagamento')}|{date}",
        )
        if self.config_bool("impressao_mostrar_assinatura", True):
            y = max(margin + 18 * mm, y - 18 * mm)
            canvas.line(margin, y, width - margin, y)
            canvas.setFont(font, max(7, size - 1))
            canvas.drawCentredString(width / 2, y - 11, "Assinatura do cliente / responsável")

        return self._finalize_document(
            canvas, path, destination=destination, document_id=movement_id, category="recibo"
        )

    def generate_closing(
        self,
        summary: Mapping[str, Any],
        counted_value: float | None = None,
        responsible: str = "",
        observation: str = "",
        destination: str | os.PathLike[str] | None = None,
    ) -> str:
        model = self.document_model("fechamento")
        path = self._document_path(
            destination, f"fechamento_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        )
        canvas, (width, height), mm = self._create_canvas(path, model, 220)
        margin, font, size, _step = self._render_config(mm, minimum_size=8)
        y = self._draw_header(canvas, width, height - margin, mm, model, "FECHAMENTO / RESUMO DO DIA")
        lines = [
            f"Data: {summary['data']}", f"Abertura: R$ {summary['abertura']:.2f}",
            f"Vendas: R$ {summary['vendas']:.2f}", f"Recebimentos: R$ {summary['recebimentos']:.2f}",
            f"Suprimentos: R$ {summary['suprimentos']:.2f}", f"Retiradas: R$ {summary['retiradas']:.2f}",
            f"Pagamentos de conta: R$ {summary['contas']:.2f}", f"Entradas: R$ {summary['entradas']:.2f}",
            f"Saídas: R$ {summary['saidas']:.2f}", f"SALDO ESPERADO: R$ {summary['saldo_esperado']:.2f}",
        ]
        if summary.get("formas"):
            lines.append("--- Recebimentos por forma ---")
            lines.extend(f"{key}: R$ {value:.2f}" for key, value in sorted(summary["formas"].items()))
        if counted_value is not None:
            lines.extend([
                f"Valor contado: R$ {counted_value:.2f}",
                f"Diferença: R$ {counted_value - summary['saldo_esperado']:.2f}",
            ])
        if responsible:
            lines.append(f"Responsável: {responsible}")
        if observation:
            lines.append(f"Observação: {observation}")
        self._draw_lines(canvas, lines, margin, y, font, size, model)
        return self._finalize_document(canvas, path, destination=destination)

    def _customer(self, customer_id: int) -> tuple[Any, ...]:
        connection = self._connection_factory()
        try:
            row = connection.execute(
                "SELECT nome,codigo,numero_ficha,telefone,endereco,referencia,saldo_devedor "
                "FROM clientes WHERE id=?", (customer_id,),
            ).fetchone()
            return tuple(row) if row else ("Cliente", "", "", "", "", "", 0)
        finally:
            connection.close()

    def _movement(self, movement_id: int) -> tuple[Any, ...] | None:
        connection = self._connection_factory()
        try:
            row = connection.execute(
                "SELECT m.tipo,m.descricao,m.valor,m.data,COALESCE(m.forma_pagamento,''),"
                "COALESCE(m.responsavel,''),COALESCE(c.nome,'Sem cliente') "
                "FROM movimentacoes m LEFT JOIN clientes c ON c.id=m.cliente_id WHERE m.id=?",
                (movement_id,),
            ).fetchone()
            return tuple(row) if row else None
        finally:
            connection.close()

    def _payment_details(self, movement_id: int) -> tuple[Any, ...] | None:
        connection = self._connection_factory()
        try:
            row = connection.execute(
                """SELECT m.cliente_id, COALESCE(c.nome,'Sem cliente'),
                          COALESCE(c.codigo,''), COALESCE(c.numero_ficha,''),
                          COALESCE(m.descricao,''), COALESCE(m.valor,0),
                          COALESCE(m.data,''), COALESCE(m.forma_pagamento,''),
                          COALESCE(m.responsavel,'')
                   FROM movimentacoes m
                   LEFT JOIN clientes c ON c.id=m.cliente_id
                   WHERE m.id=? AND m.tipo='PAGAMENTO'""",
                (int(movement_id),),
            ).fetchone()
            return tuple(row) if row else None
        finally:
            connection.close()

    def _sales_with_installments(self, sale_ids: Sequence[int]) -> dict[int, dict[str, Any]]:
        if not sale_ids:
            return {}
        connection = self._connection_factory()
        try:
            result: dict[int, dict[str, Any]] = {}
            placeholders = ",".join("?" for _ in sale_ids)
            rows = connection.execute(
                f"""SELECT id, COALESCE(data,''), COALESCE(descricao,''),
                           COALESCE(valor,0), COALESCE(valor_aberto,0),
                           COALESCE(total_parcelas,1), COALESCE(status_pagamento,'')
                    FROM movimentacoes
                    WHERE id IN ({placeholders})""",
                tuple(int(value) for value in sale_ids),
            ).fetchall()
            for row in rows:
                result[int(row[0])] = {
                    "data": row[1],
                    "descricao": row[2],
                    "valor": DecimalStorage.to_decimal(row[3] or 0, field="valor da movimentação"),
                    "valor_aberto": DecimalStorage.to_decimal(row[4] or 0, field="valor aberto"),
                    "total_parcelas": int(row[5] or 1),
                    "status": row[6],
                    "parcelas": [],
                }
            parcel_rows = connection.execute(
                f"""SELECT movimentacao_id, numero_parcela, valor_parcela,
                           COALESCE(vencimento,''), COALESCE(status,'PENDENTE'),
                           COALESCE(valor_pago,0), COALESCE(data_pagamento,'')
                    FROM parcelas
                    WHERE movimentacao_id IN ({placeholders})
                    ORDER BY movimentacao_id, numero_parcela, id""",
                tuple(int(value) for value in sale_ids),
            ).fetchall()
            for movement_id, number, amount, due, status, paid, paid_at in parcel_rows:
                if int(movement_id) in result:
                    result[int(movement_id)]["parcelas"].append(
                        (number, amount, due, status, paid, paid_at)
                    )
            return result
        finally:
            connection.close()

    def _document_path(
        self, destination: str | os.PathLike[str] | None, filename: str
    ) -> Path:
        """Resolve o destino de qualquer PDF por uma única regra."""
        return Path(destination) if destination else self._monthly_folder() / filename

    def _finalize_document(
        self,
        canvas: Any,
        path: Path,
        *,
        destination: str | os.PathLike[str] | None,
        document_id: int | None = None,
        category: str | None = None,
    ) -> str:
        """Salva e registra um PDF exatamente uma vez."""
        canvas.save()
        absolute = str(path.resolve())
        if (
            destination is None
            and document_id is not None
            and category
            and self._document_registrar
        ):
            self._document_registrar(document_id, category, absolute, str(document_id))
        return absolute

    def _monthly_folder(self) -> Path:
        folder = self._pdf_dir / datetime.now().strftime("%Y") / datetime.now().strftime("%m")
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    @staticmethod
    def _create_canvas(path: Path, model: str, estimated_height_mm: float = 180):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise RuntimeError("Instale a biblioteca reportlab: pip install reportlab") from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        if model == "A4":
            page_size = A4
        elif model == "Térmica 58 mm econômica":
            page_size = (58 * mm, max(90, estimated_height_mm) * mm)
        else:
            page_size = (80 * mm, max(100, estimated_height_mm) * mm)
        return canvas.Canvas(str(path), pagesize=page_size), page_size, mm

    def _draw_header(self, canvas: Any, width: float, y: float, mm: float, model: str, title: str) -> float:
        data = self.store_data()
        margin, font, _size, _step = self._render_config(mm)
        title_size = max(9, float(self._config_getter("impressao_titulo_tamanho") or 15))
        center = width / 2
        logo = self._config_getter("impressao_logo_path")
        if self.config_bool("impressao_mostrar_logo", False) and logo and os.path.exists(logo):
            try:
                canvas.drawImage(logo, margin, y - 18 * mm, width=22 * mm, height=16 * mm, preserveAspectRatio=True, mask="auto")
            except Exception as exc:  # reportlab may reject malformed images
                self.last_warning = f"Logo de impressão ignorado: {exc}"
                self._logger.warning(self.last_warning, exc_info=True)
        bold_font = bold_font_name(font)
        canvas.setFont(bold_font, title_size)
        canvas.drawCentredString(center, y, data["nome"])
        y -= title_size + 4
        canvas.setFont(font, max(7, title_size - 5))
        extras: list[str] = []
        if self.config_bool("impressao_mostrar_endereco") and data["endereco"]:
            extras.append(data["endereco"])
        if self.config_bool("impressao_mostrar_telefone") and data["telefone"]:
            extras.append(f"Tel.: {data['telefone']}")
        if self.config_bool("impressao_mostrar_cnpj") and data["cnpj"]:
            extras.append(f"CNPJ: {data['cnpj']}")
        if self.config_bool("impressao_mostrar_email", False) and data["email"]:
            extras.append(data["email"])
        max_chars = self._model_width_chars(model)
        for extra in extras:
            for line in wrap_lines(extra, max_chars):
                canvas.drawCentredString(center, y, line)
                y -= max(9, title_size - 2)
        y -= 2
        canvas.line(margin, y, width - margin, y)
        y -= 13
        canvas.setFont(bold_font, max(9, title_size - 2))
        canvas.drawCentredString(center, y, title)
        return y - 16

    def _draw_qr_if_enabled(self, canvas: Any, width: float, y: float, margin: float, mm: float, content: str) -> float:
        if not self.config_bool("impressao_qrcode", True):
            return y
        try:
            from reportlab.graphics import renderPDF
            from reportlab.graphics.barcode import qr
            from reportlab.graphics.shapes import Drawing
            widget = qr.QrCodeWidget(content)
            bounds = widget.getBounds()
            size = 24 * mm
            drawing = Drawing(size, size, transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0])
            drawing.add(widget)
            # Nunca empurra o QR para cima com max(margin, ...), pois isso o
            # sobrepunha ao rodapé. A página térmica já é dimensionada com a
            # reserva necessária; o QR segue sempre abaixo do último texto.
            qr_bottom = y - (6 * mm) - size
            renderPDF.draw(drawing, canvas, (width - size) / 2, qr_bottom)
            return qr_bottom - (6 * mm)
        except Exception as exc:
            self.last_warning = f"QR Code do comprovante não foi gerado: {exc}"
            self._logger.warning(self.last_warning, exc_info=True)
            return y

    def _draw_lines(self, canvas: Any, lines: Sequence[str], margin: float, y: float, font: str, size: float, model: str) -> float:
        renderer = self._line_renderer(canvas, margin=margin, y=y, font=font, size=size, model=model)
        for text in lines:
            renderer.draw(text)
        return renderer.y
