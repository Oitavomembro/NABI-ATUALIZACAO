from __future__ import annotations


class NFeImportValidator:
    VALID_ACTIONS = frozenset({"VINCULAR", "ATUALIZAR", "CRIAR"})

    @classmethod
    def decision(cls, action: str, product_id: int | None) -> str:
        normalized = str(action or "").strip().upper()
        if normalized not in cls.VALID_ACTIONS:
            raise ValueError("Escolha Vincular, Atualizar ou Criar para o item.")
        if normalized in {"VINCULAR", "ATUALIZAR"} and not product_id:
            raise ValueError("Selecione o produto cadastrado para vincular ou atualizar.")
        if normalized == "CRIAR" and product_id is not None:
            raise ValueError("A ação Criar não pode manter vínculo com produto existente.")
        return normalized

    @staticmethod
    def complete_items(items_count: int, document_items_count: int) -> None:
        if items_count <= 0 or items_count != document_items_count:
            raise ValueError("Todos os itens da NF-e devem estar preparados para a importação.")
