from __future__ import annotations


class MovementValidator:
    @staticmethod
    def movement_id(value: int) -> int:
        movement_id = int(value)
        if movement_id <= 0:
            raise ValueError("O ID da movimentação deve ser maior que zero.")
        return movement_id

    @staticmethod
    def update_values(description: str, value: float) -> tuple[str, float]:
        normalized_description = str(description or "").strip()
        if not normalized_description:
            raise ValueError("A descrição da movimentação é obrigatória.")
        normalized_value = float(value)
        if normalized_value < 0:
            raise ValueError("O valor da movimentação não pode ser negativo.")
        return normalized_description, normalized_value
