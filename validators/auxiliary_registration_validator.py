from __future__ import annotations


class AuxiliaryRegistrationValidator:
    VALID_TYPES = frozenset({"marca", "fornecedor", "unidade"})

    @classmethod
    def normalize_type(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in cls.VALID_TYPES:
            raise ValueError("Tipo de cadastro auxiliar inválido.")
        return normalized

    @staticmethod
    def normalize_name(value: str, *, unit: bool = False) -> str:
        name = " ".join(str(value or "").split())
        if not name:
            raise ValueError("Informe o nome ou a sigla.")
        if unit:
            name = name.upper()
            if len(name) > 8:
                raise ValueError("A sigla da unidade deve possuir no máximo 8 caracteres.")
        return name
