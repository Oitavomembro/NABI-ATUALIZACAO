from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import json
from typing import Any

from repositories.financeiro_repository import FinanceiroRepository
from repositories.decimal_storage import DecimalStorage
from repositories.assistant_operation_journal_repository import (
    AssistantOperationJournalRepository,
)
from services.financeiro_calculator import FinanceiroCalculator


@dataclass(frozen=True)
class ResultadoPagamento:
    titulo_id: int
    pagamento_id: int
    valor_pago: Decimal
    saldo_aberto: Decimal
    status: str


class FinanceiroService:
    """Regras transacionais do financeiro essencial."""

    DINHEIRO = FinanceiroCalculator.DINHEIRO
    ZERO = FinanceiroCalculator.ZERO
    FORMAS_PAGAMENTO = {"DINHEIRO", "PIX", "CARTAO", "BOLETO", "TRANSFERENCIA", "CREDIARIO", "OUTRO"}

    def __init__(self, repository: FinanceiroRepository) -> None:
        self.repository = repository
        self.database = repository.database
        self.operation_journal = AssistantOperationJournalRepository()

    _dinheiro = staticmethod(FinanceiroCalculator.dinheiro)
    _data_iso = staticmethod(FinanceiroCalculator.data_iso)

    @classmethod
    def _forma_pagamento(cls, valor: Any) -> str:
        forma = str(valor or "").strip().upper()
        if not forma:
            return "NAO_INFORMADO"
        if forma not in cls.FORMAS_PAGAMENTO:
            permitidas = ", ".join(sorted(cls.FORMAS_PAGAMENTO))
            raise ValueError(f"Forma de pagamento inválida. Use: {permitidas}.")
        return forma

    def criar_titulo(
        self,
        *,
        tipo: str,
        valor: Any,
        data_vencimento: str | date | datetime,
        pessoa_id: int | None = None,
        pessoa_nome: str = "",
        documento: str = "",
        descricao: str = "",
        observacao: str = "",
        origem: str = "MANUAL",
        origem_id: str = "",
        data_emissao: str | date | datetime | None = None,
        usuario: str = "Sistema",
        connection=None,
    ) -> int:
        tipo_normalizado = str(tipo or "").strip().upper()
        if tipo_normalizado not in {"PAGAR", "RECEBER"}:
            raise ValueError("Tipo financeiro deve ser PAGAR ou RECEBER.")
        valor_decimal = self._dinheiro(valor)
        if valor_decimal <= 0:
            raise ValueError("O valor do título deve ser maior que zero.")
        vencimento = self._data_iso(data_vencimento)
        emissao = self._data_iso(data_emissao, padrao_hoje=True)
        origem_normalizada = str(origem or "MANUAL").strip().upper()
        origem_id_normalizada = str(origem_id or "").strip()
        documento_normalizado = str(documento or "").strip()

        def executar(conn) -> int:
            if origem_id_normalizada:
                existente = self.repository.buscar_por_origem(
                    tipo_normalizado, origem_normalizada, origem_id_normalizada,
                    documento_normalizado, conn,
                )
                if existente:
                    return int(existente["id"])
            titulo_id = self.repository.criar_titulo(
                tipo=tipo_normalizado,
                origem=origem_normalizada,
                origem_id=origem_id_normalizada,
                pessoa_id=int(pessoa_id) if pessoa_id is not None else None,
                pessoa_nome=str(pessoa_nome or "").strip(),
                documento=documento_normalizado,
                descricao=str(descricao or "").strip(),
                data_emissao=emissao,
                data_vencimento=vencimento,
                valor_original=valor_decimal,
                observacao=str(observacao or "").strip(),
                connection=conn,
            )
            self.repository.registrar_auditoria(
                usuario=usuario, acao="CRIAR_TITULO", objeto=str(titulo_id),
                detalhes=f"{tipo_normalizado}; valor={valor_decimal:.2f}; vencimento={vencimento}",
                connection=conn,
            )
            return titulo_id

        if connection is not None:
            return executar(connection)
        with self.database.session(write=True) as conn:
            return executar(conn)

    def _sincronizar_pagamento_venda_legada(
        self, connection, *, titulo: dict[str, Any], pagamento_id: int,
        valor: Decimal, data_pagamento: str,
    ) -> None:
        """Atualiza parcela, movimento e saldo do cliente da venda a crediário.

        A fotografia anterior é persistida em ``configuracoes`` para permitir um
        estorno exato. Bancos antigos sem as tabelas legadas continuam
        funcionando sem essa sincronização.
        """

        if str(titulo.get("origem") or "").upper() != "VENDA":
            return
        origem_id = str(titulo.get("origem_id") or "").strip()
        if not origem_id:
            return
        estado = self.repository.carregar_estado_venda_legada(int(origem_id), connection)
        if not estado:
            return
        mov = estado["movimento"]
        parcelas = estado["parcelas"]
        cliente = estado["cliente"]
        movement_columns = estado["movement_columns"]
        parcel_columns = estado["parcel_columns"]
        customer_columns = estado["customer_columns"]
        aberto = DecimalStorage.read(
            mov.get("valor_aberto_decimal"), mov.get("valor_aberto", 0), field="valor em aberto"
        )
        if valor > aberto:
            raise ValueError("Pagamento excede o saldo legado da venda.")
        snapshot = {"movimento": mov, "parcelas": parcelas, "cliente": cliente}
        restante = valor
        for parcela in parcelas:
            if restante <= 0:
                break
            valor_parcela = DecimalStorage.read(
                parcela.get("valor_parcela_decimal"), parcela["valor_parcela"], field="valor da parcela"
            )
            pago_anterior = DecimalStorage.read(
                parcela.get("valor_pago_decimal"), parcela["valor_pago"], field="valor pago da parcela"
            )
            falta = max(Decimal("0"), valor_parcela - pago_anterior)
            aplicado = min(restante, falta)
            if aplicado <= 0:
                continue
            novo_pago = (pago_anterior + aplicado).quantize(self.DINHEIRO)
            quitada = novo_pago >= valor_parcela
            vencimento = str(parcela.get("vencimento") or "")
            atraso = int(parcela.get("atraso_registrado") or 0)
            if quitada and vencimento and data_pagamento > vencimento[:10]:
                atraso = 1
            self.repository.atualizar_parcela_legada(
                int(parcela["id"]), valor_pago=novo_pago,
                status="PAGO" if quitada else "PARCIAL",
                data_pagamento=data_pagamento if quitada else str(parcela.get("data_pagamento") or ""),
                atraso=atraso, possui_decimal="valor_pago_decimal" in parcel_columns,
                connection=connection,
            )
            restante -= aplicado
        if restante > Decimal("0.001"):
            raise ValueError("Parcelas da venda não comportam o pagamento informado.")

        novo_aberto = (aberto - valor).quantize(self.DINHEIRO)
        self.repository.atualizar_movimento_legado(
            int(origem_id), valor_aberto=novo_aberto,
            status="PAGO" if novo_aberto == 0 else "PARCIAL",
            possui_decimal="valor_aberto_decimal" in movement_columns, connection=connection,
        )
        if cliente:
            novo_saldo = max(
                Decimal("0"),
                DecimalStorage.read(cliente.get("saldo_devedor_decimal"), cliente["saldo_devedor"], field="saldo devedor") - valor,
            )
            self.repository.atualizar_cliente_legado(
                int(cliente["id"]), saldo_devedor=novo_saldo,
                possui_decimal="saldo_devedor_decimal" in customer_columns, connection=connection,
            )
        self.repository.salvar_configuracao_json(
            f"financeiro_pagamento_legado:{int(pagamento_id)}", snapshot, connection
        )

    def _restaurar_pagamento_venda_legada(self, connection, pagamento_id: int, titulo_id: int) -> None:

        chave = f"financeiro_pagamento_legado:{int(pagamento_id)}"
        snapshot = self.repository.obter_configuracao_json(chave, connection)
        if not snapshot:
            return
        if self.repository.existe_pagamento_posterior(int(titulo_id), int(pagamento_id), connection):
            raise ValueError("Estorne primeiro os pagamentos mais recentes deste título.")
        movimento = snapshot.get("movimento") or {}
        if movimento:
            movement_columns = self.repository.colunas_tabela("movimentacoes", connection)
            valor_aberto = DecimalStorage.read(
                movimento.get("valor_aberto_decimal"), movimento.get("valor_aberto", 0), field="valor em aberto"
            )
            self.repository.atualizar_movimento_legado(
                int(movimento["id"]), valor_aberto=valor_aberto,
                status=movimento.get("status_pagamento"),
                possui_decimal="valor_aberto_decimal" in movement_columns, connection=connection,
            )
        parcel_columns = (
            self.repository.colunas_tabela("parcelas", connection)
            if self.repository.tabela_existe("parcelas", connection) else set()
        )
        for parcela in snapshot.get("parcelas") or []:
            valor_pago = DecimalStorage.read(
                parcela.get("valor_pago_decimal"), parcela.get("valor_pago", 0), field="valor pago da parcela"
            )
            self.repository.atualizar_parcela_legada(
                int(parcela["id"]), valor_pago=valor_pago,
                status=parcela.get("status", "PENDENTE"),
                data_pagamento=parcela.get("data_pagamento", ""),
                atraso=int(parcela.get("atraso_registrado", 0)),
                possui_decimal="valor_pago_decimal" in parcel_columns, connection=connection,
            )
        cliente = snapshot.get("cliente")
        if cliente:
            customer_columns = self.repository.colunas_tabela("clientes", connection)
            saldo = DecimalStorage.read(
                cliente.get("saldo_devedor_decimal"), cliente.get("saldo_devedor", 0), field="saldo devedor"
            )
            self.repository.atualizar_cliente_legado(
                int(cliente["id"]), saldo_devedor=saldo,
                possui_decimal="saldo_devedor_decimal" in customer_columns, connection=connection,
            )
        self.repository.excluir_configuracao(chave, connection)

    def pagar(
        self,
        titulo_id: int,
        valor: Any,
        *,
        forma_pagamento: str = "",
        observacao: str = "",
        usuario: str = "Sistema",
        data_pagamento: str | date | datetime | None = None,
    ) -> ResultadoPagamento:
        valor_decimal = self._dinheiro(valor)
        if valor_decimal <= 0:
            raise ValueError("O pagamento deve ser maior que zero.")
        data_iso = self._data_iso(data_pagamento, padrao_hoje=True)
        with self.database.session(write=True) as connection:
            titulo = self.repository.obter_titulo(int(titulo_id), connection)
            if not titulo:
                raise ValueError("Título financeiro não encontrado.")
            if titulo["status"] in {"PAGO", "CANCELADO"}:
                raise ValueError(f"Título {titulo['status'].lower()} não aceita pagamento.")
            saldo = self._dinheiro(titulo["valor_original"]) - self._dinheiro(titulo["valor_pago"])
            if valor_decimal > saldo:
                raise ValueError(f"Pagamento excede o saldo aberto de R$ {saldo:.2f}.")
            novo_pago = (self._dinheiro(titulo["valor_pago"]) + valor_decimal).quantize(self.DINHEIRO)
            novo_saldo = (self._dinheiro(titulo["valor_original"]) - novo_pago).quantize(self.DINHEIRO)
            status = "PAGO" if novo_saldo == 0 else "PARCIAL"
            pagamento_id = self.repository.registrar_pagamento(
                titulo_id=int(titulo_id), valor=valor_decimal,
                forma_pagamento=self._forma_pagamento(forma_pagamento),
                observacao=str(observacao or "").strip(), usuario=str(usuario or "Sistema"),
                data_pagamento=data_iso, connection=connection,
            )
            self.repository.atualizar_pagamento_titulo(int(titulo_id), novo_pago, status, connection)
            self._sincronizar_pagamento_venda_legada(
                connection, titulo=dict(titulo), pagamento_id=pagamento_id,
                valor=valor_decimal, data_pagamento=data_iso,
            )
            self.repository.registrar_auditoria(
                usuario=usuario, acao="PAGAR_TITULO", objeto=str(titulo_id),
                detalhes=f"pagamento={pagamento_id}; valor={valor_decimal:.2f}; status={status}",
                connection=connection,
            )
        return ResultadoPagamento(
            titulo_id=int(titulo_id), pagamento_id=pagamento_id,
            valor_pago=novo_pago, saldo_aberto=novo_saldo, status=status,
        )

    def registrar_venda_crediario_transacao(
        self,
        connection,
        *,
        venda_id: int,
        cliente_id: int | None,
        cliente_nome: str,
        valor: Any,
        data_vencimento: str | date | datetime,
        descricao: str = "Venda a crediário",
        usuario: str = "Sistema",
    ) -> int:
        """Cria o contas a receber da venda dentro da transação do PDV."""
        return self.criar_titulo(
            tipo="RECEBER",
            valor=valor,
            data_vencimento=data_vencimento,
            pessoa_id=cliente_id,
            pessoa_nome=cliente_nome,
            documento=f"VENDA-{int(venda_id)}",
            descricao=descricao,
            origem="VENDA",
            origem_id=str(int(venda_id)),
            usuario=usuario,
            connection=connection,
        )

    def registrar_recebimento_venda_transacao(
        self, connection, *, venda_id: int, valor: Any, forma_pagamento: str,
        observacao: str = "", usuario: str = "Sistema",
        data_pagamento: str | date | datetime | None = None,
    ) -> ResultadoPagamento | None:
        """Registra no Financeiro uma baixa já aplicada pelo módulo de Cobranças.

        O método altera somente o título financeiro. A movimentação, as parcelas e
        o saldo do cliente continuam sob responsabilidade da transação chamadora,
        evitando dupla baixa no legado. Vendas antigas sem título são aceitas.
        """
        titulo = self.repository.buscar_por_origem(
            "RECEBER", "VENDA", str(int(venda_id)), "", connection
        )
        if not titulo:
            titulo = self.repository.buscar_titulo_venda_aberto(int(venda_id), connection)
        if not titulo:
            return None
        if str(titulo.get("status", "")).upper() in {"PAGO", "CANCELADO"}:
            raise ValueError(f"Título da venda {venda_id} não aceita recebimento.")
        valor_n = self._dinheiro(valor)
        saldo = self._dinheiro(titulo["valor_original"]) - self._dinheiro(titulo["valor_pago"])
        if valor_n <= 0:
            raise ValueError("O recebimento deve ser maior que zero.")
        if valor_n > saldo:
            raise ValueError(f"Recebimento excede o título da venda em R$ {(valor_n-saldo):.2f}.")
        novo_pago = (self._dinheiro(titulo["valor_pago"]) + valor_n).quantize(self.DINHEIRO)
        novo_saldo = (self._dinheiro(titulo["valor_original"]) - novo_pago).quantize(self.DINHEIRO)
        status = "PAGO" if novo_saldo == 0 else "PARCIAL"
        pagamento_id = self.repository.registrar_pagamento(
            titulo_id=int(titulo["id"]), valor=valor_n,
            forma_pagamento=self._forma_pagamento(forma_pagamento),
            observacao=str(observacao or "").strip(), usuario=str(usuario or "Sistema"),
            data_pagamento=self._data_iso(data_pagamento, padrao_hoje=True), connection=connection,
        )
        self.repository.atualizar_pagamento_titulo(int(titulo["id"]), novo_pago, status, connection)
        self.repository.registrar_auditoria(
            usuario=usuario, acao="RECEBER_COBRANCA", objeto=str(int(titulo["id"])),
            detalhes=f"venda={int(venda_id)}; pagamento={pagamento_id}; valor={valor_n:.2f}",
            connection=connection,
        )
        return ResultadoPagamento(
            int(titulo["id"]), pagamento_id, novo_pago, novo_saldo, status
        )

    def cancelar_titulos_origem_transacao(
        self,
        connection,
        *,
        tipo: str,
        origem: str,
        origem_id: str | int,
        usuario: str = "Sistema",
    ) -> list[int]:
        """Cancela títulos sem pagamento vinculados a uma operação na mesma transação."""
        rows = self.repository.listar_titulos_origem_ativos(
            tipo=tipo, origem=origem, origem_id=origem_id, connection=connection
        )
        cancelados: list[int] = []
        for row in rows:
            titulo_id = int(row["id"])
            valor_pago = row["valor_pago"]
            status = row["status"]
            if str(status).upper() == "PAGO" or self._dinheiro(valor_pago) > 0:
                raise ValueError(f"Título {titulo_id} possui pagamento e impede o cancelamento da origem.")
            self.repository.cancelar_titulo(titulo_id, connection)
            self.repository.registrar_auditoria(
                usuario=usuario, acao="CANCELAR_TITULO_ORIGEM", objeto=str(titulo_id),
                detalhes=f"origem={origem}; origem_id={origem_id}", connection=connection,
            )
            cancelados.append(titulo_id)
        return cancelados

    def cancelar(self, titulo_id: int, *, usuario: str = "Sistema") -> None:
        with self.database.session(write=True) as connection:
            titulo = self.repository.obter_titulo(int(titulo_id), connection)
            if not titulo:
                raise ValueError("Título financeiro não encontrado.")
            if titulo["status"] == "PAGO" or self._dinheiro(titulo["valor_pago"]) > 0:
                raise ValueError("Título com pagamento não pode ser cancelado.")
            if titulo["status"] == "CANCELADO":
                return
            origem = str(titulo.get("origem") or "").strip().upper()
            if origem in {"VENDA", "COMPRA", "NFE", "XML", "NF-E"}:
                raise ValueError(
                    "Título integrado não pode ser cancelado isoladamente. "
                    "Cancele ou desfaça o documento no módulo de origem."
                )
            self.repository.cancelar_titulo(int(titulo_id), connection)
            self.repository.registrar_auditoria(
                usuario=usuario, acao="CANCELAR_TITULO", objeto=str(titulo_id),
                connection=connection,
            )

    def baixar(self, titulo_id: int, valor: Any, **kwargs) -> ResultadoPagamento:
        """Alias explícito para baixa parcial ou total."""
        return self.pagar(titulo_id, valor, **kwargs)


    @staticmethod
    def normalizar_filtros_titulos(tipo: Any = None, status: Any = None) -> tuple[str | None, str | None]:
        tipo_normalizado = str(tipo or "").strip().upper()
        status_normalizado = str(status or "").strip().upper()
        if tipo_normalizado in {"", "TODOS"}:
            tipo_normalizado = None
        elif tipo_normalizado not in {"PAGAR", "RECEBER"}:
            raise ValueError("Tipo financeiro inválido.")
        if status_normalizado in {"", "TODOS"}:
            status_normalizado = None
        elif status_normalizado not in {"ABERTO", "PARCIAL", "PAGO", "CANCELADO"}:
            raise ValueError("Status financeiro inválido.")
        return tipo_normalizado, status_normalizado

    def obter_recorrencia(self, identificador: str) -> dict[str, Any]:
        chave = str(identificador or "").strip()
        if not chave:
            raise ValueError("Identificador da recorrência é obrigatório.")
        recorrencia = next(
            (item for item in self.listar_recorrencias() if str(item.get("identificador", "")).strip() == chave),
            None,
        )
        if recorrencia is None:
            raise ValueError("Recorrência não encontrada.")
        return recorrencia

    def gerar_recorrencias_competencia(self, competencia: str, *, usuario: str = "Sistema") -> list[int]:
        texto = str(competencia or "").strip()
        try:
            data_competencia = datetime.strptime(texto, "%Y-%m")
        except ValueError as exc:
            raise ValueError("Competência inválida. Use AAAA-MM.") from exc
        return self.gerar_recorrencias(data_competencia.year, data_competencia.month, usuario=usuario)

    def listar_titulos(self, *, tipo: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        return self.repository.listar_titulos(tipo=tipo, status=status)

    def obter_titulo(self, titulo_id: int) -> dict[str, Any]:
        """Expõe o título já decimalizado sem vazar o repositório para a UI."""
        titulo = self.repository.obter_titulo(int(titulo_id))
        if not titulo:
            raise ValueError("Título financeiro não encontrado.")
        return titulo

    def saldo_titulo(self, titulo_id: int) -> Decimal:
        titulo = self.obter_titulo(titulo_id)
        return FinanceiroCalculator.saldo(titulo["valor_original"], titulo["valor_pago"])

    def listar_pagamentos(self, titulo_id: int) -> list[dict[str, Any]]:
        return self.repository.listar_pagamentos(titulo_id)

    def calcular_juros_multa(
        self,
        titulo_id: int,
        *,
        data_referencia: str | date | datetime | None = None,
        multa_percentual: Any = 0,
        juros_mensal_percentual: Any = 0,
    ) -> dict[str, Decimal | int]:
        titulo = self.repository.obter_titulo(int(titulo_id))
        if not titulo:
            raise ValueError("Título financeiro não encontrado.")
        referencia = datetime.strptime(self._data_iso(data_referencia, padrao_hoje=True), "%Y-%m-%d").date()
        vencimento = datetime.strptime(str(titulo["data_vencimento"]), "%Y-%m-%d").date()
        return FinanceiroCalculator.encargos(
            saldo=FinanceiroCalculator.saldo(titulo["valor_original"], titulo["valor_pago"]),
            vencimento=vencimento,
            referencia=referencia,
            multa_percentual=multa_percentual,
            juros_mensal_percentual=juros_mensal_percentual,
        )

    def fluxo_caixa(self, data_inicial: str | date | datetime, data_final: str | date | datetime) -> dict[str, Any]:
        inicio = self._data_iso(data_inicial)
        fim = self._data_iso(data_final)
        if inicio > fim:
            raise ValueError("Período financeiro inválido.")
        calculo = FinanceiroCalculator.fluxo_caixa(
            self.repository.listar_pagamentos_periodo(inicio, fim),
            self.repository.listar_movimentacoes_legadas_periodo(inicio, fim),
        )
        return {"data_inicial": inicio, "data_final": fim, **calculo}

    def dre(self, data_inicial: str | date | datetime, data_final: str | date | datetime) -> dict[str, Any]:
        inicio = self._data_iso(data_inicial)
        fim = self._data_iso(data_final)
        if inicio > fim:
            raise ValueError("Período financeiro inválido.")
        titulos = self.repository.listar_titulos_periodo(inicio, fim)
        pagamentos = self.repository.listar_pagamentos_periodo(inicio, fim)
        movimentos_legados = self.repository.listar_movimentacoes_legadas_periodo(inicio, fim)
        calculo = FinanceiroCalculator.dre(titulos, pagamentos, movimentos_legados)
        return {
            "data_inicial": inicio, "data_final": fim, **calculo,
            "titulos_competencia": titulos, "pagamentos_realizados": pagamentos,
            "movimentacoes_legadas": movimentos_legados,
        }

    def baixar_com_encargos(
        self, titulo_id: int, *, multa_percentual: Any = 0, juros_mensal_percentual: Any = 0,
        data_pagamento: str | date | datetime | None = None, forma_pagamento: str = "",
        usuario: str = "Sistema",
    ) -> ResultadoPagamento:
        calculo = self.calcular_juros_multa(
            titulo_id, data_referencia=data_pagamento, multa_percentual=multa_percentual,
            juros_mensal_percentual=juros_mensal_percentual,
        )
        encargos = self._dinheiro(calculo["multa"]) + self._dinheiro(calculo["juros"])
        with self.database.session(write=True) as connection:
            titulo = self.repository.obter_titulo(int(titulo_id), connection)
            if not titulo or titulo["status"] in {"PAGO", "CANCELADO"}:
                raise ValueError("Título não aceita baixa com encargos.")
            original = self._dinheiro(titulo["valor_original"])
            pago_anterior = self._dinheiro(titulo["valor_pago"])
            novo_original = (original + encargos).quantize(self.DINHEIRO)
            valor_baixa = (novo_original - pago_anterior).quantize(self.DINHEIRO)
            self.repository.atualizar_valor_original(int(titulo_id), novo_original, connection)
            pagamento_id = self.repository.registrar_pagamento(
                titulo_id=int(titulo_id), valor=valor_baixa, forma_pagamento=self._forma_pagamento(forma_pagamento),
                observacao=f"Encargos aplicados: juros={calculo['juros']:.2f}; multa={calculo['multa']:.2f}",
                usuario=str(usuario or "Sistema"),
                data_pagamento=self._data_iso(data_pagamento, padrao_hoje=True), connection=connection,
            )
            self.repository.atualizar_pagamento_titulo(int(titulo_id), novo_original, "PAGO", connection)

            # A venda/parcelas legadas representam somente o principal da dívida.
            # Juros e multa pertencem ao título financeiro e não podem inflar o
            # saldo original da venda nem o saldo devedor histórico do cliente.
            principal_aberto = (original - pago_anterior).quantize(self.DINHEIRO)
            if principal_aberto > 0:
                self._sincronizar_pagamento_venda_legada(
                    connection, titulo=dict(titulo), pagamento_id=pagamento_id,
                    valor=principal_aberto,
                    data_pagamento=self._data_iso(data_pagamento, padrao_hoje=True),
                )
            self.repository.registrar_auditoria(
                usuario=usuario, acao="BAIXAR_COM_ENCARGOS", objeto=str(titulo_id),
                detalhes=f"pagamento={pagamento_id}; encargos={encargos:.2f}", connection=connection,
            )
        return ResultadoPagamento(int(titulo_id), pagamento_id, novo_original, Decimal("0.00"), "PAGO")

    def estornar_pagamento(self, pagamento_id: int, *, usuario: str = "Sistema") -> ResultadoPagamento:
        with self.database.session(write=True) as connection:
            pagamento = self.repository.obter_pagamento(int(pagamento_id), connection)
            if not pagamento:
                raise ValueError("Pagamento não encontrado.")
            titulo = self.repository.obter_titulo(int(pagamento["titulo_id"]), connection)
            if not titulo or titulo["status"] == "CANCELADO":
                raise ValueError("Título inválido para estorno.")
            valor_pagamento = self._dinheiro(pagamento["valor"])
            novo_pago = (self._dinheiro(titulo["valor_pago"]) - valor_pagamento).quantize(self.DINHEIRO)
            if novo_pago < 0:
                raise ValueError("Pagamento inconsistente com o título.")

            # Baixas totais com encargos aumentam temporariamente o valor original.
            # Ao estornar essa baixa, os encargos precisam ser removidos também.
            encargos = FinanceiroCalculator.encargos_observacao(pagamento.get("observacao"))

            novo_original = (self._dinheiro(titulo["valor_original"]) - encargos).quantize(self.DINHEIRO)
            if novo_original < novo_pago:
                raise ValueError("Encargos do pagamento são inconsistentes com o título.")
            novo_saldo = (novo_original - novo_pago).quantize(self.DINHEIRO)
            status = "ABERTO" if novo_pago == 0 else "PARCIAL"
            self._restaurar_pagamento_venda_legada(
                connection, int(pagamento_id), int(titulo["id"])
            )
            self.repository.excluir_pagamento(int(pagamento_id), connection)
            if encargos:
                self.repository.atualizar_valor_original(int(titulo["id"]), novo_original, connection)
            self.repository.atualizar_pagamento_titulo(int(titulo["id"]), novo_pago, status, connection)
            conciliacoes = self.repository.obter_configuracao_json("financeiro_conciliacoes", connection)
            conciliacoes.pop(str(int(pagamento_id)), None)
            self.repository.salvar_configuracao_json("financeiro_conciliacoes", conciliacoes, connection)
            self.repository.registrar_auditoria(
                usuario=usuario, acao="ESTORNAR_PAGAMENTO", objeto=str(pagamento_id),
                detalhes=f"titulo={titulo['id']}; valor={self._dinheiro(pagamento['valor']):.2f}; encargos_revertidos={encargos:.2f}",
                connection=connection,
            )
        return ResultadoPagamento(int(titulo["id"]), int(pagamento_id), novo_pago, novo_saldo, status)

    def definir_centro_custo(self, titulo_id: int, centro_custo: str, *, usuario: str = "Sistema") -> None:
        if not self.repository.obter_titulo(int(titulo_id)):
            raise ValueError("Título financeiro não encontrado.")
        centro = str(centro_custo or "").strip().upper()
        with self.database.session(write=True) as conn:
            chave = "financeiro_centros_custo"
            dados = self.repository.obter_configuracao_json(chave, conn)
            if centro:
                dados[str(int(titulo_id))] = centro
            else:
                dados.pop(str(int(titulo_id)), None)
            self.repository.salvar_configuracao_json(chave, dados, conn)
            self.repository.registrar_auditoria(usuario=usuario, acao="CENTRO_CUSTO", objeto=str(titulo_id), detalhes=centro, connection=conn)

    def obter_centro_custo(self, titulo_id: int) -> str:
        dados = self.repository.obter_configuracao_json("financeiro_centros_custo")
        return str(dados.get(str(int(titulo_id)), ""))

    def conciliar_pagamento(self, pagamento_id: int, referencia: str, *, usuario: str = "Sistema") -> None:
        ref = str(referencia or "").strip()
        if not ref:
            raise ValueError("Referência de conciliação obrigatória.")
        with self.database.session(write=True) as conn:
            existe = self.repository.pagamento_existe(int(pagamento_id), conn)
            if not existe:
                raise ValueError("Pagamento não encontrado.")
            chave = "financeiro_conciliacoes"
            dados = self.repository.obter_configuracao_json(chave, conn)
            dados[str(int(pagamento_id))] = {"referencia": ref, "usuario": str(usuario or "Sistema"), "data": datetime.now().isoformat(timespec="seconds")}
            self.repository.salvar_configuracao_json(chave, dados, conn)
            self.repository.registrar_auditoria(
                usuario=usuario, acao="CONCILIAR_PAGAMENTO",
                objeto=str(int(pagamento_id)), detalhes=ref, connection=conn,
            )

    def criar_recorrencia(self, *, identificador: str, tipo: str, valor: Any, dia_vencimento: int, descricao: str = "", pessoa_nome: str = "", usuario: str = "Sistema") -> None:
        ident = str(identificador or "").strip()
        if not ident:
            raise ValueError("Identificador da recorrência obrigatório.")
        tipo_n = str(tipo or "").upper()
        if tipo_n not in {"PAGAR", "RECEBER"}:
            raise ValueError("Tipo financeiro deve ser PAGAR ou RECEBER.")
        valor_n = self._dinheiro(valor)
        if valor_n <= 0 or not 1 <= int(dia_vencimento) <= 31:
            raise ValueError("Valor ou dia de vencimento inválido.")
        with self.database.session(write=True) as conn:
            chave = "financeiro_recorrencias"
            dados = self.repository.obter_configuracao_json(chave, conn)
            dados[ident] = {"tipo": tipo_n, "valor": DecimalStorage.canonical(valor_n, field="valor da recorrência"), "dia_vencimento": int(dia_vencimento), "descricao": str(descricao), "pessoa_nome": str(pessoa_nome), "ativo": True}
            self.repository.salvar_configuracao_json(chave, dados, conn)
            self.repository.registrar_auditoria(
                usuario=usuario, acao="CRIAR_RECORRENCIA", objeto=ident,
                detalhes=f"tipo={tipo_n}; valor={valor_n:.2f}; dia={int(dia_vencimento)}", connection=conn,
            )

    def editar_recorrencia(
        self, identificador: str, *, tipo: str, valor: Any, dia_vencimento: int,
        descricao: str = "", pessoa_nome: str = "", usuario: str = "Sistema",
    ) -> None:
        ident = str(identificador or "").strip()
        tipo_n = str(tipo or "").strip().upper()
        valor_n = self._dinheiro(valor)
        if tipo_n not in {"PAGAR", "RECEBER"}:
            raise ValueError("Tipo financeiro deve ser PAGAR ou RECEBER.")
        if valor_n <= 0 or not 1 <= int(dia_vencimento) <= 31:
            raise ValueError("Valor ou dia de vencimento inválido.")
        with self.database.session(write=True) as conn:
            dados = self.repository.obter_configuracao_json("financeiro_recorrencias", conn)
            if ident not in dados:
                raise ValueError("Recorrência não encontrada.")
            ativo = bool(dados[ident].get("ativo", True))
            dados[ident] = {
                "tipo": tipo_n, "valor": DecimalStorage.canonical(valor_n, field="valor da recorrência"), "dia_vencimento": int(dia_vencimento),
                "descricao": str(descricao or ""), "pessoa_nome": str(pessoa_nome or ""), "ativo": ativo,
            }
            self.repository.salvar_configuracao_json("financeiro_recorrencias", dados, conn)
            self.repository.registrar_auditoria(
                usuario=usuario, acao="EDITAR_RECORRENCIA", objeto=ident,
                detalhes=f"tipo={tipo_n}; valor={valor_n:.2f}; dia={int(dia_vencimento)}", connection=conn,
            )

    def listar_recorrencias(self) -> list[dict[str, Any]]:
        dados = self.repository.obter_configuracao_json("financeiro_recorrencias")
        resultado: list[dict[str, Any]] = []
        for ident, regra in sorted(dados.items()):
            item = {"identificador": ident, **regra}
            item["valor"] = self._dinheiro(item.get("valor", 0))
            resultado.append(item)
        return resultado

    def ativar_recorrencia(self, identificador: str, ativo: bool, *, usuario: str = "Sistema") -> None:
        ident = str(identificador or "").strip()
        with self.database.session(write=True) as conn:
            dados = self.repository.obter_configuracao_json("financeiro_recorrencias", conn)
            if ident not in dados:
                raise ValueError("Recorrência não encontrada.")
            dados[ident]["ativo"] = bool(ativo)
            self.repository.salvar_configuracao_json("financeiro_recorrencias", dados, conn)
            self.repository.registrar_auditoria(
                usuario=usuario, acao="ATIVAR_RECORRENCIA", objeto=ident,
                detalhes="ATIVA" if ativo else "INATIVA", connection=conn,
            )

    def excluir_recorrencia(self, identificador: str, *, usuario: str = "Sistema") -> None:
        ident = str(identificador or "").strip()
        with self.database.session(write=True) as conn:
            dados = self.repository.obter_configuracao_json("financeiro_recorrencias", conn)
            if ident not in dados:
                raise ValueError("Recorrência não encontrada.")
            dados.pop(ident)
            self.repository.salvar_configuracao_json("financeiro_recorrencias", dados, conn)
            self.repository.registrar_auditoria(
                usuario=usuario, acao="EXCLUIR_RECORRENCIA", objeto=ident, connection=conn,
            )

    def listar_conciliacoes(self) -> list[dict[str, Any]]:
        dados = self.repository.obter_configuracao_json("financeiro_conciliacoes")
        resultado = []
        for pagamento in self.repository.listar_todos_pagamentos():
            item = dict(pagamento)
            item["conciliacao"] = dados.get(str(int(pagamento["id"])))
            item["conciliado"] = bool(item["conciliacao"] )
            resultado.append(item)
        return resultado

    def desfazer_conciliacao(self, pagamento_id: int, *, usuario: str = "Sistema") -> None:
        with self.database.session(write=True) as conn:
            dados = self.repository.obter_configuracao_json("financeiro_conciliacoes", conn)
            if str(int(pagamento_id)) not in dados:
                raise ValueError("Pagamento não está conciliado.")
            dados.pop(str(int(pagamento_id)))
            self.repository.salvar_configuracao_json("financeiro_conciliacoes", dados, conn)
            self.repository.registrar_auditoria(
                usuario=usuario, acao="DESFAZER_CONCILIACAO",
                objeto=str(int(pagamento_id)), connection=conn,
            )

    def listar_centros_custo(self) -> list[str]:
        dados = self.repository.obter_configuracao_json("financeiro_centros_custo")
        return sorted({str(v).strip().upper() for v in dados.values() if str(v).strip()})

    def relatorio_centros_custo(self, data_inicial: str, data_final: str) -> list[dict[str, Any]]:
        centros = {}
        centros_por_titulo = self.repository.obter_configuracao_json("financeiro_centros_custo")
        for titulo in self.repository.listar_titulos_periodo(self._data_iso(data_inicial), self._data_iso(data_final)):
            centro = str(centros_por_titulo.get(str(int(titulo["id"])), "")).strip() or "SEM CENTRO"
            item = centros.setdefault(centro, {"centro_custo": centro, "pagar": self.ZERO, "receber": self.ZERO})
            item["pagar" if titulo["tipo"] == "PAGAR" else "receber"] += self._dinheiro(titulo["valor_original"])
        return [{"centro_custo": v["centro_custo"], "pagar": v["pagar"], "receber": v["receber"], "saldo": v["receber"]-v["pagar"]} for v in centros.values()]

    def gerar_recorrencias(self, ano: int, mes: int, *, usuario: str = "Sistema") -> list[int]:
        import calendar
        dados = self.repository.obter_configuracao_json("financeiro_recorrencias")
        criados: list[int] = []
        ultimo_dia = calendar.monthrange(int(ano), int(mes))[1]
        for ident, regra in dados.items():
            if not regra.get("ativo", True):
                continue
            dia = min(int(regra["dia_vencimento"]), ultimo_dia)
            vencimento = date(int(ano), int(mes), dia).isoformat()
            titulo = self.criar_titulo(tipo=regra["tipo"], valor=regra["valor"], data_vencimento=vencimento, pessoa_nome=regra.get("pessoa_nome", ""), descricao=regra.get("descricao", ""), origem="RECORRENTE", origem_id=ident, documento=f"{ano:04d}-{mes:02d}", usuario=usuario)
            criados.append(titulo)
        return criados

    def _reconciliar_cliente_transacao(self, connection, cliente_id: int, *, corrigir: bool) -> dict[str, Any]:
        estado = self.repository.carregar_estado_reconciliacao_cliente(int(cliente_id), connection)
        if not estado:
            raise ValueError("Cliente não encontrado.")
        reconciliacao = FinanceiroCalculator.reconciliar_cliente(
            estado["cliente"]["saldo_devedor"], estado["compras"]
        )
        if reconciliacao["bloqueios"]:
            raise ValueError(
                "Divergência histórica não reconciliável entre compras e parcelas; pagamento cancelado."
            )
        if corrigir and reconciliacao["divergencias"]:
            for ajuste in reconciliacao["ajustes_parcelas"]:
                self.repository.reconciliar_valor_pago_parcela(
                    ajuste["parcela_id"], valor_pago=ajuste["valor_pago"],
                    status=ajuste["status"], connection=connection,
                )
            # Nunca reduzir saldo consolidado histórico apenas por ausência de
            # detalhes migrados. Atualizamos somente quando as compras comprovam
            # saldo maior que o saldo armazenado do cliente.
            if reconciliacao["saldo_informado"] < reconciliacao["saldo_real"]:
                self.repository.atualizar_saldo_cliente(
                    int(cliente_id), reconciliacao["saldo_real"], connection
                )
            estado = self.repository.carregar_estado_reconciliacao_cliente(int(cliente_id), connection)
            reconciliacao = FinanceiroCalculator.reconciliar_cliente(
                estado["cliente"]["saldo_devedor"], estado["compras"]
            )
            if reconciliacao["bloqueios"]:
                raise ValueError("Não foi possível reconciliar o saldo financeiro do cliente.")
        return reconciliacao

    def reconciliar_cliente(self, cliente_id: int) -> dict[str, Any]:
        with self.database.session(write=True) as connection:
            return self._reconciliar_cliente_transacao(connection, int(cliente_id), corrigir=True)

    def preparar_recebimento_cliente(self, cliente_id: int) -> dict[str, Any]:
        with self.database.session(write=True) as connection:
            reconciliacao = self._reconciliar_cliente_transacao(connection, int(cliente_id), corrigir=True)
            cliente = self.repository.obter_cliente_crediario(int(cliente_id), connection)
        saldo = reconciliacao["saldo_real"]
        return {
            "cliente": cliente, "saldo": saldo,
            # Recebimento é sempre sobre o saldo total. Compra/parcela específica
            # deixou de ser uma opção operacional; a distribuição é interna.
            "alvos": {"Saldo total do cliente": {"tipo": "AUTO", "limite": saldo}},
            "saldo_compras": reconciliacao.get("saldo_compras", saldo),
            "saldo_residual_legado": reconciliacao.get("saldo_residual_legado", self.ZERO),
            "divergencias_corrigidas": reconciliacao["divergencias"],
        }

    def receber_pagamento_cliente(
        self, *, cliente_id: int, valor: Any, alvo: dict[str, Any] | None,
        forma_pagamento: str, observacao: str = "", usuario: str = "Sistema",
        data_pagamento: str | date | datetime | None = None,
        idempotency_key: str | None = None,
        operation_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        # A API aceita o parâmetro por compatibilidade, mas recebimentos novos
        # são sempre distribuídos automaticamente sobre o saldo total do cliente.
        hoje = self._data_iso(data_pagamento, padrao_hoje=True)
        data_movimento = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        forma = str(forma_pagamento or "Não informada").strip()
        observacao = str(observacao or "").strip()
        key = str(idempotency_key or "").strip()
        fingerprint = str(operation_fingerprint or "").strip().lower()
        if bool(key) != bool(fingerprint):
            raise ValueError("Chave idempotente e fingerprint devem ser informados juntos.")
        if key and (len(key) > 160 or len(fingerprint) != 64 or any(
            char not in "0123456789abcdef" for char in fingerprint
        )):
            raise ValueError("Identificação idempotente do recebimento inválida.")

        with self.database.session(write=True) as connection:
            if key:
                row = self.operation_journal.get(connection, key)
                if row is not None:
                    if row["fingerprint"].lower() != fingerprint:
                        raise PermissionError("A chave idempotente já pertence a outro conteúdo.")
                    if row["status"].upper() != "COMMITTED":
                        raise RuntimeError("O recebimento assistido possui estado persistente desconhecido.")
                    payload = json.loads(row["result_json"])
                    return {
                        "pagamento_mov_id": int(payload["pagamento_mov_id"]),
                        "valor": self._dinheiro(payload["valor"]),
                        "saldo_anterior": self._dinheiro(payload["saldo_anterior"]),
                        "novo_saldo": self._dinheiro(payload["novo_saldo"]),
                        "alocacoes": [],
                        "forma_pagamento": str(payload["forma_pagamento"]),
                        "observacao": str(payload.get("observacao") or ""),
                        "idempotent_replay": True,
                    }
                self.operation_journal.begin(
                    connection, idempotency_key=key,
                    operation_kind="CUSTOMER_RECEIPT", fingerprint=fingerprint,
                    username=str(usuario or "").strip(),
                )
            reconciliacao_antes = self._reconciliar_cliente_transacao(
                connection, int(cliente_id), corrigir=True
            )
            saldo = reconciliacao_antes["saldo_real"]
            compras = self.repository.listar_compras_para_alocacao(
                int(cliente_id), movimentacao_id=None, connection=connection,
            )
            pagamento = FinanceiroCalculator.limitar_pagamento(valor, saldo, saldo)

            detalhes = f"Pagamento recebido via {forma}"
            if observacao:
                detalhes += f" — {observacao}"
            pagamento_mov_id = self.repository.inserir_movimento_pagamento_cliente(
                cliente_id=int(cliente_id), descricao=detalhes, valor=pagamento,
                data=data_movimento, forma_pagamento=forma, connection=connection,
            )

            restante = pagamento
            alocacoes: list[dict[str, Any]] = []
            for compra in compras:
                if restante <= self.ZERO:
                    break
                aberto = self._dinheiro(compra["valor_aberto"])
                abatido = min(restante, aberto).quantize(self.DINHEIRO)
                venda_id = int(compra["id"])
                self.registrar_recebimento_venda_transacao(
                    connection, venda_id=venda_id, valor=abatido,
                    forma_pagamento=forma, observacao=observacao,
                    usuario=usuario, data_pagamento=hoje,
                )
                novo_aberto = (aberto - abatido).quantize(self.DINHEIRO)
                self.repository.atualizar_compra_aberta(
                    venda_id, novo_aberto, "PAGO" if novo_aberto == self.ZERO else "PARCIAL", connection,
                )
                alocacao = {
                    "venda_id": venda_id, "valor_aplicado": abatido,
                    "saldo_antes": aberto, "saldo_depois": novo_aberto,
                    "parcelas_aplicadas": [],
                }
                parcelas = self.repository.listar_parcelas_para_alocacao(
                    venda_id, parcela_id=None, connection=connection,
                )
                if not parcelas:
                    self.repository.criar_parcela_unica_se_ausente(venda_id, connection)
                    parcelas = self.repository.listar_parcelas_para_alocacao(
                        venda_id, parcela_id=None, connection=connection,
                    )
                a_distribuir = abatido
                for parcela in parcelas:
                    if a_distribuir <= self.ZERO:
                        break
                    falta = max(self.ZERO, FinanceiroCalculator.saldo(
                        parcela["valor_parcela"], parcela["valor_pago"]
                    ))
                    aplicado = min(a_distribuir, falta).quantize(self.DINHEIRO)
                    if aplicado <= self.ZERO:
                        continue
                    total_pago = (self._dinheiro(parcela["valor_pago"]) + aplicado).quantize(self.DINHEIRO)
                    quitada = total_pago >= self._dinheiro(parcela["valor_parcela"])
                    atraso = 0
                    if quitada and parcela["vencimento"]:
                        try:
                            atraso = int(date.fromisoformat(
                                FinanceiroCalculator.data_iso(parcela["vencimento"])
                            ) < date.fromisoformat(hoje))
                        except ValueError:
                            atraso = 0
                    self.repository.atualizar_parcela_pagamento(
                        int(parcela["id"]), valor_pago=total_pago,
                        status="PAGO" if quitada else "PARCIAL",
                        data_pagamento=hoje, registrar_data=quitada,
                        atraso=atraso, connection=connection,
                    )
                    alocacao["parcelas_aplicadas"].append({
                        "parcela_id": int(parcela["id"]),
                        "valor_aplicado": aplicado, "quitada": quitada,
                    })
                    a_distribuir = (a_distribuir - aplicado).quantize(self.DINHEIRO)
                if a_distribuir > self.ZERO:
                    # Parte da dívida da compra veio de migração sem parcela detalhada.
                    # O abatimento permanece válido no saldo da compra e é explicitado
                    # para auditoria/recibo em vez de bloquear o recebimento.
                    alocacao["valor_sem_parcela"] = a_distribuir
                    a_distribuir = self.ZERO
                alocacoes.append(alocacao)
                restante = (restante - abatido).quantize(self.DINHEIRO)

            saldo_residual_legado = self._dinheiro(
                reconciliacao_antes.get("saldo_residual_legado", self.ZERO)
            )
            aplicado_residual = self.ZERO
            if restante > self.ZERO:
                aplicado_residual = min(restante, saldo_residual_legado).quantize(self.DINHEIRO)
                restante = (restante - aplicado_residual).quantize(self.DINHEIRO)
                if aplicado_residual > self.ZERO:
                    alocacoes.append({
                        "tipo": "SALDO_LEGADO",
                        "valor_aplicado": aplicado_residual,
                        "saldo_antes": saldo_residual_legado,
                        "saldo_depois": (saldo_residual_legado - aplicado_residual).quantize(self.DINHEIRO),
                        "parcelas_aplicadas": [],
                    })
            if restante > self.ZERO:
                raise ValueError("O saldo total reconciliado não comporta o pagamento informado.")

            saldo_esperado = (saldo - pagamento).quantize(self.DINHEIRO)
            self.repository.atualizar_saldo_cliente(int(cliente_id), saldo_esperado, connection)
            reconciliacao_depois = self._reconciliar_cliente_transacao(
                connection, int(cliente_id), corrigir=False
            )
            if reconciliacao_depois["bloqueios"] or reconciliacao_depois["saldo_real"] != saldo_esperado:
                raise ValueError("Inconsistência financeira detectada após o pagamento; operação revertida.")

            if key:
                payload = json.dumps({
                    "pagamento_mov_id": int(pagamento_mov_id),
                    "valor": format(pagamento, "f"),
                    "saldo_anterior": format(saldo, "f"),
                    "novo_saldo": format(saldo_esperado, "f"),
                    "forma_pagamento": forma,
                    "observacao": observacao,
                }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                self.operation_journal.commit(
                    connection, idempotency_key=key, result_json=payload
                )

        return {
            "pagamento_mov_id": pagamento_mov_id,
            "valor": pagamento, "saldo_anterior": saldo,
            "novo_saldo": saldo_esperado, "alocacoes": alocacoes,
            "forma_pagamento": forma, "observacao": observacao,
            "idempotent_replay": False,
        }
