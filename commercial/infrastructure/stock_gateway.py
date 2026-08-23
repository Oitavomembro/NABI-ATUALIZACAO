from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from commercial.application.product_dto import (
    LowStockProductSummary, PersistedStockAction, ProductCreateCommand,
    ProductDetails, ProductStockSummary, ProductUpdateCommand,
    StockAdjustmentCommand, StockMovementCommand, StockMovementSummary,
)


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


class NabiCodeProductStockGateway:
    """Adapta ProdutoService/EstoqueService; toda mutação fica no backend."""

    def __init__(self, product_service, stock_service) -> None:
        self.products = product_service
        self.stock_service = stock_service
        self.stock_repository = stock_service.repository

    @staticmethod
    def _details(row) -> ProductDetails:
        return ProductDetails(
            int(row["id"]), str(row.get("codigo") or ""),
            str(row.get("codigo_barras") or ""), str(row.get("nome") or ""),
            row.get("preco_venda") or Decimal("0"), row.get("preco_custo") or Decimal("0"),
            _decimal(row.get("estoque_atual")), _decimal(row.get("estoque_minimo")),
            bool(row.get("permite_estoque_negativo")), str(row.get("tipo_produto") or ""),
            bool(row.get("ativo", True)),
        )

    def get_details(self, product_id: int) -> ProductDetails | None:
        row = self.products.buscar(int(product_id)) if int(product_id) > 0 else None
        return self._details(row) if row else None

    def search_details(self, term: str, *, limit: int = 30) -> tuple[ProductDetails, ...]:
        safe_limit = max(1, min(int(limit), 200))
        return tuple(self._details(row) for row in self.products.listar(str(term or ""))[:safe_limit])

    def get_by_barcode(self, barcode: str) -> ProductDetails | None:
        normalized = str(barcode or "").strip()
        if not normalized:
            return None
        matches = [
            row for row in self.products.listar(normalized)
            if str(row.get("codigo_barras") or "").strip() == normalized
        ]
        if len(matches) > 1:
            raise ValueError("Código de barras duplicado no catálogo; corrija a integridade dos produtos.")
        return self._details(matches[0]) if matches else None

    @staticmethod
    def _save_kwargs(command, current=None):
        current = current or {}
        return dict(
            codigo=command.code, nome=command.description, preco_venda=command.sale_price,
            categoria_id=command.category_id, tipo_produto=command.product_type,
            marca_id=current.get("marca_id"), fornecedor_id=current.get("fornecedor_id"),
            unidade_id=current.get("unidade_id"), unidade_compra_id=current.get("unidade_compra_id"),
            fator_conversao=current.get("fator_conversao", Decimal("1")),
            preco_custo=command.cost_price,
            despesas_percentual=current.get("despesas_percentual", Decimal("0")),
            margem_lucro=current.get("margem_lucro", Decimal("0")),
            codigo_barras=command.barcode, ncm=current.get("ncm", ""),
            cest=current.get("cest", ""), cfop=current.get("cfop", ""),
            fiscal_origin=current.get("fiscal_origin", ""),
            fiscal_csosn=current.get("fiscal_csosn", ""),
            fiscal_icms_cst=current.get("fiscal_icms_cst", ""),
            fiscal_icms_rate=current.get("fiscal_icms_rate", "0"),
            fiscal_pis_cst=current.get("fiscal_pis_cst", ""),
            fiscal_pis_rate=current.get("fiscal_pis_rate", "0"),
            fiscal_cofins_cst=current.get("fiscal_cofins_cst", ""),
            fiscal_cofins_rate=current.get("fiscal_cofins_rate", "0"),
            fiscal_ipi_cst=current.get("fiscal_ipi_cst", ""),
            fiscal_ipi_rate=current.get("fiscal_ipi_rate", "0"),
            fiscal_ipi_enq=current.get("fiscal_ipi_enq", ""),
            fiscal_profile_source=current.get("fiscal_profile_source", ""),
            ibs_cbs_cst=current.get("ibs_cbs_cst", ""),
            ibs_cbs_class=current.get("ibs_cbs_class", ""),
            ibs_uf_rate=current.get("ibs_uf_rate", "0"),
            ibs_city_rate=current.get("ibs_city_rate", "0"), cbs_rate=current.get("cbs_rate", "0"),
            estoque_atual=command.current_stock, estoque_minimo=command.minimum_stock,
            permite_estoque_negativo=command.allow_negative_stock,
        )

    def create(self, command: ProductCreateCommand) -> ProductDetails:
        product_id = self.products.salvar(**self._save_kwargs(command))
        return self.get_details(product_id)

    def update(self, command: ProductUpdateCommand) -> ProductDetails:
        current = self.products.buscar(command.product_id)
        if current is None:
            raise ValueError("Produto não encontrado.")
        kwargs = self._save_kwargs(command, current)
        kwargs["produto_id"] = command.product_id
        self.products.salvar(**kwargs)
        return self.get_details(command.product_id)

    def stock(self, product_id: int) -> ProductStockSummary:
        row = self.stock_repository.buscar_produto(int(product_id))
        if not row:
            raise ValueError("Produto não encontrado.")
        if not bool(row["controla_estoque"]) or str(row["tipo_produto"]).upper() == "SERVICO":
            raise ValueError("O produto não controla estoque.")
        current = _decimal(row["estoque_atual"])
        minimum = _decimal(row["estoque_minimo"])
        allow_negative = bool(row["permite_estoque_negativo"])
        status = "NEGATIVO" if current < 0 else "ZERADO" if current == 0 else "BAIXO" if current <= minimum else "OK"
        return ProductStockSummary(int(product_id), current, minimum, current > 0 or allow_negative, status, allow_negative)

    def movements(self, product_id: int, *, limit: int = 200) -> tuple[StockMovementSummary, ...]:
        if not self.stock_repository.buscar_produto(int(product_id)):
            raise ValueError("Produto não encontrado.")
        return tuple(StockMovementSummary(
            int(row["id"]), int(row["produto_id"]), datetime.fromisoformat(str(row["data"])),
            str(row["tipo"]), _decimal(row["quantidade"]), _decimal(row["saldo_anterior"]),
            _decimal(row["saldo_atual"]), str(row.get("origem") or ""),
            str(row.get("origem_id") or ""), str(row.get("motivo") or ""),
            str(row.get("usuario") or ""),
        ) for row in self.stock_repository.listar_movimentacoes(product_id, limit))

    def low_stock(self) -> tuple[LowStockProductSummary, ...]:
        return tuple(LowStockProductSummary(
            int(row["id"]), str(row.get("codigo") or ""), str(row.get("nome") or ""),
            _decimal(row["estoque_atual"]), _decimal(row["estoque_minimo"]),
        ) for row in self.stock_repository.listar_abaixo_minimo())

    @staticmethod
    def _persisted(result) -> PersistedStockAction:
        return PersistedStockAction(
            result.movimentacao_id, result.produto_id, result.tipo,
            _decimal(result.quantidade), _decimal(result.saldo_anterior), _decimal(result.saldo_atual),
        )

    def receive(self, command: StockMovementCommand, *, user: str) -> PersistedStockAction:
        return self._persisted(self.stock_service.entrada(
            command.product_id, command.amount, origem="AJUSTE_MANUAL",
            origem_id=command.reference, motivo=command.reason, usuario=user,
        ))

    def remove(self, command: StockMovementCommand, *, user: str) -> PersistedStockAction:
        return self._persisted(self.stock_service.saida(
            command.product_id, command.amount, origem="AJUSTE_MANUAL",
            origem_id=command.reference, motivo=command.reason, usuario=user,
        ))

    def adjust(self, command: StockAdjustmentCommand, *, user: str) -> PersistedStockAction:
        return self._persisted(self.stock_service.ajustar(
            command.product_id, command.new_balance, motivo=command.reason, usuario=user,
        ))
