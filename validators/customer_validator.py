from __future__ import annotations

from decimal import Decimal, InvalidOperation


class CustomerValidator:
    """Normalização e validação de dados de clientes, sem persistência/UI."""

    @staticmethod
    def normalize_name(value: str) -> str:
        name = " ".join(str(value or "").split())
        if not name:
            raise ValueError("O campo Nome é obrigatório!")
        return name

    @staticmethod
    def parse_record_number(value: int | str | None) -> int | None:
        text = str("" if value is None else value).strip()
        if not text:
            return None
        try:
            record_number = int(text)
        except (TypeError, ValueError) as exc:
            raise ValueError("Número da ficha ou limite inválido.") from exc
        if record_number <= 0:
            raise ValueError("Número da ficha ou limite inválido.")
        return record_number

    @staticmethod
    def parse_credit_limit(value: Decimal | float | str) -> float:
        text = str(value or "0").strip().replace("R$", "").replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", ".")
        try:
            credit_limit = Decimal(text)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Número da ficha ou limite inválido.") from exc
        if credit_limit < 0:
            raise ValueError("O limite de crédito não pode ser negativo.")
        return float(credit_limit)
