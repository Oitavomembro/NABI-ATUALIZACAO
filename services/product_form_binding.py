from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .product_application_service import ProductFormState


@dataclass(frozen=True)
class ProductFormControls:
    codigo: Any
    nome: Any
    preco_venda: Any
    categoria: Any
    tipo_produto: Any
    marca: Any
    fornecedor: Any
    unidade: Any
    unidade_compra: Any
    fator_conversao: Any
    preco_custo: Any
    despesas_percentual: Any
    margem_lucro: Any
    codigo_barras: Any
    estoque_atual: Any
    estoque_minimo: Any
    permite_estoque_negativo: Any


class ProductFormBinding:
    """Fronteira de formulário baseada em duck typing, sem dependência de Tkinter."""

    def __init__(self, controls: ProductFormControls) -> None:
        self.controls = controls

    @staticmethod
    def _read(control: Any) -> Any:
        return control.get()

    @staticmethod
    def _write_text(control: Any, value: Any) -> None:
        try:
            control.configure(state="normal")
        except (AttributeError, TypeError):
            pass
        control.delete(0, "end")
        control.insert(0, str(value))

    @staticmethod
    def _write_choice(control: Any, value: Any) -> None:
        control.set(str(value))

    def capture(self) -> ProductFormState:
        c = self.controls
        return ProductFormState(
            codigo=str(self._read(c.codigo)),
            nome=str(self._read(c.nome)),
            preco_venda=str(self._read(c.preco_venda)),
            categoria=str(self._read(c.categoria)),
            tipo_produto=str(self._read(c.tipo_produto)),
            marca=str(self._read(c.marca)),
            fornecedor=str(self._read(c.fornecedor)),
            unidade=str(self._read(c.unidade)),
            unidade_compra=str(self._read(c.unidade_compra)),
            fator_conversao=str(self._read(c.fator_conversao)),
            preco_custo=str(self._read(c.preco_custo)),
            despesas_percentual=str(self._read(c.despesas_percentual)),
            margem_lucro=str(self._read(c.margem_lucro)),
            codigo_barras=str(self._read(c.codigo_barras)),
            estoque_atual=str(self._read(c.estoque_atual)),
            estoque_minimo=str(self._read(c.estoque_minimo)),
            permite_estoque_negativo=bool(self._read(c.permite_estoque_negativo)),
        )

    def apply(self, state: ProductFormState, *, codigo_editavel: bool) -> None:
        c = self.controls
        text_values = (
            (c.codigo, state.codigo),
            (c.nome, state.nome),
            (c.preco_custo, state.preco_custo),
            (c.despesas_percentual, state.despesas_percentual),
            (c.margem_lucro, state.margem_lucro),
            (c.preco_venda, state.preco_venda),
            (c.fator_conversao, state.fator_conversao),
            (c.estoque_atual, state.estoque_atual),
            (c.estoque_minimo, state.estoque_minimo),
            (c.codigo_barras, state.codigo_barras),
        )
        for control, value in text_values:
            self._write_text(control, value)

        for control, value in (
            (c.tipo_produto, state.tipo_produto),
            (c.categoria, state.categoria),
            (c.marca, state.marca),
            (c.fornecedor, state.fornecedor),
            (c.unidade, state.unidade),
            (c.unidade_compra, state.unidade_compra),
        ):
            self._write_choice(control, value)

        c.permite_estoque_negativo.set(bool(state.permite_estoque_negativo))
        try:
            c.codigo.configure(state="normal" if codigo_editavel else "disabled")
        except (AttributeError, TypeError):
            pass
