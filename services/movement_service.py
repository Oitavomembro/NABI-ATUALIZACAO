from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from validators import MovementValidator


ConnectionFactory = Callable[[], object]


@dataclass(frozen=True)
class MovementRecord:
    id: int
    customer_id: int | None
    movement_type: str
    description: str
    value: float
    occurred_at: str = ""
    payment_method: str = ""
    customer_name: str = ""


class MovementService:
    """Consulta e edição auditada de movimentações sem dependência da interface."""

    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    def get(self, movement_id: int) -> MovementRecord | None:
        movement_id = self._valid_id(movement_id)
        conn = self._connection_factory()
        try:
            row = conn.execute(
                """
                SELECT m.id,m.cliente_id,m.tipo,COALESCE(m.descricao,''),COALESCE(m.valor,0),
                       COALESCE(m.data,''),COALESCE(m.forma_pagamento,''),
                       COALESCE(c.nome,'Sem cliente')
                FROM movimentacoes m
                LEFT JOIN clientes c ON c.id=m.cliente_id
                WHERE m.id=?
                """,
                (movement_id,),
            ).fetchone()
            if row is None:
                return None
            return MovementRecord(
                id=int(row[0]),
                customer_id=int(row[1]) if row[1] is not None else None,
                movement_type=str(row[2] or "").upper(),
                description=str(row[3] or ""),
                value=float(row[4] or 0),
                occurred_at=str(row[5] or ""),
                payment_method=str(row[6] or ""),
                customer_name=str(row[7] or "Sem cliente"),
            )
        finally:
            conn.close()

    def update(self, movement_id: int, description: str, value: float) -> MovementRecord:
        movement_id = self._valid_id(movement_id)
        new_description, new_value = MovementValidator.update_values(description, value)

        conn = self._connection_factory()
        try:
            row = conn.execute(
                "SELECT cliente_id,tipo,COALESCE(descricao,''),COALESCE(valor,0) "
                "FROM movimentacoes WHERE id=?",
                (movement_id,),
            ).fetchone()
            if row is None:
                raise LookupError("Movimentação não encontrada.")
            customer_id = int(row[0]) if row[0] is not None else None
            movement_type = str(row[1] or "").upper()
            old_value = float(row[3] or 0)

            if customer_id is not None:
                balance_delta = self._balance_delta(movement_type, old_value, new_value)
                if balance_delta:
                    conn.execute(
                        "UPDATE clientes SET saldo_devedor=MAX(0,COALESCE(saldo_devedor,0)+?) WHERE id=?",
                        (balance_delta, customer_id),
                    )

            conn.execute(
                "UPDATE movimentacoes SET descricao=?,valor=? WHERE id=?",
                (new_description, new_value, movement_id),
            )
            if customer_id is not None:
                conn.execute(
                    "INSERT INTO historico_clientes(cliente_id,evento,detalhes,data) VALUES(?,?,?,?)",
                    (
                        customer_id,
                        "EDIÇÃO",
                        f"Lançamento #{movement_id} alterado: {new_description} — R$ {new_value:.2f}.",
                        datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        updated = self.get(movement_id)
        if updated is None:  # pragma: no cover - proteção contra corrupção concorrente
            raise RuntimeError("A movimentação foi alterada, mas não pôde ser relida.")
        return updated

    @staticmethod
    def _balance_delta(movement_type: str, old_value: float, new_value: float) -> float:
        if movement_type == "COMPRA":
            return new_value - old_value
        if movement_type == "PAGAMENTO":
            return old_value - new_value
        return 0.0

    _valid_id = staticmethod(MovementValidator.movement_id)
