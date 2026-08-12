from __future__ import annotations

from datetime import datetime
from typing import Any

from database import DatabaseManager
from repositories.fornecedor_repository import FornecedorRepository


class CadastroAuxiliarRepository:
    """CRUD comum para marcas, fornecedores e unidades.

    Os nomes das tabelas e campos são internos e validados por listas fixas para
    evitar SQL dinâmico arbitrário.
    """

    _CONFIG = {
        "marca": ("marcas_produtos", "nome"),
        "unidade": ("unidades_medida", "sigla"),
    }

    def __init__(self, database: DatabaseManager, fornecedores: FornecedorRepository | None = None) -> None:
        self.database = database
        self.fornecedores = fornecedores or FornecedorRepository(database)

    def listar_ativos(self, tipo: str) -> list[dict[str, Any]]:
        if str(tipo or "").strip().lower() == "fornecedor":
            return self.fornecedores.listar_ativos()
        tabela, campo = self._resolver(tipo)
        rows = self.database.fetch_all(
            f"SELECT id, {campo} AS nome FROM {tabela} WHERE ativo=1 ORDER BY {campo} COLLATE NOCASE"
        )
        return [dict(row) for row in rows]

    def criar(self, tipo: str, nome: str, **extras: Any) -> int:
        tipo_normalizado = str(tipo or "").strip().lower()
        if tipo_normalizado == "fornecedor":
            return self.fornecedores.criar(nome, **extras)
        tabela, campo = self._resolver(tipo_normalizado)
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if tipo_normalizado == "unidade":
            return self.database.execute(
                """INSERT INTO unidades_medida
                   (sigla,descricao,permite_fracionado,ativo,criado_em,atualizado_em)
                   VALUES(?,?,?,1,?,?)""",
                (
                    nome.upper(),
                    extras.get("descricao", ""),
                    int(bool(extras.get("permite_fracionado", False))),
                    agora,
                    agora,
                ),
            )
        return self.database.execute(
            f"INSERT INTO {tabela}({campo},ativo,criado_em,atualizado_em) VALUES(?,1,?,?)",
            (nome, agora, agora),
        )

    @classmethod
    def _resolver(cls, tipo: str) -> tuple[str, str]:
        chave = str(tipo or "").strip().lower()
        if chave not in cls._CONFIG:
            raise ValueError("Tipo de cadastro auxiliar inválido.")
        return cls._CONFIG[chave]
