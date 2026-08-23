from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Final


class MoneyValueError(ValueError):
    """Entrada monetária inválida ou ambígua."""


class MoneyCodec:
    """Converte e apresenta dinheiro sem passar por ``float``.

    Strings aceitas usam uma destas formas inequívocas:
    - inteiro sem separador: ``1000``;
    - decimal canônico com uma ou duas casas: ``10.5`` ou ``10.50``;
    - brasileiro com vírgula decimal: ``10,50`` ou ``1.000,00``;
    - milhares brasileiros sem centavos quando há mais de um ponto:
      ``1.000.000``.

    Uma string com um único ponto e três dígitos à direita, como ``1.000``, é
    rejeitada porque pode significar um ou mil.
    """

    CENT: Final = Decimal("0.01")
    ZERO: Final = Decimal("0.00")
    _INTEGER = re.compile(r"^[+-]?\d+$")
    _CANONICAL_DECIMAL = re.compile(r"^[+-]?\d+\.\d{1,2}$")
    _BR_DECIMAL = re.compile(r"^[+-]?(?:\d{1,3}(?:\.\d{3})*|\d+),\d{1,2}$")
    _BR_GROUPED_INTEGER = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3}){2,}$")

    @classmethod
    def parse(cls, value: Decimal | int | str, *, field: str = "valor") -> Decimal:
        if isinstance(value, bool) or isinstance(value, float):
            raise MoneyValueError(f"{field} deve ser informado sem ponto flutuante binário.")

        if isinstance(value, Decimal):
            decimal_value = value
        elif isinstance(value, int):
            decimal_value = Decimal(value)
        elif isinstance(value, str):
            text = value.strip()
            if not text or any(character.isspace() for character in text):
                raise MoneyValueError(f"{field} monetário inválido.")
            if cls._INTEGER.fullmatch(text):
                canonical = text
            elif cls._CANONICAL_DECIMAL.fullmatch(text):
                canonical = text
            elif cls._BR_DECIMAL.fullmatch(text):
                canonical = text.replace(".", "").replace(",", ".")
            elif cls._BR_GROUPED_INTEGER.fullmatch(text):
                canonical = text.replace(".", "")
            else:
                raise MoneyValueError(f"{field} monetário inválido ou ambíguo: {value!r}.")
            try:
                decimal_value = Decimal(canonical)
            except InvalidOperation as exc:
                raise MoneyValueError(f"{field} monetário inválido.") from exc
        else:
            raise MoneyValueError(f"{field} deve ser Decimal, inteiro ou texto monetário.")

        if not decimal_value.is_finite():
            raise MoneyValueError(f"{field} deve ser um decimal finito.")
        if decimal_value.as_tuple().exponent < -2:
            raise MoneyValueError(f"{field} não pode possuir mais de duas casas decimais.")
        return decimal_value.quantize(cls.CENT, rounding=ROUND_HALF_UP)

    @classmethod
    def canonical(cls, value: Decimal | int | str, *, field: str = "valor") -> str:
        return format(cls.parse(value, field=field), ".2f")

    @classmethod
    def format_br(cls, value: Decimal | int | str, *, field: str = "valor") -> str:
        canonical = cls.parse(value, field=field)
        return f"{canonical:,.2f}".translate(str.maketrans({",": ".", ".": ","}))
