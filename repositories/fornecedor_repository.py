from __future__ import annotations

from datetime import datetime
from typing import Any

from database import DatabaseManager


class FornecedorRepository:
    """Consultas e gravações exclusivas do cadastro de fornecedores."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def listar_ativos(self) -> list[dict[str, Any]]:
        rows = self.database.fetch_all(
            "SELECT id, nome_fantasia AS nome FROM fornecedores "
            "WHERE ativo=1 ORDER BY nome_fantasia COLLATE NOCASE"
        )
        return [dict(row) for row in rows]

    def criar(self, nome: str, *, connection=None, **extras: Any) -> int:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = """INSERT INTO fornecedores
               (razao_social,nome_fantasia,cnpj,telefone,email,ativo,criado_em,atualizado_em)
               VALUES(?,?,?,?,?,1,?,?)"""
        parameters = (
            extras.get("razao_social") or nome,
            nome,
            extras.get("cnpj", ""),
            extras.get("telefone", ""),
            extras.get("email", ""),
            agora,
            agora,
        )
        if connection is None:
            return int(self.database.execute(sql, parameters))
        cursor = connection.execute(sql, parameters)
        return int(cursor.lastrowid)
