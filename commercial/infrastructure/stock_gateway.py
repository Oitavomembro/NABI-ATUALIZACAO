from __future__ import annotations

from datetime import datetime
import json
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

    def _limited_rows(self, term: str, limit: int):
        try:
            return self.products.listar(term, limit=limit)
        except TypeError as exc:
            if "unexpected keyword argument 'limit'" not in str(exc):
                raise
            return self.products.listar(term)[:limit]

    @staticmethod
    def _details(row) -> ProductDetails:
        return ProductDetails(
            int(row["id"]), str(row.get("codigo") or ""),
            str(row.get("codigo_barras") or ""), str(row.get("nome") or ""),
            row.get("preco_venda") or Decimal("0"), row.get("preco_custo") or Decimal("0"),
            _decimal(row.get("estoque_atual")), _decimal(row.get("estoque_minimo")),
            bool(row.get("permite_estoque_negativo")), str(row.get("tipo_produto") or ""),
            bool(row.get("ativo", True)), str(row.get("unidade") or "UN"),
            tuple(row.get("codigos_barras") or ()), bool(row.get("permite_fracionado", False)),
        )

    def get_details(self, product_id: int) -> ProductDetails | None:
        row = self.products.buscar(int(product_id)) if int(product_id) > 0 else None
        return self._details(row) if row else None

    def search_details(self, term: str, *, limit: int = 30) -> tuple[ProductDetails, ...]:
        safe_limit = max(1, min(int(limit), 200))
        return tuple(
            self._details(row)
            for row in self._limited_rows(str(term or ""), safe_limit)
        )

    def get_by_barcode(self, barcode: str) -> ProductDetails | None:
        normalized = str(barcode or "").strip()
        if not normalized:
            return None
        repository = getattr(self.products, "produtos", None)
        if repository is not None and hasattr(repository, "buscar_por_codigo_barras"):
            matches = repository.buscar_por_codigo_barras(normalized)
        else:
            matches = [
                row for row in self._limited_rows(normalized, 200)
                if normalized.casefold() in {
                    str(row.get("codigo_barras") or "").strip().casefold(),
                    *(str(code).strip().casefold() for code in row.get("codigos_barras", ())),
                }
            ]
        if len(matches) > 1:
            raise ValueError("Código de barras duplicado no catálogo; corrija a integridade dos produtos.")
        return self._details(matches[0]) if matches else None

    def list_units(self) -> tuple[dict, ...]:
        return tuple(self.products.listar_auxiliares("unidade"))

    def _unit_id(self, unit_code: str) -> int | None:
        normalized = str(unit_code or "").strip().casefold()
        if not normalized:
            return None
        matches = [
            item for item in self.products.listar_auxiliares("unidade")
            if str(item.get("nome") or item.get("sigla") or "").strip().casefold() == normalized
        ]
        if not matches:
            alias = self.products.produtos.database.fetch_one(
                """SELECT u.id,u.sigla AS nome,u.sigla,u.descricao,u.permite_fracionado
                   FROM unidade_fornecedor_aliases a JOIN unidades_medida u ON u.id=a.unidade_id
                   WHERE a.alias=? COLLATE NOCASE AND u.ativo=1""", (str(unit_code).strip(),),
            )
            matches = [dict(alias)] if alias else []
        if len(matches) > 1:
            raise ValueError("A unidade do XML corresponde a mais de um cadastro auxiliar.")
        return int(matches[0]["id"]) if matches else None

    def _save_kwargs(self, command, current=None):
        current = current or {}
        creating = not current
        unit_id = current.get("unidade_id") if current else self._unit_id(
            getattr(command, "unit_code", "")
        )
        return dict(
            codigo=command.code, nome=command.description, preco_venda=command.sale_price,
            categoria_id=command.category_id, tipo_produto=command.product_type,
            marca_id=current.get("marca_id"), fornecedor_id=current.get("fornecedor_id"),
            unidade_id=unit_id,
            unidade_compra_id=(current.get("unidade_compra_id") if current else unit_id),
            fator_conversao=current.get("fator_conversao", Decimal("1")),
            preco_custo=command.cost_price,
            despesas_percentual=current.get("despesas_percentual", Decimal("0")),
            margem_lucro=current.get("margem_lucro", Decimal("0")),
            codigo_barras=command.barcode,
            codigos_barras=tuple(getattr(command, "barcodes", ()) or ()),
            permite_fracionado=getattr(command, "allow_fractional_quantity", None),
            ncm=(getattr(command, "ncm", "") if creating else current.get("ncm", "")),
            cest=(getattr(command, "cest", "") if creating else current.get("cest", "")),
            cfop=current.get("cfop", ""),
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

    def create_products_from_xml(
        self, commands: tuple[ProductCreateCommand, ...], *, actor: str,
        source_sha256: str, draft_fingerprint: str,
        resolved_existing_ids: tuple[int, ...] = (),
        skipped_source_items: tuple[int, ...] = (),
    ) -> tuple[ProductDetails, ...]:
        actor = str(actor or "").strip()
        if not actor:
            raise PermissionError("A sessão autenticada não possui identidade válida.")
        if not all(command.current_stock == 0 for command in commands):
            raise ValueError("Cadastro preparado por XML deve iniciar sem movimentar estoque.")
        created_ids: list[int] = []
        occurred_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with self.products.produtos.transaction() as connection:
            for command in commands:
                created_ids.append(int(self.products.salvar(
                    **self._save_kwargs(command), connection=connection,
                )))
            details = json.dumps(
                {
                    "source_sha256": str(source_sha256),
                    "draft_fingerprint": str(draft_fingerprint),
                    "created_product_ids": created_ids,
                    "resolved_existing_ids": [int(value) for value in resolved_existing_ids],
                    "skipped_source_items": [int(value) for value in skipped_source_items],
                    "stock_moved": False,
                    "financial_created": False,
                    "fiscal_authorization_imported": False,
                },
                ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            )
            connection.execute(
                """INSERT INTO auditoria
                   (data,usuario,modulo,acao,objeto,detalhes,resultado)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    occurred_at, actor, "PRODUTOS", "CADASTRAR_POR_XML",
                    str(draft_fingerprint), details, "SUCESSO",
                ),
            )
        return tuple(self.get_details(product_id) for product_id in created_ids)

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
