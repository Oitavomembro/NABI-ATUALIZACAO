from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Callable

from repositories.emitted_document_repository import EmittedDocument, EmittedDocumentRepository


class EmittedDocumentService:
    """Persiste e localiza PDFs emitidos sem esconder falhas de banco."""

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection],
        *,
        logger: logging.Logger | None = None,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._connection_factory = connection_factory
        self._repository = EmittedDocumentRepository(connection_factory)
        self._logger = logger or logging.getLogger("NabiCode.EmittedDocuments")
        self._clock = clock

    def register(
        self,
        movement_id: int,
        category: str,
        pdf_path: str | os.PathLike[str],
        document_number: str = "",
    ) -> int:
        movement_id = int(movement_id)
        if movement_id <= 0:
            raise ValueError("O ID da movimentação deve ser maior que zero.")
        category = str(category or "").strip().upper()
        if not category:
            raise ValueError("A categoria do documento é obrigatória.")
        normalized_path = str(Path(pdf_path).expanduser().resolve())
        if not normalized_path:
            raise ValueError("O caminho do PDF é obrigatório.")

        try:
            return self._repository.register(
                movement_id,
                category,
                normalized_path,
                str(document_number or "").strip(),
                self._clock().strftime("%d/%m/%Y %H:%M:%S"),
            )
        except Exception:
            self._logger.exception(
                "Falha ao registrar documento emitido para movimentação %s", movement_id
            )
            raise

    def latest(self, movement_id: int) -> EmittedDocument | None:
        movement_id = int(movement_id)
        if movement_id <= 0:
            raise ValueError("O ID da movimentação deve ser maior que zero.")
        return self._repository.latest(movement_id)

    def latest_existing_file(self, movement_id: int) -> EmittedDocument | None:
        document = self.latest(movement_id)
        if document is None or not Path(document.pdf_path).is_file():
            return None
        return document
