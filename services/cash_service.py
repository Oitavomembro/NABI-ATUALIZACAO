from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Optional

from repositories.decimal_storage import DecimalStorage


ConnectionFactory = Callable[[], object]


@dataclass(frozen=True)
class CashClosingResult:
    closing_id: int
    replaced: bool


class CashService:
    """Persistência e cálculos do caixa, sem dependência da interface gráfica."""

    MOVEMENT_TYPES = {
        "RETIRADA": "RETIRADA_CAIXA",
        "SUPRIMENTO": "SUPRIMENTO_CAIXA",
        "PAGAMENTO DE CONTA": "PAGAMENTO_CONTA",
    }

    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory

    @staticmethod
    def _columns(connection, table: str) -> set[str]:
        return {str(row[1]).casefold() for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}

    def has_opening(self, date_sql: str) -> bool:
        conn = self._connection_factory()
        try:
            return conn.execute(
                "SELECT 1 FROM caixa_aberturas WHERE data_caixa=?", (date_sql,)
            ).fetchone() is not None
        finally:
            conn.close()

    def register_opening(
        self,
        date_sql: str,
        initial_value: Any = Decimal("0"),
        responsible: str = "",
        observation: str = "",
        created_at: Optional[str] = None,
    ) -> None:
        value = DecimalStorage.to_decimal(initial_value, field="valor inicial")
        if value < 0:
            raise ValueError("O valor inicial não pode ser negativo.")
        conn = self._connection_factory()
        try:
            if "valor_inicial_decimal" in self._columns(conn, "caixa_aberturas"):
                conn.execute(
                    """INSERT OR REPLACE INTO caixa_aberturas(
                           data_caixa,valor_inicial,valor_inicial_decimal,responsavel,observacao,criado_em
                       ) VALUES(?,?,?,?,?,?)""",
                    (date_sql, DecimalStorage.legacy_real(value, field="valor inicial"), DecimalStorage.canonical(value, field="valor inicial"), (responsible or "").strip(), (observation or "").strip(), created_at or datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
                )
            else:
                conn.execute(
                    """INSERT OR REPLACE INTO caixa_aberturas(data_caixa,valor_inicial,responsavel,observacao,criado_em) VALUES(?,?,?,?,?)""",
                    (date_sql, DecimalStorage.legacy_real(value, field="valor inicial"), (responsible or "").strip(), (observation or "").strip(), created_at or datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def register_movement(
        self,
        movement_type: str,
        value: Any,
        payment_method: str,
        description: str = "",
        responsible: str = "",
        occurred_at: Optional[str] = None,
    ) -> int:
        label = (movement_type or "").strip().upper()
        db_type = self.MOVEMENT_TYPES.get(label, label)
        if db_type not in set(self.MOVEMENT_TYPES.values()):
            raise ValueError("Tipo de movimentação de caixa inválido.")
        amount = DecimalStorage.to_decimal(value, field="valor da movimentação")
        if amount <= 0:
            raise ValueError("O valor deve ser maior que zero.")
        conn = self._connection_factory()
        try:
            cur = conn.cursor()
            if {"valor_decimal", "valor_aberto_decimal"}.issubset(self._columns(conn, "movimentacoes")):
                cur.execute(
                    """INSERT INTO movimentacoes(cliente_id,tipo,descricao,valor,valor_decimal,data,status_pagamento,valor_aberto,valor_aberto_decimal,forma_pagamento,responsavel)
                       VALUES(NULL,?,?,?,?,?, 'PAGO',0,'0',?,?)""",
                    (db_type, (description or label.title()).strip(), DecimalStorage.legacy_real(amount, field="valor da movimentação"), DecimalStorage.canonical(amount, field="valor da movimentação"), occurred_at or datetime.now().strftime("%d/%m/%Y %H:%M:%S"), (payment_method or "").strip(), (responsible or "").strip()),
                )
            else:
                cur.execute(
                    """INSERT INTO movimentacoes(cliente_id,tipo,descricao,valor,data,status_pagamento,valor_aberto,forma_pagamento,responsavel)
                       VALUES(NULL,?,?,?,?, 'PAGO',0,?,?)""",
                    (db_type, (description or label.title()).strip(), DecimalStorage.legacy_real(amount, field="valor da movimentação"), occurred_at or datetime.now().strftime("%d/%m/%Y %H:%M:%S"), (payment_method or "").strip(), (responsible or "").strip()),
                )
            movement_id = int(cur.lastrowid)
            conn.commit()
            return movement_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def daily_summary(self, date_br: Optional[str] = None) -> dict:
        date_br = date_br or datetime.now().strftime("%d/%m/%Y")
        date_sql = datetime.strptime(date_br, "%d/%m/%Y").strftime("%Y-%m-%d")
        conn = self._connection_factory()
        try:
            movement_columns = self._columns(conn, "movimentacoes")
            movement_canonical = "valor_decimal" if "valor_decimal" in movement_columns else "NULL"
            rows = conn.execute(
                f"SELECT tipo,COALESCE(forma_pagamento,''),valor,{movement_canonical} FROM movimentacoes WHERE data LIKE ?",
                (date_br + "%",),
            ).fetchall()
            opening_columns = self._columns(conn, "caixa_aberturas")
            opening_canonical = "valor_inicial_decimal" if "valor_inicial_decimal" in opening_columns else "NULL"
            opening = conn.execute(
                f"SELECT valor_inicial,{opening_canonical},responsavel,observacao FROM caixa_aberturas WHERE data_caixa=?",
                (date_sql,),
            ).fetchone() or (0, None, "", "")
        finally:
            conn.close()

        totals = defaultdict(lambda: Decimal("0"))
        payment_methods = defaultdict(lambda: Decimal("0"))
        for movement_type, payment_method, legacy_value, canonical_value in rows:
            amount = DecimalStorage.read(canonical_value, legacy_value, field="valor da movimentação")
            totals[movement_type] += amount
            if movement_type in ("PAGAMENTO", "SUPRIMENTO_CAIXA"):
                payment_methods[payment_method or "Não informada"] += amount
        opening_value = DecimalStorage.read(opening[1], opening[0], field="valor inicial")
        entries = totals["PAGAMENTO"] + totals["SUPRIMENTO_CAIXA"] + opening_value
        exits = totals["RETIRADA_CAIXA"] + totals["PAGAMENTO_CONTA"]
        return {
            "data": date_br,
            "vendas": totals["COMPRA"],
            "recebimentos": totals["PAGAMENTO"],
            "abatimentos": totals["ABATIMENTO"],
            "suprimentos": totals["SUPRIMENTO_CAIXA"],
            "retiradas": totals["RETIRADA_CAIXA"],
            "contas": totals["PAGAMENTO_CONTA"],
            "abertura": opening_value,
            "entradas": entries,
            "saidas": exits,
            "saldo_esperado": entries - exits,
            "formas": dict(payment_methods),
            "responsavel_abertura": opening[2] or "",
            "obs_abertura": opening[3] or "",
        }

    def existing_closing_id(self, date_sql: str) -> Optional[int]:
        conn = self._connection_factory()
        try:
            row = conn.execute(
                "SELECT id FROM fechamentos_caixa WHERE data_caixa=? ORDER BY id DESC LIMIT 1",
                (date_sql,),
            ).fetchone()
            return int(row[0]) if row else None
        finally:
            conn.close()

    def save_closing(
        self,
        date_sql: str,
        expected_value: Any,
        counted_value: Optional[float],
        responsible: str = "",
        observation: str = "",
        pdf_path: str = "",
        replace_existing: bool = False,
        created_at: Optional[str] = None,
    ) -> CashClosingResult:
        expected = DecimalStorage.to_decimal(expected_value, field="valor esperado")
        counted = None if counted_value is None else DecimalStorage.to_decimal(counted_value, field="valor contado")
        difference = None if counted is None else counted - expected
        conn = self._connection_factory()
        try:
            row = conn.execute(
                "SELECT id FROM fechamentos_caixa WHERE data_caixa=? ORDER BY id DESC LIMIT 1",
                (date_sql,),
            ).fetchone()
            now = created_at or datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            canonical_closing = {"valor_esperado_decimal", "valor_contado_decimal", "diferenca_decimal"}.issubset(self._columns(conn, "fechamentos_caixa"))
            if row:
                if not replace_existing:
                    raise FileExistsError("Já existe fechamento para a data informada.")
                closing_id = int(row[0])
                if canonical_closing:
                    conn.execute("""UPDATE fechamentos_caixa SET valor_esperado=?,valor_esperado_decimal=?,valor_contado=?,valor_contado_decimal=?,diferenca=?,diferenca_decimal=?,responsavel=?,observacao=?,pdf_path=?,criado_em=? WHERE id=?""", (DecimalStorage.legacy_real(expected, field="valor esperado"), DecimalStorage.canonical(expected, field="valor esperado"), None if counted is None else DecimalStorage.legacy_real(counted, field="valor contado"), None if counted is None else DecimalStorage.canonical(counted, field="valor contado"), None if difference is None else DecimalStorage.legacy_real(difference, field="diferença"), None if difference is None else DecimalStorage.canonical(difference, field="diferença"), (responsible or "").strip(), (observation or "").strip(), str(pdf_path or ""), now, closing_id))
                else:
                    conn.execute("""UPDATE fechamentos_caixa SET valor_esperado=?,valor_contado=?,diferenca=?,responsavel=?,observacao=?,pdf_path=?,criado_em=? WHERE id=?""", (DecimalStorage.legacy_real(expected, field="valor esperado"), None if counted is None else DecimalStorage.legacy_real(counted, field="valor contado"), None if difference is None else DecimalStorage.legacy_real(difference, field="diferença"), (responsible or "").strip(), (observation or "").strip(), str(pdf_path or ""), now, closing_id))
                replaced = True
            else:
                cur = conn.cursor()
                if canonical_closing:
                    cur.execute("""INSERT INTO fechamentos_caixa(data_caixa,valor_esperado,valor_esperado_decimal,valor_contado,valor_contado_decimal,diferenca,diferenca_decimal,responsavel,observacao,pdf_path,criado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (date_sql, DecimalStorage.legacy_real(expected, field="valor esperado"), DecimalStorage.canonical(expected, field="valor esperado"), None if counted is None else DecimalStorage.legacy_real(counted, field="valor contado"), None if counted is None else DecimalStorage.canonical(counted, field="valor contado"), None if difference is None else DecimalStorage.legacy_real(difference, field="diferença"), None if difference is None else DecimalStorage.canonical(difference, field="diferença"), (responsible or "").strip(), (observation or "").strip(), str(pdf_path or ""), now))
                else:
                    cur.execute("""INSERT INTO fechamentos_caixa(data_caixa,valor_esperado,valor_contado,diferenca,responsavel,observacao,pdf_path,criado_em) VALUES(?,?,?,?,?,?,?,?)""", (date_sql, DecimalStorage.legacy_real(expected, field="valor esperado"), None if counted is None else DecimalStorage.legacy_real(counted, field="valor contado"), None if difference is None else DecimalStorage.legacy_real(difference, field="diferença"), (responsible or "").strip(), (observation or "").strip(), str(pdf_path or ""), now))
                closing_id = int(cur.lastrowid)
                replaced = False
            conn.commit()
            return CashClosingResult(closing_id, replaced)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def movement_type(self, movement_id: int) -> str:
        conn = self._connection_factory()
        try:
            row = conn.execute(
                "SELECT tipo FROM movimentacoes WHERE id=?", (int(movement_id),)
            ).fetchone()
            return str(row[0]) if row else ""
        finally:
            conn.close()
