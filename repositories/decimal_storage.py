from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
from typing import Any


class DecimalStorageError(ValueError):
    """Valor decimal inválido recebido na fronteira de persistência."""


class DecimalStorage:
    """Serialização canônica para colunas TEXT e compatibilidade com colunas REAL."""

    @staticmethod
    def to_decimal(value: Any, *, field: str = "valor") -> Decimal:
        try:
            result = value if isinstance(value, Decimal) else Decimal(str(value if value is not None else 0))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise DecimalStorageError(f"{field} contém um decimal inválido: {value!r}.") from exc
        if not result.is_finite():
            raise DecimalStorageError(f"{field} deve ser um número decimal finito.")
        return result

    @classmethod
    def canonical(cls, value: Any, *, field: str = "valor") -> str:
        decimal_value = cls.to_decimal(value, field=field)
        text = format(decimal_value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"

    @classmethod
    def legacy_real(cls, value: Any, *, field: str = "valor") -> float:
        """Representação legada aproximada; a coluna TEXT é a fonte canônica."""
        decimal_value = cls.to_decimal(value, field=field)
        try:
            result = float(decimal_value)
        except (OverflowError, ValueError) as exc:
            raise DecimalStorageError(f"{field} excede o limite da representação legada REAL.") from exc
        if not math.isfinite(result):
            raise DecimalStorageError(f"{field} excede o limite da representação legada REAL.")
        return result

    @classmethod
    def read(cls, canonical_value: Any, legacy_value: Any = 0, *, field: str = "valor") -> Decimal:
        """Lê a fonte canônica e usa a legada apenas se a canônica estiver vazia ou inválida."""
        if canonical_value is not None and str(canonical_value).strip():
            try:
                return cls.to_decimal(str(canonical_value).strip(), field=field)
            except DecimalStorageError:
                pass
        return cls.to_decimal(legacy_value, field=field)

    @classmethod
    def pair(cls, value: Any, *, field: str = "valor") -> tuple[float, str]:
        return cls.legacy_real(value, field=field), cls.canonical(value, field=field)
