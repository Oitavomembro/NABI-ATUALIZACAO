from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable


class FinanceiroCalculator:
    """Cálculos financeiros puros, sem SQL, UI ou controle transacional."""

    DINHEIRO = Decimal("0.01")
    ZERO = Decimal("0.00")
    CEM = Decimal("100")
    DIAS_MES = Decimal("30")
    TIPOS_ENTRADA_LEGADOS = frozenset({"COMPRA", "VENDA", "PAGAMENTO", "RECEBIMENTO", "ENTRADA"})
    TIPOS_SAIDA_LEGADOS = frozenset({"SAIDA", "DESPESA", "PAGAMENTO_FORNECEDOR"})
    STATUS_REALIZADO = frozenset({"PAGO", "QUITADO", "RECEBIDO"})
    ORIGENS_FINANCEIRO = frozenset({"FINANCEIRO", "TITULO_FINANCEIRO"})

    @classmethod
    def dinheiro(cls, valor: Any, *, campo: str = "valor financeiro") -> Decimal:
        try:
            return Decimal(str(valor)).quantize(cls.DINHEIRO, rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(f"{campo.capitalize()} inválido.") from exc

    @classmethod
    def saldo(cls, valor_original: Any, valor_pago: Any) -> Decimal:
        return (cls.dinheiro(valor_original) - cls.dinheiro(valor_pago)).quantize(cls.DINHEIRO)

    @classmethod
    def encargos(
        cls,
        *,
        saldo: Any,
        vencimento: date,
        referencia: date,
        multa_percentual: Any = 0,
        juros_mensal_percentual: Any = 0,
    ) -> dict[str, Decimal | int]:
        saldo_decimal = cls.dinheiro(saldo, campo="saldo")
        dias_atraso = max(0, (referencia - vencimento).days)
        if dias_atraso == 0:
            multa = juros = cls.ZERO
        else:
            multa = (
                saldo_decimal * cls.dinheiro(multa_percentual, campo="multa") / cls.CEM
            ).quantize(cls.DINHEIRO, rounding=ROUND_HALF_UP)
            juros = (
                saldo_decimal
                * cls.dinheiro(juros_mensal_percentual, campo="juros")
                / cls.CEM
                * Decimal(dias_atraso)
                / cls.DIAS_MES
            ).quantize(cls.DINHEIRO, rounding=ROUND_HALF_UP)
        total = (saldo_decimal + multa + juros).quantize(cls.DINHEIRO, rounding=ROUND_HALF_UP)
        return {
            "dias_atraso": dias_atraso,
            "saldo": saldo_decimal,
            "multa": multa,
            "juros": juros,
            "total": total,
        }

    @classmethod
    def somar(cls, valores: Iterable[Any]) -> Decimal:
        return sum((cls.dinheiro(valor) for valor in valores), cls.ZERO).quantize(cls.DINHEIRO)

    @classmethod
    def saldo_parcelas(cls, parcelas: Iterable[dict[str, Any]]) -> Decimal:
        return cls.somar(
            max(cls.ZERO, cls.saldo(parcela.get("valor_parcela", 0), parcela.get("valor_pago", 0)))
            for parcela in parcelas
        )

    @staticmethod
    def data_iso(valor: str | date | datetime | None, *, padrao_hoje: bool = False) -> str:
        if valor is None or valor == "":
            if padrao_hoje:
                return date.today().isoformat()
            raise ValueError("Data obrigatória não informada.")
        if isinstance(valor, datetime):
            return valor.date().isoformat()
        if isinstance(valor, date):
            return valor.isoformat()
        texto = str(valor).strip()
        for formato in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(texto, formato).date().isoformat()
            except ValueError:
                continue
        raise ValueError("Data inválida. Use AAAA-MM-DD ou DD/MM/AAAA.")

    @classmethod
    def limitar_pagamento(cls, valor: Any, *limites: Any) -> Decimal:
        pagamento = cls.dinheiro(valor, campo="pagamento")
        if pagamento <= cls.ZERO:
            raise ValueError("O pagamento deve ser maior que zero.")
        limite = min(cls.dinheiro(item, campo="limite do pagamento") for item in limites)
        if pagamento > limite:
            raise ValueError(f"O pagamento não pode ser maior que R$ {limite:.2f} para a seleção atual.")
        return pagamento


    @classmethod
    def natureza_movimento_legado(cls, movimento: dict[str, Any]) -> str | None:
        """Classifica movimento legado sem duplicar regras entre Fluxo e DRE."""
        if str(movimento.get("origem_sistema") or "").strip().upper() in cls.ORIGENS_FINANCEIRO:
            return None
        tipo = str(movimento.get("tipo") or "").strip().upper()
        if tipo in cls.TIPOS_ENTRADA_LEGADOS:
            return "ENTRADA"
        if tipo in cls.TIPOS_SAIDA_LEGADOS:
            return "SAIDA"
        return None

    @classmethod
    def fluxo_caixa(
        cls, pagamentos: Iterable[dict[str, Any]], movimentos_legados: Iterable[dict[str, Any]]
    ) -> dict[str, Any]:
        entradas = cls.ZERO
        saidas = cls.ZERO
        movimentos: list[dict[str, Any]] = []

        for pagamento in pagamentos:
            valor = cls.dinheiro(pagamento.get("valor", 0))
            natureza = "ENTRADA" if str(pagamento.get("tipo") or "").upper() == "RECEBER" else "SAIDA"
            if natureza == "ENTRADA":
                entradas += valor
            else:
                saidas += valor
            movimentos.append({**pagamento, "fonte": "TITULO", "natureza": natureza, "valor": valor})

        for movimento in movimentos_legados:
            natureza = cls.natureza_movimento_legado(movimento)
            status = str(movimento.get("status_pagamento") or "").strip().upper()
            if natureza is None or status not in cls.STATUS_REALIZADO:
                continue
            valor = cls.dinheiro(movimento.get("valor", 0))
            if valor <= cls.ZERO:
                continue
            if natureza == "ENTRADA":
                entradas += valor
            else:
                saidas += valor
            movimentos.append({**movimento, "fonte": "MOVIMENTACAO", "natureza": natureza, "valor": valor})

        entradas = entradas.quantize(cls.DINHEIRO)
        saidas = saidas.quantize(cls.DINHEIRO)
        return {
            "entradas": entradas,
            "saidas": saidas,
            "saldo": (entradas - saidas).quantize(cls.DINHEIRO),
            "movimentos": movimentos,
        }

    @classmethod
    def dre(
        cls, titulos: Iterable[dict[str, Any]], pagamentos: Iterable[dict[str, Any]],
        movimentos_legados: Iterable[dict[str, Any]],
    ) -> dict[str, Decimal]:
        titulos = list(titulos)
        pagamentos = list(pagamentos)
        movimentos_legados = list(movimentos_legados)
        receitas = cls.somar(t["valor_original"] for t in titulos if str(t.get("tipo") or "").upper() == "RECEBER")
        despesas = cls.somar(t["valor_original"] for t in titulos if str(t.get("tipo") or "").upper() == "PAGAR")
        recebido = cls.somar(p["valor"] for p in pagamentos if str(p.get("tipo") or "").upper() == "RECEBER")
        pago = cls.somar(p["valor"] for p in pagamentos if str(p.get("tipo") or "").upper() == "PAGAR")

        for movimento in movimentos_legados:
            natureza = cls.natureza_movimento_legado(movimento)
            if natureza is None:
                continue
            valor = cls.dinheiro(movimento.get("valor", 0))
            if valor <= cls.ZERO:
                continue
            realizado = str(movimento.get("status_pagamento") or "").strip().upper() in cls.STATUS_REALIZADO
            if natureza == "ENTRADA":
                receitas += valor
                if realizado:
                    recebido += valor
            else:
                despesas += valor
                if realizado:
                    pago += valor

        receitas = receitas.quantize(cls.DINHEIRO)
        despesas = despesas.quantize(cls.DINHEIRO)
        recebido = recebido.quantize(cls.DINHEIRO)
        pago = pago.quantize(cls.DINHEIRO)
        return {
            "receitas_competencia": receitas,
            "despesas_competencia": despesas,
            "resultado_competencia": (receitas - despesas).quantize(cls.DINHEIRO),
            "receitas_realizadas": recebido,
            "despesas_realizadas": pago,
            "resultado_realizado": (recebido - pago).quantize(cls.DINHEIRO),
        }

    @classmethod
    def encargos_observacao(cls, observacao: Any) -> Decimal:
        import re

        texto = str(observacao or "")
        if not texto.startswith("Encargos aplicados:"):
            return cls.ZERO
        encontrados = re.search(r"juros=([0-9.,-]+);\s*multa=([0-9.,-]+)", texto)
        if not encontrados:
            return cls.ZERO
        return cls.somar(
            valor.replace(",", ".") for valor in encontrados.groups()
        )


    @classmethod
    def reconciliar_cliente(cls, saldo_cliente: Any, compras: Iterable[dict[str, Any]]) -> dict[str, Any]:
        saldo_cliente_n = cls.dinheiro(saldo_cliente, campo="saldo do cliente")
        saldo_real = cls.ZERO
        divergencias: list[dict[str, Any]] = []
        bloqueios: list[dict[str, Any]] = []
        ajustes_parcelas: list[dict[str, Any]] = []
        compras_reconciliadas: list[dict[str, Any]] = []

        for compra in compras:
            mov_id = int(compra["id"])
            saldo_mov = max(cls.ZERO, cls.dinheiro(compra.get("valor_aberto", 0), campo="saldo da compra"))
            saldo_real = (saldo_real + saldo_mov).quantize(cls.DINHEIRO)
            parcelas = list(compra.get("parcelas") or [])
            saldo_parcelas = cls.saldo_parcelas(parcelas) if parcelas else saldo_mov

            if parcelas and saldo_parcelas > saldo_mov:
                diferenca = (saldo_parcelas - saldo_mov).quantize(cls.DINHEIRO)
                restante = diferenca
                for parcela in parcelas:
                    if restante <= cls.ZERO:
                        break
                    valor_parcela = cls.dinheiro(parcela.get("valor_parcela", 0), campo="valor da parcela")
                    valor_pago = cls.dinheiro(parcela.get("valor_pago", 0), campo="valor pago")
                    falta = max(cls.ZERO, valor_parcela - valor_pago)
                    aplicado = min(restante, falta).quantize(cls.DINHEIRO)
                    if aplicado <= cls.ZERO:
                        continue
                    novo_pago = (valor_pago + aplicado).quantize(cls.DINHEIRO)
                    ajustes_parcelas.append({
                        "parcela_id": int(parcela["id"]), "valor_pago": novo_pago,
                        "status": "PAGO" if novo_pago >= valor_parcela else "PARCIAL",
                        "valor_reconciliado": aplicado, "movimentacao_id": mov_id,
                    })
                    restante = (restante - aplicado).quantize(cls.DINHEIRO)
                divergencias.append({
                    "tipo": "PARCELAS_COM_PAGAMENTO_HISTORICO_FALTANTE",
                    "movimentacao_id": mov_id, "saldo_compra": saldo_mov,
                    "saldo_parcelas": saldo_parcelas, "diferenca": diferenca,
                })
                if restante > cls.ZERO:
                    bloqueios.append(divergencias[-1])
            elif parcelas and saldo_parcelas < saldo_mov:
                # Bases históricas migradas podem ter compras com saldo aberto maior que
                # a soma das parcelas preservadas. A compra continua sendo a fonte
                # detalhada disponível e a diferença é tratada como saldo histórico
                # sem detalhamento de parcela, sem bloquear um recebimento legítimo.
                divergencia = {
                    "tipo": "PARCELAS_HISTORICAS_INCOMPLETAS",
                    "movimentacao_id": mov_id, "saldo_compra": saldo_mov,
                    "saldo_parcelas": saldo_parcelas,
                    "diferenca": (saldo_mov - saldo_parcelas).quantize(cls.DINHEIRO),
                }
                divergencias.append(divergencia)

            compras_reconciliadas.append({
                **compra, "saldo_reconciliado": saldo_mov, "saldo_parcelas": saldo_parcelas,
            })

        saldo_compras = saldo_real
        # Registros migrados podem ter saldo consolidado do cliente sem todas as
        # compras antigas detalhadas. Nunca zerar essa dívida apenas porque o detalhe
        # histórico não veio na migração. O saldo oficial é o maior valor comprovado.
        saldo_residual_legado = max(cls.ZERO, saldo_cliente_n - saldo_compras).quantize(cls.DINHEIRO)
        saldo_real = max(saldo_cliente_n, saldo_compras).quantize(cls.DINHEIRO)
        if saldo_cliente_n != saldo_compras:
            tipo = "SALDO_LEGADO_SEM_COMPRA" if saldo_cliente_n > saldo_compras else "CLIENTE_X_COMPRAS"
            divergencias.append({
                "tipo": tipo, "saldo_cliente": saldo_cliente_n,
                "saldo_compras": saldo_compras,
                "diferenca": abs(saldo_compras - saldo_cliente_n).quantize(cls.DINHEIRO),
            })

        return {
            "saldo_informado": saldo_cliente_n, "saldo_real": saldo_real,
            "saldo_compras": saldo_compras, "saldo_residual_legado": saldo_residual_legado,
            "compras": compras_reconciliadas, "divergencias": divergencias,
            "bloqueios": bloqueios, "ajustes_parcelas": ajustes_parcelas,
        }

    @classmethod
    def aplicar_pagamento(cls, saldo: Any, valor: Any) -> tuple[Decimal, Decimal]:
        saldo_n = cls.dinheiro(saldo, campo="saldo")
        valor_n = cls.limitar_pagamento(valor, saldo_n)
        return valor_n, (saldo_n - valor_n).quantize(cls.DINHEIRO)
