from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import tempfile
from decimal import Decimal
from typing import Any, Iterable

from repositories import EstoqueRepository
from validators import StockValidator


@dataclass(frozen=True)
class ResultadoMovimentacaoEstoque:
    produto_id: int
    saldo_anterior: float
    saldo_atual: float
    quantidade: float
    tipo: str
    movimentacao_id: int


@dataclass(frozen=True)
class ResultadoInventario:
    snapshot_path: str
    movimentacoes: tuple[ResultadoMovimentacaoEstoque, ...]


class EstoqueService:
    """Regras transacionais do estoque.

    Quantidades são normalizadas em até 4 casas decimais. Saídas ficam negativas
    nas movimentações; entradas ficam positivas.
    """

    CASAS = StockValidator.QUANTIZER

    def __init__(self, repository: EstoqueRepository) -> None:
        self.repository = repository
        self.database = repository.database

    @classmethod
    def _quantidade(cls, valor: Any, *, permitir_zero: bool = False) -> Decimal:
        return StockValidator.quantity(valor, allow_zero=permitir_zero)

    def saldo(self, produto_id: int) -> float:
        produto = self.repository.buscar_produto(int(produto_id))
        if not produto:
            raise ValueError("Produto não encontrado.")
        return float(produto["estoque_atual"])

    def entrada(
        self,
        produto_id: int,
        quantidade: float,
        *,
        origem: str,
        origem_id: str = "",
        motivo: str = "",
        usuario: str = "Sistema",
    ) -> ResultadoMovimentacaoEstoque:
        return self._movimentar(
            produto_id, quantidade, entrada=True, origem=origem,
            origem_id=origem_id, motivo=motivo, usuario=usuario,
        )

    def entrada_idempotente(
        self,
        produto_id: int,
        quantidade: float,
        *,
        origem: str,
        origem_id: str,
        motivo: str = "",
        usuario: str = "Sistema",
    ) -> ResultadoMovimentacaoEstoque | None:
        """Registra uma entrada apenas uma vez para a mesma origem/produto."""
        with self.database.session(write=True) as connection:
            existente = self.repository.buscar_movimentacao_por_origem(
                origem, str(origem_id), int(produto_id), connection
            )
            if existente:
                return None
        return self.entrada(
            produto_id,
            quantidade,
            origem=origem,
            origem_id=str(origem_id),
            motivo=motivo,
            usuario=usuario,
        )

    def saida(
        self,
        produto_id: int,
        quantidade: float,
        *,
        origem: str,
        origem_id: str = "",
        motivo: str = "",
        usuario: str = "Sistema",
    ) -> ResultadoMovimentacaoEstoque:
        return self._movimentar(
            produto_id, quantidade, entrada=False, origem=origem,
            origem_id=origem_id, motivo=motivo, usuario=usuario,
        )

    def ajustar(
        self,
        produto_id: int,
        novo_saldo: float,
        *,
        motivo: str,
        usuario: str = "Sistema",
    ) -> ResultadoMovimentacaoEstoque:
        with self.database.session(write=True) as connection:
            # Reserva a escrita antes de ler o saldo. Sem isso, duas conexões
            # podem ler o mesmo valor e confirmar um lost update.
            connection.execute("BEGIN IMMEDIATE")
            return self.ajustar_na_transacao(
                connection, produto_id, novo_saldo, motivo=motivo, usuario=usuario
            )

    def ajustar_na_transacao(
        self,
        connection,
        produto_id: int,
        novo_saldo: float,
        *,
        motivo: str,
        usuario: str = "Sistema",
    ) -> ResultadoMovimentacaoEstoque:
        if not str(motivo or "").strip():
            raise ValueError("Informe o motivo do ajuste de estoque.")
        saldo_destino = self._quantidade(novo_saldo, permitir_zero=True)
        produto = self.repository.buscar_produto(int(produto_id), connection)
        self._validar_produto(produto)
        saldo_anterior = Decimal(str(produto["estoque_atual"]))
        if not bool(produto["permite_estoque_negativo"]) and saldo_destino < 0:
            raise ValueError("O produto não permite estoque negativo.")
        diferenca = (saldo_destino - saldo_anterior).quantize(self.CASAS)
        self.repository.atualizar_saldo(int(produto_id), float(saldo_destino), connection)
        mov_id = self.repository.registrar_movimentacao(
            produto_id=int(produto_id), tipo="AJUSTE", quantidade=float(diferenca),
            saldo_anterior=float(saldo_anterior), saldo_atual=float(saldo_destino),
            origem="AJUSTE", motivo=str(motivo).strip(), usuario=usuario, connection=connection,
        )
        return ResultadoMovimentacaoEstoque(
            int(produto_id), float(saldo_anterior), float(saldo_destino),
            float(diferenca), "AJUSTE", mov_id,
        )

    def criar_snapshot(self, produto_ids: Iterable[int], *, diretorio: str | Path | None = None) -> str:
        ids = sorted({int(produto_id) for produto_id in produto_ids})
        if not ids:
            raise ValueError("Nenhum produto informado para o snapshot.")
        with self.database.session() as connection:
            produtos = []
            for produto_id in ids:
                produto = self.repository.buscar_produto(produto_id, connection)
                self._validar_produto(produto)
                produtos.append({
                    "id": produto_id, "codigo": produto["codigo"], "nome": produto["nome"],
                    "estoque_atual": float(produto["estoque_atual"]),
                    "estoque_minimo": float(produto["estoque_minimo"]),
                })
        pasta = Path(diretorio) if diretorio else self.database.database_path.parent / "snapshots_estoque"
        pasta.mkdir(parents=True, exist_ok=True)
        instante = datetime.now()
        destino = pasta / f"estoque_{instante.strftime('%Y%m%d_%H%M%S_%f')}.json"
        payload = {
            "tipo": "SNAPSHOT_ESTOQUE",
            "criado_em": instante.isoformat(timespec="seconds"),
            "database": str(self.database.database_path),
            "produtos": produtos,
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=pasta, delete=False) as temporario:
            json.dump(payload, temporario, ensure_ascii=False, indent=2)
            temporario.flush()
            temporario_path = Path(temporario.name)
        temporario_path.replace(destino)
        return str(destino)

    def inventario_lote(
        self, contagens: Iterable[dict[str, Any]], *, motivo: str, usuario: str = "Sistema",
        diretorio_snapshot: str | Path | None = None,
    ) -> ResultadoInventario:
        motivo = str(motivo or "").strip()
        if not motivo:
            raise ValueError("Informe o motivo do inventário.")
        preparados: list[tuple[int, Decimal]] = []
        vistos: set[int] = set()
        for item in contagens:
            produto_id = int(item.get("produto_id"))
            if produto_id in vistos:
                raise ValueError(f"Produto duplicado no inventário: {produto_id}.")
            vistos.add(produto_id)
            preparados.append((produto_id, self._quantidade(item.get("contagem_fisica"), permitir_zero=True)))
        if not preparados:
            raise ValueError("Nenhuma contagem informada.")
        # Valida tudo antes de criar o snapshot e iniciar qualquer correção.
        with self.database.session() as connection:
            for produto_id, saldo_destino in preparados:
                produto = self.repository.buscar_produto(produto_id, connection)
                self._validar_produto(produto)
                if saldo_destino < 0 and not bool(produto["permite_estoque_negativo"]):
                    raise ValueError(f"O produto {produto['codigo']} não permite estoque negativo.")
        snapshot = self.criar_snapshot((produto_id for produto_id, _ in preparados), diretorio=diretorio_snapshot)
        resultados: list[ResultadoMovimentacaoEstoque] = []
        with self.database.session(write=True) as connection:
            for produto_id, saldo_destino in preparados:
                produto = self.repository.buscar_produto(produto_id, connection)
                self._validar_produto(produto)
                saldo_anterior = Decimal(str(produto["estoque_atual"])).quantize(self.CASAS)
                diferenca = (saldo_destino - saldo_anterior).quantize(self.CASAS)
                if diferenca == 0:
                    continue
                self.repository.atualizar_saldo(produto_id, float(saldo_destino), connection)
                mov_id = self.repository.registrar_movimentacao(
                    produto_id=produto_id, tipo="AJUSTE", quantidade=float(diferenca),
                    saldo_anterior=float(saldo_anterior), saldo_atual=float(saldo_destino),
                    origem="INVENTARIO", origem_id=Path(snapshot).name,
                    motivo=motivo, usuario=usuario, connection=connection,
                )
                resultados.append(ResultadoMovimentacaoEstoque(
                    produto_id, float(saldo_anterior), float(saldo_destino),
                    float(diferenca), "AJUSTE", mov_id,
                ))
        return ResultadoInventario(snapshot, tuple(resultados))

    def diagnosticar_divergencias(self) -> list[dict[str, Any]]:
        divergencias: list[dict[str, Any]] = []
        with self.database.session() as connection:
            for produto in self.repository.listar_produtos_estoque(connection):
                ultima = self.repository.ultima_movimentacao(int(produto["id"]), connection)
                if not ultima:
                    if Decimal(str(produto["estoque_atual"])) != 0:
                        divergencias.append({**produto, "tipo": "SEM_HISTORICO", "saldo_historico": None})
                    continue
                saldo_atual = Decimal(str(produto["estoque_atual"])).quantize(self.CASAS)
                saldo_historico = Decimal(str(ultima["saldo_atual"])).quantize(self.CASAS)
                if saldo_atual != saldo_historico:
                    divergencias.append({
                        **produto, "tipo": "SALDO_DIVERGENTE",
                        "saldo_historico": float(saldo_historico),
                        "movimentacao_id": int(ultima["id"]),
                    })
        return divergencias

    def reverter_movimentacao(
        self, movimentacao_id: int, *, motivo: str, usuario: str = "Sistema"
    ) -> ResultadoMovimentacaoEstoque | None:
        motivo = str(motivo or "").strip()
        if not motivo:
            raise ValueError("Informe o motivo da reversão.")
        bloqueadas = {"VENDA", "ESTORNO_VENDA", "NFE_XML", "COMPRA", "RECEBIMENTO_COMPRA"}
        with self.database.session(write=True) as connection:
            original = self.repository.buscar_movimentacao(int(movimentacao_id), connection)
            if not original:
                raise ValueError("Movimentação de estoque não encontrada.")
            if original["origem"] == "REVERSAO_ESTOQUE":
                raise ValueError("Uma reversão não pode ser revertida por este fluxo.")
            if str(original["origem"]).upper() in bloqueadas:
                raise ValueError("Movimentação vinculada deve ser revertida pelo documento de origem.")
            existente = self.repository.buscar_movimentacao_por_origem(
                "REVERSAO_ESTOQUE", str(movimentacao_id), int(original["produto_id"]), connection
            )
            if existente:
                return None
            produto = self.repository.buscar_produto(int(original["produto_id"]), connection)
            self._validar_produto(produto)
            saldo_anterior = Decimal(str(produto["estoque_atual"])).quantize(self.CASAS)
            quantidade = -Decimal(str(original["quantidade"])).quantize(self.CASAS)
            saldo_atual = (saldo_anterior + quantidade).quantize(self.CASAS)
            if saldo_atual < 0 and not bool(produto["permite_estoque_negativo"]):
                raise ValueError("A reversão produziria estoque negativo.")
            self.repository.atualizar_saldo(int(original["produto_id"]), float(saldo_atual), connection)
            mov_id = self.repository.registrar_movimentacao(
                produto_id=int(original["produto_id"]), tipo="REVERSAO", quantidade=float(quantidade),
                saldo_anterior=float(saldo_anterior), saldo_atual=float(saldo_atual),
                origem="REVERSAO_ESTOQUE", origem_id=str(movimentacao_id),
                motivo=motivo, usuario=usuario, connection=connection,
            )
        return ResultadoMovimentacaoEstoque(
            int(original["produto_id"]), float(saldo_anterior), float(saldo_atual),
            float(quantidade), "REVERSAO", mov_id,
        )

    def baixar_itens_venda(
        self,
        itens: Iterable[dict[str, Any]],
        *,
        venda_id: int,
        usuario: str = "Sistema",
    ) -> list[ResultadoMovimentacaoEstoque]:
        with self.database.session(write=True) as connection:
            return self.baixar_itens_venda_na_transacao(
                connection, itens, venda_id=venda_id, usuario=usuario
            )

    def baixar_itens_venda_na_transacao(
        self,
        connection,
        itens: Iterable[dict[str, Any]],
        *,
        venda_id: int,
        usuario: str = "Sistema",
    ) -> list[ResultadoMovimentacaoEstoque]:
        quantidades_por_produto: dict[int, Decimal] = {}
        override_por_produto: dict[int, bool] = {}
        for item in itens:
            produto_id = item.get("produto_id")
            if produto_id in (None, ""):
                continue
            produto_id = int(produto_id)
            quantidade = self._quantidade(item.get("qtd", 0))
            quantidades_por_produto[produto_id] = (
                quantidades_por_produto.get(produto_id, Decimal("0")) + quantidade
            ).quantize(self.CASAS)
            override_por_produto[produto_id] = (
                override_por_produto.get(produto_id, False)
                or bool(item.get("estoque_override", False))
            )
        resultados: list[ResultadoMovimentacaoEstoque] = []
        for produto_id, quantidade in quantidades_por_produto.items():
            existente = self.repository.buscar_movimentacao_por_origem(
                "VENDA", str(venda_id), produto_id, connection
            )
            if existente:
                continue
            produto = self.repository.buscar_produto(produto_id, connection)
            self._validar_produto(produto)
            saldo_anterior = Decimal(str(produto["estoque_atual"]))
            saldo_atual = (saldo_anterior - quantidade).quantize(self.CASAS)
            if (
                not bool(produto["permite_estoque_negativo"])
                and not override_por_produto.get(produto_id, False)
                and saldo_atual < 0
            ):
                raise ValueError(
                    f"Estoque insuficiente para {produto['codigo']} - {produto['nome']}. "
                    f"Disponível: {float(saldo_anterior):g}; solicitado: {float(quantidade):g}."
                )
            self.repository.atualizar_saldo(produto_id, float(saldo_atual), connection)
            mov_id = self.repository.registrar_movimentacao(
                produto_id=produto_id, tipo="SAIDA", quantidade=-float(quantidade),
                saldo_anterior=float(saldo_anterior), saldo_atual=float(saldo_atual),
                origem="VENDA", origem_id=str(venda_id),
                motivo=(
                    "Baixa automática da venda — saldo negativo autorizado no PDV"
                    if override_por_produto.get(produto_id, False)
                    else "Baixa automática da venda"
                ),
                usuario=usuario, connection=connection,
            )
            resultados.append(ResultadoMovimentacaoEstoque(
                produto_id, float(saldo_anterior), float(saldo_atual),
                -float(quantidade), "SAIDA", mov_id,
            ))
        return resultados

    def estornar_venda(self, venda_id: int, *, usuario: str = "Sistema") -> list[ResultadoMovimentacaoEstoque]:
        with self.database.session(write=True) as connection:
            return self.estornar_venda_na_transacao(connection, venda_id, usuario=usuario)

    def estornar_venda_na_transacao(self, connection, venda_id: int, *, usuario: str = "Sistema") -> list[ResultadoMovimentacaoEstoque]:
        resultados: list[ResultadoMovimentacaoEstoque] = []
        rows = connection.execute(
            """
            SELECT produto_id, quantidade
            FROM estoque_movimentacoes
            WHERE origem='VENDA' AND origem_id=? AND tipo='SAIDA'
            ORDER BY id
            """,
            (str(venda_id),),
        ).fetchall()
        for row in rows:
            produto_id = int(row["produto_id"])
            if self.repository.buscar_movimentacao_por_origem("ESTORNO_VENDA", str(venda_id), produto_id, connection):
                continue
            quantidade = abs(Decimal(str(row["quantidade"]))).quantize(self.CASAS)
            produto = self.repository.buscar_produto(produto_id, connection)
            self._validar_produto(produto)
            saldo_anterior = Decimal(str(produto["estoque_atual"]))
            saldo_atual = (saldo_anterior + quantidade).quantize(self.CASAS)
            self.repository.atualizar_saldo(produto_id, float(saldo_atual), connection)
            mov_id = self.repository.registrar_movimentacao(
                produto_id=produto_id, tipo="ENTRADA", quantidade=float(quantidade),
                saldo_anterior=float(saldo_anterior), saldo_atual=float(saldo_atual),
                origem="ESTORNO_VENDA", origem_id=str(venda_id), motivo="Estorno da venda",
                usuario=usuario, connection=connection,
            )
            resultados.append(ResultadoMovimentacaoEstoque(
                produto_id, float(saldo_anterior), float(saldo_atual),
                float(quantidade), "ENTRADA", mov_id,
            ))
        return resultados

    def _movimentar(
        self,
        produto_id: int,
        quantidade: float,
        *,
        entrada: bool,
        origem: str,
        origem_id: str,
        motivo: str,
        usuario: str,
    ) -> ResultadoMovimentacaoEstoque:
        qtd = self._quantidade(quantidade)
        with self.database.session(write=True) as connection:
            # A leitura e a atualização do saldo formam uma única operação
            # serializada, inclusive quando duas ações manuais concorrem.
            connection.execute("BEGIN IMMEDIATE")
            produto = self.repository.buscar_produto(int(produto_id), connection)
            self._validar_produto(produto)
            saldo_anterior = Decimal(str(produto["estoque_atual"]))
            saldo_atual = (saldo_anterior + qtd if entrada else saldo_anterior - qtd).quantize(self.CASAS)
            if not entrada and not bool(produto["permite_estoque_negativo"]) and saldo_atual < 0:
                raise ValueError("Estoque insuficiente para concluir a saída.")
            self.repository.atualizar_saldo(int(produto_id), float(saldo_atual), connection)
            tipo = "ENTRADA" if entrada else "SAIDA"
            quantidade_mov = qtd if entrada else -qtd
            mov_id = self.repository.registrar_movimentacao(
                produto_id=int(produto_id), tipo=tipo, quantidade=float(quantidade_mov),
                saldo_anterior=float(saldo_anterior), saldo_atual=float(saldo_atual),
                origem=origem, origem_id=origem_id, motivo=motivo, usuario=usuario,
                connection=connection,
            )
        return ResultadoMovimentacaoEstoque(
            int(produto_id), float(saldo_anterior), float(saldo_atual),
            float(quantidade_mov), tipo, mov_id,
        )

    @staticmethod
    def _validar_produto(produto: dict[str, Any] | None) -> None:
        if not produto:
            raise ValueError("Produto não encontrado.")
        if produto["tipo_produto"] == "SERVICO" or not bool(produto["controla_estoque"]):
            raise ValueError("Este produto não controla estoque.")
