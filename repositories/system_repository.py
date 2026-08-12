"""Persistência compartilhada de configurações e histórico de clientes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional
import sqlite3


ConnectionFactory = Callable[[], sqlite3.Connection]


@dataclass(frozen=True)
class ClientHistoryEntry:
    client_id: int
    event: str
    details: str
    created_at: str


class SystemRepository:
    """Agrupa operações globais simples que antes ficavam no módulo de interface."""

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def get_config(self, key: str, default: str = "") -> str:
        normalized = str(key or "").strip()
        if not normalized:
            raise ValueError("A chave da configuração é obrigatória.")
        conn = self._connection_factory()
        try:
            row = conn.execute("SELECT valor FROM configuracoes WHERE chave = ?", (normalized,)).fetchone()
            return str(row[0]) if row and row[0] is not None else default
        finally:
            conn.close()

    def set_config(self, key: str, value: object) -> None:
        normalized = str(key or "").strip()
        if not normalized:
            raise ValueError("A chave da configuração é obrigatória.")
        conn = self._connection_factory()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)",
                (normalized, "" if value is None else str(value)),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def add_client_history(
        self,
        client_id: int,
        event: str,
        details: str = "",
        *,
        created_at: Optional[str] = None,
    ) -> ClientHistoryEntry:
        client_id = int(client_id)
        if client_id <= 0:
            raise ValueError("O cliente do histórico é obrigatório.")
        normalized_event = str(event or "").strip()
        if not normalized_event:
            raise ValueError("O evento do histórico é obrigatório.")
        timestamp = created_at or datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        entry = ClientHistoryEntry(client_id, normalized_event, str(details or ""), timestamp)
        conn = self._connection_factory()
        try:
            conn.execute(
                "INSERT INTO historico_clientes (cliente_id, evento, detalhes, data) VALUES (?, ?, ?, ?)",
                (entry.client_id, entry.event, entry.details, entry.created_at),
            )
            conn.commit()
            return entry
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
