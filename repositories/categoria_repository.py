from __future__ import annotations

from datetime import datetime

from database import DatabaseManager


class CategoriaRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def listar_ativas(self) -> list[dict]:
        rows = self.database.fetch_all(
            "SELECT id, nome FROM categorias_produtos WHERE ativo=1 ORDER BY nome COLLATE NOCASE"
        )
        return [dict(row) for row in rows]

    def criar(self, nome: str) -> int:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.database.execute(
            "INSERT INTO categorias_produtos(nome,ativo,criado_em,atualizado_em) VALUES(?,1,?,?)",
            (nome, agora, agora),
        )
