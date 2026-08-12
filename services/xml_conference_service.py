from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

MONEY = Decimal("0.01")
PERCENT = Decimal("0.01")
QUANTITY = Decimal("0.0001")


@dataclass(frozen=True)
class XMLPricingResult:
    custo: Decimal
    margem_percentual: Decimal
    preco_venda: Decimal
    lucro_unitario: Decimal
    markup_percentual: Decimal

    def as_dict(self) -> dict[str, float]:
        return {
            "custo": float(self.custo),
            "margem_percentual": float(self.margem_percentual),
            "preco_venda": float(self.preco_venda),
            "lucro_unitario": float(self.lucro_unitario),
            "markup_percentual": float(self.markup_percentual),
        }


class XMLConferenceService:
    """Regras puras da conferência do XML.

    A porcentagem usada é acréscimo/markup sobre o custo unitário de estoque,
    coerente com o cadastro atual de produtos do NabiCode.
    """

    @staticmethod
    def _decimal(value: Any, field: str) -> Decimal:
        text = str(value if value is not None else "").strip().replace(".", "").replace(",", ".")
        # Se não havia vírgula e havia apenas um ponto decimal, a remoção acima seria incorreta.
        raw = str(value if value is not None else "").strip()
        if "," not in raw and raw.count(".") <= 1:
            text = raw or "0"
        try:
            return Decimal(text or "0")
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(f"{field} inválido.") from exc

    @classmethod
    def por_margem(cls, custo: Any, margem_percentual: Any) -> XMLPricingResult:
        custo_d = cls._decimal(custo, "Custo").quantize(MONEY, rounding=ROUND_HALF_UP)
        margem_d = cls._decimal(margem_percentual, "Margem").quantize(PERCENT, rounding=ROUND_HALF_UP)
        if custo_d < 0:
            raise ValueError("O custo não pode ser negativo.")
        if margem_d < -100:
            raise ValueError("A margem não pode ser menor que -100%.")
        preco = (custo_d * (Decimal("1") + margem_d / Decimal("100"))).quantize(MONEY, rounding=ROUND_HALF_UP)
        lucro = (preco - custo_d).quantize(MONEY, rounding=ROUND_HALF_UP)
        markup = Decimal("0") if custo_d == 0 else (lucro / custo_d * Decimal("100")).quantize(PERCENT, rounding=ROUND_HALF_UP)
        return XMLPricingResult(custo_d, margem_d, preco, lucro, markup)

    @classmethod
    def por_preco(cls, custo: Any, preco_venda: Any) -> XMLPricingResult:
        custo_d = cls._decimal(custo, "Custo").quantize(MONEY, rounding=ROUND_HALF_UP)
        preco_d = cls._decimal(preco_venda, "Preço de venda").quantize(MONEY, rounding=ROUND_HALF_UP)
        if custo_d < 0 or preco_d < 0:
            raise ValueError("Custo e preço não podem ser negativos.")
        lucro = (preco_d - custo_d).quantize(MONEY, rounding=ROUND_HALF_UP)
        margem = Decimal("0") if custo_d == 0 else (lucro / custo_d * Decimal("100")).quantize(PERCENT, rounding=ROUND_HALF_UP)
        return XMLPricingResult(custo_d, margem, preco_d, lucro, margem)


    @classmethod
    def parse_clipboard_rows(cls, text: str) -> list[dict[str, Any]]:
        """Converte linhas copiadas do Excel em configurações de conferência.

        Colunas aceitas, nesta ordem: quantidade, fator, unidade, custo, margem, preço.
        Linhas vazias são ignoradas. A primeira linha pode ser um cabeçalho.
        """
        rows: list[dict[str, Any]] = []
        raw_lines = [line for line in str(text or "").splitlines() if line.strip()]
        for line_number, line in enumerate(raw_lines, start=1):
            cells = [cell.strip() for cell in line.split("\t")]
            if len(cells) == 1 and ";" in line:
                cells = [cell.strip() for cell in line.split(";")]
            if line_number == 1 and cells and any(
                token in " ".join(cells).casefold()
                for token in ("quantidade", "qtd", "fator", "unidade", "custo", "margem", "preço", "preco")
            ):
                continue
            if len(cells) < 4:
                raise ValueError(
                    f"Linha {line_number}: informe ao menos quantidade, fator, unidade e custo."
                )
            while len(cells) < 6:
                cells.append("")
            quantidade = cls._decimal(cells[0], f"Linha {line_number} - quantidade")
            fator = cls._decimal(cells[1], f"Linha {line_number} - fator")
            unidade = cells[2].strip().upper()
            custo = cls._decimal(cells[3], f"Linha {line_number} - custo")
            margem_text = cells[4]
            preco_text = cells[5]
            if quantidade <= 0:
                raise ValueError(f"Linha {line_number}: quantidade deve ser maior que zero.")
            if fator <= 0:
                raise ValueError(f"Linha {line_number}: fator deve ser maior que zero.")
            if not unidade:
                raise ValueError(f"Linha {line_number}: unidade não informada.")
            if custo < 0:
                raise ValueError(f"Linha {line_number}: custo não pode ser negativo.")
            if preco_text:
                pricing = cls.por_preco(custo, preco_text)
            elif margem_text:
                pricing = cls.por_margem(custo, margem_text)
            else:
                raise ValueError(f"Linha {line_number}: informe margem ou preço de venda.")
            rows.append({
                "quantidade": float(quantidade),
                "fator": float(fator),
                "unidade": unidade,
                "custo": float(pricing.custo),
                "margem": float(pricing.margem_percentual),
                "preco": float(pricing.preco_venda),
            })
        if not rows:
            raise ValueError("A área de transferência não contém linhas válidas.")
        return rows

    @classmethod
    def validar_item(cls, config: Mapping[str, Any], *, exigir_preco: bool = True) -> list[str]:
        errors: list[str] = []
        try:
            quantidade = cls._decimal(config.get("quantidade", 0), "Quantidade").quantize(QUANTITY)
            if quantidade <= 0:
                errors.append("quantidade deve ser maior que zero")
        except ValueError as exc:
            errors.append(str(exc))
        try:
            fator = cls._decimal(config.get("fator", 0), "Fator").quantize(QUANTITY)
            if fator <= 0:
                errors.append("fator deve ser maior que zero")
        except ValueError as exc:
            errors.append(str(exc))
        if not str(config.get("unidade") or "").strip():
            errors.append("unidade de estoque não informada")
        try:
            custo = cls._decimal(config.get("custo", 0), "Custo")
            if custo < 0:
                errors.append("custo não pode ser negativo")
        except ValueError as exc:
            errors.append(str(exc))
        if exigir_preco:
            try:
                preco = cls._decimal(config.get("preco", 0), "Preço de venda")
                if preco <= 0:
                    errors.append("preço de venda deve ser maior que zero")
            except ValueError as exc:
                errors.append(str(exc))
        return errors

    @classmethod
    def validar_todos(cls, configs: Mapping[int, Mapping[str, Any]], *, exigir_preco: bool = True) -> dict[int, list[str]]:
        return {
            int(index): errors
            for index, config in configs.items()
            if (errors := cls.validar_item(config, exigir_preco=exigir_preco))
        }
