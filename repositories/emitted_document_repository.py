from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class EmittedDocument:
    id: int
    movement_id: int
    category: str
    pdf_path: str
    document_number: str
    issued_at: str


class EmittedDocumentRepository:
    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]) -> None:
        self._connection_factory = connection_factory

    def register(
        self,
        movement_id: int,
        category: str,
        pdf_path: str,
        document_number: str,
        issued_at: str,
    ) -> int:
        connection = self._connection_factory()
        try:
            cursor = connection.execute(
                """INSERT INTO documentos_emitidos(
                       movimentacao_id, categoria, caminho_pdf, numero_documento, data_emissao
                   ) VALUES (?, ?, ?, ?, ?)""",
                (movement_id, category, pdf_path, document_number, issued_at),
            )
            connection.commit()
            return int(cursor.lastrowid)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def latest(self, movement_id: int) -> EmittedDocument | None:
        connection = self._connection_factory()
        try:
            row = connection.execute(
                """SELECT id, movimentacao_id, categoria, caminho_pdf,
                          COALESCE(numero_documento, ''), COALESCE(data_emissao, '')
                   FROM documentos_emitidos
                   WHERE movimentacao_id = ?
                   ORDER BY id DESC
                   LIMIT 1""",
                (movement_id,),
            ).fetchone()
            if row is None:
                return None
            return EmittedDocument(
                id=int(row[0]),
                movement_id=int(row[1]),
                category=str(row[2]),
                pdf_path=str(row[3]),
                document_number=str(row[4]),
                issued_at=str(row[5]),
            )
        finally:
            connection.close()
