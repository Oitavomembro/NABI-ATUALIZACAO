from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable
import json
import re

from repositories import CompraRepository, EstoqueRepository
from repositories.assistant_operation_journal_repository import AssistantOperationJournalRepository
from services.financeiro_service import FinanceiroService


@dataclass(frozen=True)
class ResultadoRecebimentoCompra:
    pedido_id: int
    recebimento_id: int
    status_pedido: str
    itens_recebidos: int
    valor_total: Decimal


class CompraService:
    """Pedidos e recebimentos de compra com atualização transacional do estoque."""

    QTD = Decimal("0.0001")
    DINHEIRO = Decimal("0.01")

    def __init__(
        self,
        repository: CompraRepository,
        estoque_repository: EstoqueRepository,
        financeiro_service: FinanceiroService | None = None,
    ) -> None:
        self.repository = repository
        self.estoque_repository = estoque_repository
        self.financeiro_service = financeiro_service
        self.database = repository.database
        self.operation_journal = AssistantOperationJournalRepository()
        if estoque_repository.database.database_path != repository.database.database_path:
            raise ValueError("Os repositórios devem utilizar o mesmo banco de dados.")

    @classmethod
    def _decimal(cls, valor: Any, *, dinheiro: bool = False) -> Decimal:
        try:
            numero = Decimal(str(valor))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("Valor numérico inválido.") from exc
        return numero.quantize(cls.DINHEIRO if dinheiro else cls.QTD, rounding=ROUND_HALF_UP)

    def criar_pedido(
        self,
        fornecedor_id: int,
        itens: Iterable[dict[str, Any]],
        *,
        observacao: str = "",
        usuario: str = "Sistema",
        idempotency_key: str | None = None,
        operation_fingerprint: str | None = None,
    ) -> int:
        itens_normalizados = self._normalizar_itens_pedido(itens)
        key, fingerprint = self._idempotency_fields(
            idempotency_key, operation_fingerprint
        )
        with self.database.session(write=True) as connection:
            if key:
                previous = self.operation_journal.get(connection, key)
                if previous is not None:
                    if previous["fingerprint"].lower() != fingerprint:
                        raise PermissionError("A chave idempotente já pertence a outro conteúdo.")
                    if previous["status"].upper() != "COMMITTED":
                        raise RuntimeError("A operação assistida possui estado persistente desconhecido.")
                    return int(json.loads(previous["result_json"])["order_id"])
                self.operation_journal.begin(
                    connection, idempotency_key=key,
                    operation_kind="PURCHASE_ORDER_CREATE", fingerprint=fingerprint,
                    username=str(usuario or "Sistema"),
                )
            fornecedor = self.repository.buscar_fornecedor(int(fornecedor_id), connection)
            if not fornecedor or not bool(fornecedor["ativo"]):
                raise ValueError("Fornecedor não encontrado ou inativo.")
            for item in itens_normalizados:
                produto = self.repository.buscar_produto(item["produto_id"], connection)
                self._validar_produto_compra(produto)
            pedido_id = self.repository.criar_pedido(
                fornecedor_id=int(fornecedor_id), observacao=observacao,
                usuario=usuario, itens=itens_normalizados, connection=connection,
            )
            if key:
                connection.execute(
                    """INSERT INTO auditoria(data,usuario,modulo,acao,objeto,detalhes,resultado)
                       VALUES(datetime('now','localtime'),?,'Compras','CRIAR_PEDIDO',?,?, 'SUCESSO')""",
                    (str(usuario or "Sistema"), str(pedido_id),
                     f"Fornecedor {int(fornecedor_id)}; itens={len(itens_normalizados)}; idempotency={key}"),
                )
                self.operation_journal.commit(
                    connection, idempotency_key=key,
                    result_json=json.dumps({"order_id": pedido_id}, sort_keys=True, separators=(",", ":")),
                )
            return pedido_id

    def receber(
        self,
        pedido_id: int,
        itens: Iterable[dict[str, Any]],
        *,
        documento: str = "",
        observacao: str = "",
        usuario: str = "Sistema",
        gerar_conta_pagar: bool = False,
        data_vencimento: str | None = None,
        idempotency_key: str | None = None,
        operation_fingerprint: str | None = None,
    ) -> ResultadoRecebimentoCompra:
        itens_entrada = list(itens)
        if not itens_entrada:
            raise ValueError("Informe ao menos um item para recebimento.")
        key, fingerprint = self._idempotency_fields(
            idempotency_key, operation_fingerprint
        )
        with self.database.session(write=True) as connection:
            previous = self._begin_idempotent(
                connection, key=key, fingerprint=fingerprint, usuario=usuario
            )
            if previous is not None:
                return previous
            pedido = self.repository.obter_pedido(int(pedido_id), connection)
            if not pedido:
                raise ValueError("Pedido de compra não encontrado.")
            if pedido["status"] in {"RECEBIDO", "CANCELADO"}:
                raise ValueError(f"Pedido {pedido['status'].lower()} não aceita recebimento.")
            itens_pedido = {int(item["id"]): item for item in pedido["itens"]}
            recebidos: list[dict[str, Any]] = []
            valor_total = Decimal("0")
            ids_usados: set[int] = set()
            for bruto in itens_entrada:
                pedido_item_id = int(bruto.get("pedido_item_id") or 0)
                if pedido_item_id in ids_usados:
                    raise ValueError("O mesmo item do pedido foi informado mais de uma vez.")
                ids_usados.add(pedido_item_id)
                item_pedido = itens_pedido.get(pedido_item_id)
                if not item_pedido:
                    raise ValueError("Item não pertence ao pedido informado.")
                quantidade = self._decimal(bruto.get("quantidade"))
                if quantidade <= 0:
                    raise ValueError("A quantidade recebida deve ser maior que zero.")
                pendente = self._decimal(item_pedido["quantidade_pendente"])
                if quantidade > pendente:
                    raise ValueError(
                        f"Quantidade recebida de {item_pedido['codigo']} excede o saldo pendente ({float(pendente):g})."
                    )
                custo = self._decimal(bruto.get("custo_unitario", item_pedido["custo_unitario"]), dinheiro=True)
                if custo < 0:
                    raise ValueError("O custo unitário não pode ser negativo.")
                produto = self.repository.buscar_produto(int(item_pedido["produto_id"]), connection)
                self._validar_produto_compra(produto)
                fator = self._decimal(produto.get("fator_conversao") or 1)
                if fator <= 0:
                    raise ValueError(f"Fator de conversão inválido no produto {produto['codigo']}.")
                quantidade_estoque = (quantidade * fator).quantize(self.QTD)
                custo_estoque = (custo / fator).quantize(self.DINHEIRO, rounding=ROUND_HALF_UP)
                total = (quantidade * custo).quantize(self.DINHEIRO, rounding=ROUND_HALF_UP)
                saldo_anterior = self._decimal(produto["estoque_atual"])
                saldo_atual = (saldo_anterior + quantidade_estoque).quantize(self.QTD)
                self.estoque_repository.atualizar_saldo(int(produto["id"]), float(saldo_atual), connection)
                self.estoque_repository.registrar_movimentacao(
                    produto_id=int(produto["id"]), tipo="ENTRADA", quantidade=float(quantidade_estoque),
                    saldo_anterior=float(saldo_anterior), saldo_atual=float(saldo_atual),
                    origem="COMPRA", origem_id=f"{int(pedido_id)}:{pedido_item_id}:{float(item_pedido['quantidade_recebida']):g}",
                    motivo=f"Recebimento do pedido de compra {int(pedido_id)}",
                    usuario=usuario, connection=connection,
                )
                self.repository.atualizar_custo_produto(
                    int(produto["id"]), custo_estoque, int(pedido["fornecedor_id"]), connection
                )
                recebidos.append({
                    "pedido_item_id": pedido_item_id,
                    "produto_id": int(produto["id"]),
                    "quantidade": float(quantidade),
                    "custo_unitario": custo,
                    "valor_total": total,
                })
                valor_total += total
            recebimento_id = self.repository.registrar_recebimento(
                pedido_id=int(pedido_id), documento=documento, observacao=observacao,
                usuario=usuario, itens=recebidos, connection=connection,
            )
            status = self.repository.atualizar_status_pedido(int(pedido_id), connection)
            if gerar_conta_pagar:
                if self.financeiro_service is None:
                    raise ValueError("Serviço financeiro não configurado para gerar conta a pagar.")
                if not data_vencimento:
                    raise ValueError("Informe a data de vencimento da conta a pagar.")
                self.financeiro_service.criar_titulo(
                    tipo="PAGAR",
                    valor=valor_total,
                    data_vencimento=data_vencimento,
                    pessoa_id=int(pedido["fornecedor_id"]),
                    pessoa_nome=str(pedido.get("fornecedor_nome") or ""),
                    documento=str(documento or ""),
                    descricao=f"Recebimento do pedido de compra {int(pedido_id)}",
                    observacao=str(observacao or ""),
                    origem="RECEBIMENTO_COMPRA",
                    origem_id=str(recebimento_id),
                    usuario=usuario,
                    connection=connection,
                )
            result = ResultadoRecebimentoCompra(
                pedido_id=int(pedido_id), recebimento_id=recebimento_id,
                status_pedido=status, itens_recebidos=len(recebidos),
                valor_total=valor_total,
            )
            connection.execute(
                """
                INSERT INTO auditoria(data,usuario,modulo,acao,objeto,detalhes,resultado)
                VALUES(datetime('now','localtime'),?,'Compras','RECEBER',?,?, 'SUCESSO')
                """,
                (str(usuario or "Sistema"), str(pedido_id),
                 f"Recebimento {recebimento_id}; itens={len(recebidos)}; "
                 f"total={valor_total:.2f}; idempotency={key or '-'}"),
            )
            self._commit_idempotent(connection, key=key, result=result)
        return result

    @staticmethod
    def _idempotency_fields(key, fingerprint) -> tuple[str, str]:
        normalized_key = str(key or "").strip()
        normalized_fingerprint = str(fingerprint or "").strip().lower()
        if not normalized_key and not normalized_fingerprint:
            return "", ""
        if not normalized_key or not normalized_fingerprint:
            raise ValueError("Chave idempotente e fingerprint devem ser informados juntos.")
        if len(normalized_key) > 128 or not re.fullmatch(r"[A-Za-z0-9:._-]+", normalized_key):
            raise ValueError("Chave idempotente inválida.")
        if not re.fullmatch(r"[0-9a-f]{64}", normalized_fingerprint):
            raise ValueError("Fingerprint da operação inválido.")
        return normalized_key, normalized_fingerprint

    @staticmethod
    def _begin_idempotent(connection, *, key: str, fingerprint: str, usuario: str):
        if not key:
            return None
        try:
            row = connection.execute(
                "SELECT fingerprint,status,result_json FROM assistant_operation_journal "
                "WHERE idempotency_key=?",
                (key,),
            ).fetchone()
        except Exception as error:
            raise RuntimeError(
                "O banco ainda não possui o diário idempotente de operações assistidas."
            ) from error
        if row is not None:
            if str(row["fingerprint"]).lower() != fingerprint:
                raise PermissionError("A chave idempotente já pertence a outro conteúdo.")
            if str(row["status"]).upper() != "COMMITTED":
                raise RuntimeError("A operação assistida possui estado persistente desconhecido.")
            payload = json.loads(str(row["result_json"] or "{}"))
            return ResultadoRecebimentoCompra(
                pedido_id=int(payload["pedido_id"]),
                recebimento_id=int(payload["recebimento_id"]),
                status_pedido=str(payload["status_pedido"]),
                itens_recebidos=int(payload["itens_recebidos"]),
                valor_total=Decimal(str(payload["valor_total"])),
            )
        connection.execute(
            """INSERT INTO assistant_operation_journal
               (idempotency_key,operation_kind,fingerprint,status,result_json,username,created_at)
               VALUES(?,'PURCHASE_RECEIPT',?,'PENDING','',?,datetime('now','localtime'))""",
            (key, fingerprint, str(usuario or "Sistema")),
        )
        return None

    @staticmethod
    def _commit_idempotent(connection, *, key: str, result: ResultadoRecebimentoCompra) -> None:
        if not key:
            return
        payload = json.dumps({
            "pedido_id": result.pedido_id,
            "recebimento_id": result.recebimento_id,
            "status_pedido": result.status_pedido,
            "itens_recebidos": result.itens_recebidos,
            "valor_total": format(result.valor_total, "f"),
        }, sort_keys=True, separators=(",", ":"))
        updated = connection.execute(
            """UPDATE assistant_operation_journal
               SET status='COMMITTED',result_json=?,committed_at=datetime('now','localtime')
               WHERE idempotency_key=? AND status='PENDING'""",
            (payload, key),
        )
        if updated.rowcount != 1:
            raise RuntimeError("Não foi possível confirmar o diário idempotente.")

    def _normalizar_itens_pedido(self, itens: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        agregados: dict[int, dict[str, Any]] = {}
        for bruto in itens:
            produto_id = int(bruto.get("produto_id") or 0)
            if produto_id <= 0:
                raise ValueError("Produto inválido no pedido.")
            quantidade = self._decimal(bruto.get("quantidade"))
            custo = self._decimal(bruto.get("custo_unitario", 0), dinheiro=True)
            if quantidade <= 0:
                raise ValueError("A quantidade pedida deve ser maior que zero.")
            if custo < 0:
                raise ValueError("O custo unitário não pode ser negativo.")
            if produto_id in agregados:
                anterior = agregados[produto_id]
                qtd_total = self._decimal(anterior["quantidade"]) + quantidade
                valor_total = self._decimal(anterior["valor_total"], dinheiro=True) + (quantidade * custo)
                custo_medio = (valor_total / qtd_total).quantize(self.DINHEIRO, rounding=ROUND_HALF_UP)
                anterior.update(quantidade=float(qtd_total), custo_unitario=custo_medio, valor_total=valor_total)
            else:
                total = (quantidade * custo).quantize(self.DINHEIRO, rounding=ROUND_HALF_UP)
                agregados[produto_id] = {
                    "produto_id": produto_id,
                    "quantidade": float(quantidade),
                    "custo_unitario": custo,
                    "valor_total": total,
                    "observacao": str(bruto.get("observacao") or ""),
                }
        if not agregados:
            raise ValueError("Informe ao menos um item no pedido.")
        return list(agregados.values())

    @staticmethod
    def _validar_produto_compra(produto: dict[str, Any] | None) -> None:
        if not produto or not bool(produto["ativo"]):
            raise ValueError("Produto não encontrado ou inativo.")
        if produto["tipo_produto"] == "SERVICO" or not bool(produto["controla_estoque"]):
            raise ValueError(f"O produto {produto['codigo']} não controla estoque.")
