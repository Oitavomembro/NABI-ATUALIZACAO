from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable
from decimal import Decimal

from database import DatabaseManager
from repositories.decimal_storage import DecimalStorage


@dataclass(frozen=True)
class ResumoCobranca:
    quantidade: int
    total: Decimal


class CobrancaService:
    """Consultas e regras de cobranças sem dependência da interface gráfica."""

    FILTROS = ("Todas", "Sem contato", "Prometeu pagar", "Retorno vencido")

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    @staticmethod
    def _data_br_para_iso(valor: str | None) -> str:
        texto = str(valor or "").strip()
        if not texto:
            return ""
        for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(texto, formato).date().isoformat()
            except ValueError:
                continue
        return ""

    def listar_atrasadas(self, filtro: str = "Todas") -> list[dict]:
        rows = self.database.fetch_all(
            """
            SELECT p.id AS parcela_id,c.id AS cliente_id,c.nome,c.telefone,p.numero_parcela,
                   MAX(0,COALESCE(p.valor_parcela,0)-COALESCE(p.valor_pago,0)) AS valor_aberto,
                   p.vencimento,
                   (SELECT cc.data FROM contatos_cobranca cc WHERE cc.parcela_id=p.id ORDER BY cc.id DESC LIMIT 1) AS ultimo_contato,
                   (SELECT cc.resultado FROM contatos_cobranca cc WHERE cc.parcela_id=p.id ORDER BY cc.id DESC LIMIT 1) AS situacao,
                   (SELECT cc.proximo_contato FROM contatos_cobranca cc
                    WHERE cc.parcela_id=p.id AND COALESCE(cc.proximo_contato,'')<>'' ORDER BY cc.id DESC LIMIT 1) AS proximo_contato
            FROM parcelas p
            JOIN movimentacoes m ON m.id=p.movimentacao_id
            JOIN clientes c ON c.id=m.cliente_id
            WHERE p.status<>'PAGO' AND COALESCE(p.dados_confiaveis,1)=1
              AND p.vencimento<>'' AND date(p.vencimento)<date('now','localtime')
            ORDER BY date(p.vencimento),c.nome
            """
        )
        hoje = date.today().isoformat()
        resultado: list[dict] = []
        for row in rows:
            item = dict(row)
            situacao = str(item.get("situacao") or "")
            proximo = str(item.get("proximo_contato") or "")
            if filtro == "Sem contato" and item.get("ultimo_contato"):
                continue
            if filtro == "Prometeu pagar" and situacao.casefold() != "prometeu pagar":
                continue
            if filtro == "Retorno vencido" and (not proximo or proximo > hoje):
                continue
            resultado.append(item)
        return resultado

    def resumo(self, rows: Iterable[dict]) -> ResumoCobranca:
        itens = list(rows)
        total = sum((DecimalStorage.to_decimal(i.get("valor_aberto") or 0, field="valor em aberto") for i in itens), Decimal("0"))
        return ResumoCobranca(len(itens), total)

    def listar_lembretes_para_hoje(self) -> list[dict]:
        rows = self.database.fetch_all(
            """
            SELECT l.id AS lembrete_id,p.id AS parcela_id,c.id AS cliente_id,c.nome,c.telefone,
                   p.numero_parcela,MAX(0,COALESCE(p.valor_parcela,0)-COALESCE(p.valor_pago,0)) AS valor_aberto,
                   p.vencimento,l.dias_antecedencia,l.observacao,l.ultimo_aviso_em
            FROM lembretes_promissorias l
            JOIN parcelas p ON p.id=l.parcela_id
            JOIN movimentacoes m ON m.id=p.movimentacao_id
            JOIN clientes c ON c.id=l.cliente_id
            WHERE l.ativo=1 AND p.status<>'PAGO'
              AND date('now','localtime') >= date(p.vencimento, '-' || l.dias_antecedencia || ' day')
              AND date('now','localtime') <= date(p.vencimento)
            ORDER BY date(p.vencimento),c.nome
            """
        )
        hoje = date.today().isoformat()
        # Não repetir o mesmo lembrete no mesmo dia.
        return [dict(r) for r in rows if self._data_br_para_iso(r["ultimo_aviso_em"]) != hoje]

    def listar_retornos_pendentes(self) -> list[dict]:
        rows = self.database.fetch_all(
            """
            SELECT cc.id AS contato_id,cc.cliente_id,cc.parcela_id,c.nome,c.telefone,
                   p.numero_parcela,MAX(0,COALESCE(p.valor_parcela,0)-COALESCE(p.valor_pago,0)) AS valor_aberto,
                   p.vencimento,cc.resultado,cc.observacao,cc.proximo_contato,cc.data
            FROM contatos_cobranca cc
            JOIN clientes c ON c.id=cc.cliente_id
            JOIN parcelas p ON p.id=cc.parcela_id
            WHERE COALESCE(cc.proximo_contato,'')<>'' AND date(cc.proximo_contato)<=date('now','localtime')
              AND p.status<>'PAGO'
              AND cc.id=(SELECT MAX(x.id) FROM contatos_cobranca x
                         WHERE x.parcela_id=cc.parcela_id AND COALESCE(x.proximo_contato,'')<>'')
            ORDER BY date(cc.proximo_contato),c.nome
            """
        )
        return [dict(r) for r in rows]

    def registrar_contato(
        self,
        *,
        cliente_id: int,
        parcela_id: int,
        tipo: str,
        resultado: str,
        observacao: str = "",
        proximo_contato: str = "",
    ) -> int:
        if proximo_contato:
            datetime.strptime(proximo_contato, "%Y-%m-%d")
        return self.database.execute(
            """INSERT INTO contatos_cobranca
               (cliente_id,parcela_id,tipo,resultado,observacao,proximo_contato,data)
               VALUES (?,?,?,?,?,?,?)""",
            (cliente_id, parcela_id, tipo, resultado, observacao, proximo_contato,
             datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
        )

    def dados_parcela(self, parcela_id: int) -> dict | None:
        if int(parcela_id) <= 0:
            raise ValueError("Parcela inválida.")
        row = self.database.fetch_one(
            """SELECT m.cliente_id,c.nome,c.telefone,p.numero_parcela,
                      MAX(0,COALESCE(p.valor_parcela,0)-COALESCE(p.valor_pago,0)) AS valor_aberto,
                      p.vencimento
               FROM parcelas p
               JOIN movimentacoes m ON m.id=p.movimentacao_id
               JOIN clientes c ON c.id=m.cliente_id
               WHERE p.id=?""",
            (int(parcela_id),),
        )
        return dict(row) if row else None

    def parcelas_pendentes_cliente(self, cliente_id: int) -> list[dict]:
        if int(cliente_id) <= 0:
            raise ValueError("Cliente inválido.")
        rows = self.database.fetch_all(
            """SELECT p.id AS parcela_id,p.numero_parcela,p.valor_parcela,p.vencimento
               FROM parcelas p JOIN movimentacoes m ON m.id=p.movimentacao_id
               WHERE m.cliente_id=? AND p.status<>'PAGO' AND p.vencimento<>''
               ORDER BY date(p.vencimento),p.numero_parcela""",
            (int(cliente_id),),
        )
        return [dict(row) for row in rows]

    def salvar_lembrete(self, *, cliente_id: int, parcela_id: int, dias_antecedencia: int, observacao: str = "") -> None:
        if int(cliente_id) <= 0 or int(parcela_id) <= 0:
            raise ValueError("Cliente ou parcela inválidos.")
        dias = int(dias_antecedencia)
        if dias < 0 or dias > 365:
            raise ValueError("Dias de antecedência inválidos.")
        self.database.execute(
            """INSERT INTO lembretes_promissorias
               (cliente_id,parcela_id,dias_antecedencia,observacao,ativo,criado_em)
               VALUES (?,?,?,?,1,?)
               ON CONFLICT(parcela_id) DO UPDATE SET
                 cliente_id=excluded.cliente_id,
                 dias_antecedencia=excluded.dias_antecedencia,
                 observacao=excluded.observacao,
                 ativo=1""",
            (int(cliente_id), int(parcela_id), dias, str(observacao or "").strip(),
             datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
        )

    def dados_lembrete(self, lembrete_id: int) -> dict | None:
        if int(lembrete_id) <= 0:
            raise ValueError("Lembrete inválido.")
        row = self.database.fetch_one(
            """SELECT l.id AS lembrete_id,l.cliente_id,l.parcela_id,c.nome,c.telefone,
                      p.numero_parcela,MAX(0,COALESCE(p.valor_parcela,0)-COALESCE(p.valor_pago,0)) AS valor_aberto,
                      p.vencimento,l.observacao
               FROM lembretes_promissorias l
               JOIN clientes c ON c.id=l.cliente_id
               JOIN parcelas p ON p.id=l.parcela_id
               WHERE l.id=?""",
            (int(lembrete_id),),
        )
        return dict(row) if row else None

    def marcar_lembrete_enviado(self, *, lembrete_id: int, cliente_id: int, parcela_id: int, observacao: str = "") -> None:
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with self.database.session(write=True) as conn:
            conn.execute("UPDATE lembretes_promissorias SET ultimo_aviso_em=? WHERE id=?", (agora, int(lembrete_id)))
            conn.execute(
                """INSERT INTO contatos_cobranca(cliente_id,parcela_id,tipo,resultado,observacao,data)
                   VALUES (?,?,?,?,?,?)""",
                (int(cliente_id), int(parcela_id), "LEMBRETE", "WhatsApp aberto", str(observacao or "").strip(), agora),
            )

    def dados_retorno(self, contato_id: int) -> dict | None:
        if int(contato_id) <= 0:
            raise ValueError("Contato inválido.")
        row = self.database.fetch_one(
            """SELECT cc.id AS contato_id,cc.cliente_id,cc.parcela_id,c.nome,c.telefone,p.numero_parcela,
                      MAX(0,COALESCE(p.valor_parcela,0)-COALESCE(p.valor_pago,0)) AS valor_aberto,p.vencimento
               FROM contatos_cobranca cc
               JOIN clientes c ON c.id=cc.cliente_id
               JOIN parcelas p ON p.id=cc.parcela_id
               WHERE cc.id=?""",
            (int(contato_id),),
        )
        return dict(row) if row else None

    @staticmethod
    def mensagem_cobranca(*, nome: str, loja: str, parcela: int, valor: Decimal | int | float | str, vencimento: str) -> str:
        return (
            f"Olá {nome}, tudo bem?\n\nAqui é da {loja}. Identificamos a parcela {parcela or 1} "
            f"no valor de R$ {DecimalStorage.to_decimal(valor, field='valor da cobrança'):.2f}, vencida em {vencimento}. "
            "Poderia nos informar uma previsão para o pagamento?"
        )

    @staticmethod
    def mensagem_lembrete(*, nome: str, loja: str, parcela: int, valor: Decimal | int | float | str, vencimento: str, observacao: str = "") -> str:
        complemento = f"\n\n{observacao.strip()}" if observacao and observacao.strip() else ""
        return (
            f"Olá {nome}, tudo bem?\n\nConforme combinado, aqui é da {loja} lembrando que a parcela {parcela or 1} "
            f"no valor de R$ {DecimalStorage.to_decimal(valor, field='valor do lembrete'):.2f} vence em {vencimento}.{complemento}"
        )
