from __future__ import annotations

from typing import Any, Iterable

from services.financeiro_calculator import FinanceiroCalculator


class FinanceiroFormatter:
    """Formatação financeira pura, sem dependência de Tk ou acesso a dados."""

    @staticmethod
    def moeda(valor: Any) -> str:
        return f"R$ {FinanceiroCalculator.dinheiro(valor):.2f}"

    @classmethod
    def resumo_fluxo(cls, fluxo: dict[str, Any]) -> str:
        return f"Fluxo: entradas {cls.moeda(fluxo['entradas'])} | saídas {cls.moeda(fluxo['saidas'])} | saldo {cls.moeda(fluxo['saldo'])}"

    @classmethod
    def resumo_dre(cls, dre: dict[str, Any]) -> str:
        return f"DRE: competência {cls.moeda(dre['resultado_competencia'])} | realizado {cls.moeda(dre['resultado_realizado'])}"

    @classmethod
    def linha_titulo(cls, titulo: dict[str, Any], centro_custo: str) -> tuple[Any, ...]:
        return (titulo["id"], titulo["tipo"], titulo.get("pessoa_nome", ""), titulo.get("descricao", ""), titulo["data_vencimento"], cls.moeda(titulo["valor_original"]), cls.moeda(titulo["valor_pago"]), cls.moeda(titulo["saldo_aberto"]), titulo["status"], centro_custo)

    @classmethod
    def resumo_baixa(cls, calculo: dict[str, Any]) -> str:
        return f"Saldo: {cls.moeda(calculo['saldo'])}\nJuros: {cls.moeda(calculo['juros'])}\nMulta: {cls.moeda(calculo['multa'])}\nTotal: {cls.moeda(calculo['total'])}\n\nAplicar encargos ao título e realizar a baixa total?"

    @classmethod
    def pagamentos_para_selecao(cls, pagamentos: Iterable[dict[str, Any]]) -> str:
        return "\n".join(f"{p['id']} - {p['data_pagamento']} - {cls.moeda(p['valor'])}" for p in pagamentos)

    @classmethod
    def recorrencias_para_selecao(cls, recorrencias: Iterable[dict[str, Any]]) -> str:
        linhas = [f"{i['identificador']} | {i['tipo']} | {cls.moeda(i['valor'])} | dia {i['dia_vencimento']} | {'ATIVA' if i.get('ativo', True) else 'INATIVA'}" for i in recorrencias]
        return "\n".join(linhas) or "Nenhuma recorrência cadastrada."

    @classmethod
    def conciliacoes_para_selecao(cls, registros: Iterable[dict[str, Any]]) -> str:
        linhas = []
        for item in registros:
            conciliacao = item.get("conciliacao") or {}
            situacao = f"CONCILIADO: {conciliacao.get('referencia', '')}" if item.get("conciliado") else "NÃO CONCILIADO"
            linhas.append(f"{item['id']} | {item['data_pagamento']} | {cls.moeda(item['valor'])} | {situacao}")
        return "\n".join(linhas[:100]) or "Nenhum pagamento."

    @classmethod
    def relatorio_centros_custo(cls, dados: Iterable[dict[str, Any]]) -> str:
        return "\n".join(f"{i['centro_custo']}: pagar {cls.moeda(i['pagar'])} | receber {cls.moeda(i['receber'])} | saldo {cls.moeda(i['saldo'])}" for i in dados) or "Nenhum movimento no período."

    @classmethod
    def detalhes_financeiros(cls, fluxo: dict[str, Any], dre: dict[str, Any]) -> str:
        movimentos = "\n".join(f"{m['data_pagamento']} | {m['natureza']} | {cls.moeda(m['valor'])} | {m.get('descricao', '')}" for m in fluxo["movimentos"]) or "Sem movimentos realizados."
        competencias = "\n".join(f"{t['data_emissao']} | {t['tipo']} | {cls.moeda(t['valor_original'])} | {t.get('descricao', '')}" for t in dre["titulos_competencia"]) or "Sem títulos por competência."
        return f"MOVIMENTOS REALIZADOS\n{movimentos}\n\nTÍTULOS POR COMPETÊNCIA\n{competencias}"
