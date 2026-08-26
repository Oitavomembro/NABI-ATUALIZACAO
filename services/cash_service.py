from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Optional
import json
import re

from repositories.assistant_operation_journal_repository import AssistantOperationJournalRepository
from repositories.decimal_storage import DecimalStorage
from services.critical_audit_policy import is_critical_event, record_in_transaction


ConnectionFactory = Callable[[], object]


@dataclass(frozen=True)
class CashClosingResult:
    closing_id: int
    replaced: bool


@dataclass(frozen=True)
class CashSession:
    id: int
    terminal: str
    opened_by: str
    opened_at: str
    opening_balance: Decimal
    opening_mode: str
    status: str
    closed_by: str = ""
    closed_at: str = ""
    expected_cash: Optional[Decimal] = None
    counted_cash: Optional[Decimal] = None
    difference: Optional[Decimal] = None
    closing_note: str = ""


class CashService:
    """Persistência e cálculos do caixa, sem dependência da interface gráfica."""

    MOVEMENT_TYPES = {
        "RETIRADA": "RETIRADA_CAIXA",
        "SUPRIMENTO": "SUPRIMENTO_CAIXA",
        "PAGAMENTO DE CONTA": "PAGAMENTO_CONTA",
    }

    def __init__(self, connection_factory: ConnectionFactory):
        self._connection_factory = connection_factory
        self._operation_journal = AssistantOperationJournalRepository()

    @staticmethod
    def _assisted_identity(idempotency_key: str, operation_fingerprint: str, user: str):
        key = str(idempotency_key or "").strip()
        fingerprint = str(operation_fingerprint or "").strip().lower()
        actor = str(user or "").strip()
        if not key or len(key) > 160 or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise ValueError("Identificação idempotente do caixa inválida.")
        if not actor:
            raise PermissionError("Operador autenticado é obrigatório no caixa assistido.")
        return key, fingerprint, actor

    def _begin_assisted(self, conn, *, key, fingerprint, kind, actor):
        previous = self._operation_journal.get(conn, key)
        if previous:
            if self._operation_journal.operation_kind(conn, key) != kind:
                raise PermissionError("A chave idempotente pertence a outra operação.")
            if previous["fingerprint"].lower() != fingerprint:
                raise PermissionError("A chave idempotente já pertence a outro conteúdo.")
            if previous["status"] != "COMMITTED":
                raise RuntimeError("A operação assistida anterior não foi concluída.")
            return json.loads(previous["result_json"])
        self._operation_journal.begin(
            conn, idempotency_key=key, operation_kind=kind,
            fingerprint=fingerprint, username=actor,
        )
        return None

    def open_session_assisted(self, terminal: str, user: str, opening_balance: Any,
                              opening_mode: str, *, idempotency_key: str,
                              operation_fingerprint: str) -> dict[str, Any]:
        key, fingerprint, actor = self._assisted_identity(
            idempotency_key, operation_fingerprint, user
        )
        terminal = str(terminal or "").strip()
        mode = str(opening_mode or "").strip().upper()
        balance = self._money(opening_balance, "saldo inicial")
        if not terminal or mode not in {"VALOR_INFORMADO", "SEM_VALOR_INFORMADO"}:
            raise ValueError("Terminal ou modo de abertura inválido.")
        if balance < 0:
            raise ValueError("O saldo inicial não pode ser negativo.")
        if mode == "SEM_VALOR_INFORMADO":
            balance = Decimal("0.00")
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        conn = self._connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            replay = self._begin_assisted(
                conn, key=key, fingerprint=fingerprint, kind="CASH_OPEN", actor=actor
            )
            if replay is not None:
                conn.commit(); return {**replay, "idempotent_replay": True}
            if conn.execute("SELECT 1 FROM cash_sessions WHERE terminal=? AND status='ABERTO'", (terminal,)).fetchone():
                raise FileExistsError("Já existe um caixa aberto neste terminal.")
            cursor = conn.execute(
                "INSERT INTO cash_sessions(terminal,opened_by,opened_at,opening_balance,opening_mode,status) VALUES(?,?,?,?,?,'ABERTO')",
                (terminal, actor, now, DecimalStorage.canonical(balance, field="saldo inicial"), mode),
            )
            session_id = int(cursor.lastrowid)
            self._audit(conn, actor, "CAIXA_ABERTO", session_id,
                        f"terminal={terminal}; saldo={balance:.2f}; modo={mode}", now)
            result = {"session_id": session_id, "terminal": terminal, "status": "ABERTO"}
            self._operation_journal.commit(conn, idempotency_key=key,
                                           result_json=json.dumps(result, sort_keys=True))
            conn.commit(); return {**result, "idempotent_replay": False}
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    def register_session_movement_assisted(
        self, terminal: str, movement_type: str, amount: Any, user: str, note: str,
        *, idempotency_key: str, operation_fingerprint: str,
    ) -> dict[str, Any]:
        key, fingerprint, actor = self._assisted_identity(
            idempotency_key, operation_fingerprint, user
        )
        terminal = str(terminal or "").strip(); kind = str(movement_type or "").strip().upper()
        value = self._money(amount, "valor do movimento")
        if kind not in {"SANGRIA", "SUPRIMENTO"} or value <= 0:
            raise ValueError("Movimento assistido do caixa inválido.")
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        conn = self._connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            replay = self._begin_assisted(
                conn, key=key, fingerprint=fingerprint, kind=f"CASH_{kind}", actor=actor
            )
            if replay is not None:
                conn.commit(); return {**replay, "idempotent_replay": True}
            row = conn.execute(
                "SELECT id FROM cash_sessions WHERE terminal=? AND status='ABERTO' ORDER BY id DESC LIMIT 1",
                (terminal,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Não existe caixa aberto neste terminal.")
            session_id = int(row[0])
            cursor = conn.execute(
                "INSERT INTO cash_movements(cash_session_id,type,amount,user_id,note,created_at) VALUES(?,?,?,?,?,?)",
                (session_id, kind, DecimalStorage.canonical(value, field="valor do movimento"), actor, str(note or "").strip(), now),
            )
            movement_id = int(cursor.lastrowid)
            self._audit(conn, actor, kind, session_id,
                        f"valor={value:.2f}; motivo={str(note or '').strip()}", now)
            result = {"session_id": session_id, "movement_id": movement_id,
                      "movement_type": kind, "amount": format(value, ".2f")}
            self._operation_journal.commit(conn, idempotency_key=key,
                                           result_json=json.dumps(result, sort_keys=True))
            conn.commit(); return {**result, "idempotent_replay": False}
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    def close_session_assisted(self, *_args, **_kwargs):
        raise RuntimeError(
            "Fechamento assistido permanece bloqueado: o cálculo e o diário ainda não compartilham uma transação atômica."
        )

    @staticmethod
    def _money(value: Any, field: str = "valor") -> Decimal:
        return DecimalStorage.to_decimal(value, field=field).quantize(Decimal("0.01"))

    @staticmethod
    def _session(row) -> Optional[CashSession]:
        if not row:
            return None
        decimal_or_none = lambda value: None if value in (None, "") else Decimal(str(value))
        return CashSession(
            id=int(row[0]), terminal=str(row[1]), opened_by=str(row[2]), opened_at=str(row[3]),
            opening_balance=Decimal(str(row[4])), opening_mode=str(row[5]), status=str(row[6]),
            closed_by=str(row[7] or ""), closed_at=str(row[8] or ""),
            expected_cash=decimal_or_none(row[9]), counted_cash=decimal_or_none(row[10]),
            difference=decimal_or_none(row[11]), closing_note=str(row[12] or ""),
        )

    def get_open_session(self, terminal: str) -> Optional[CashSession]:
        conn = self._connection_factory()
        try:
            row = conn.execute(
                """SELECT id,terminal,opened_by,opened_at,opening_balance,opening_mode,status,
                          closed_by,closed_at,expected_cash,counted_cash,difference,closing_note
                     FROM cash_sessions WHERE terminal=? AND status='ABERTO' ORDER BY id DESC LIMIT 1""",
                (str(terminal).strip(),),
            ).fetchone()
            return self._session(row)
        finally:
            conn.close()

    def open_session(self, terminal: str, user: str, opening_balance: Any = 0,
                     opening_mode: str = "VALOR_INFORMADO", opened_at: Optional[str] = None) -> CashSession:
        terminal = str(terminal or "").strip()
        user = str(user or "Sistema").strip() or "Sistema"
        mode = str(opening_mode or "").strip().upper()
        if not terminal:
            raise ValueError("Terminal não identificado.")
        if mode not in {"VALOR_INFORMADO", "SEM_VALOR_INFORMADO"}:
            raise ValueError("Modo de abertura inválido.")
        balance = self._money(opening_balance, "saldo inicial")
        if balance < 0:
            raise ValueError("O saldo inicial não pode ser negativo.")
        if mode == "SEM_VALOR_INFORMADO":
            balance = Decimal("0.00")
        now = opened_at or datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        conn = self._connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM cash_sessions WHERE terminal=? AND status='ABERTO'", (terminal,)).fetchone():
                raise FileExistsError("Já existe um caixa aberto neste terminal.")
            cursor = conn.execute(
                "INSERT INTO cash_sessions(terminal,opened_by,opened_at,opening_balance,opening_mode,status) VALUES(?,?,?,?,?,'ABERTO')",
                (terminal, user, now, DecimalStorage.canonical(balance, field="saldo inicial"), mode),
            )
            session_id = int(cursor.lastrowid)
            self._audit(conn, user, "CAIXA_ABERTO", session_id, f"terminal={terminal}; saldo={balance:.2f}; modo={mode}", now)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_open_session(terminal)  # type: ignore[return-value]

    @staticmethod
    def _audit(conn, user: str, action: str, session_id: int, details: str, occurred_at: str) -> None:
        tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if is_critical_event("CAIXA", action):
            record_in_transaction(
                conn,
                "CAIXA",
                action,
                user=user,
                object_id=session_id,
                details=details,
                occurred_at=occurred_at,
            )
            return
        if "auditoria" in tables:
            conn.execute(
                "INSERT INTO auditoria(data,usuario,modulo,acao,objeto,detalhes,resultado) VALUES(?,?,'CAIXA',?,?,?,'SUCESSO')",
                (occurred_at, user, action, str(session_id), details),
            )

    def register_session_movement(self, terminal: str, movement_type: str, amount: Any,
                                  user: str, note: str = "", occurred_at: Optional[str] = None) -> int:
        kind = str(movement_type or "").strip().upper()
        if kind not in {"SANGRIA", "SUPRIMENTO"}:
            raise ValueError("Tipo de movimento de caixa inválido.")
        value = self._money(amount, "valor do movimento")
        if value <= 0:
            raise ValueError("O valor deve ser maior que zero.")
        session = self.get_open_session(terminal)
        if session is None:
            raise RuntimeError("Não existe caixa aberto neste terminal.")
        now = occurred_at or datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        actor = str(user or "Sistema").strip() or "Sistema"
        conn = self._connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM cash_sessions WHERE id=? AND status='ABERTO'", (session.id,)).fetchone():
                raise RuntimeError("A sessão de caixa está fechada.")
            cur = conn.execute(
                "INSERT INTO cash_movements(cash_session_id,type,amount,user_id,note,created_at) VALUES(?,?,?,?,?,?)",
                (session.id, kind, DecimalStorage.canonical(value, field="valor do movimento"), actor, str(note or "").strip(), now),
            )
            self._audit(conn, actor, kind, session.id, f"valor={value:.2f}; motivo={str(note or '').strip()}", now)
            conn.commit()
            return int(cur.lastrowid)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @classmethod
    def _payment_parts(cls, description: str, total: Decimal) -> dict[str, Decimal]:
        text = str(description or "").upper()
        parts = {"DINHEIRO": Decimal("0"), "PIX": Decimal("0"), "CARTAO": Decimal("0"), "OUTROS": Decimal("0")}
        matches = re.findall(r"(DINHEIRO|PIX|CART(?:ÃO|AO)(?: DE CR[EÉ]DITO| DE D[EÉ]BITO)?|CREDIARIO|TRANSFER[EÊ]NCIA|OUTRO)\s+R\$\s*([0-9.,]+)", text)
        if matches:
            for label, raw in matches:
                value = DecimalStorage.to_decimal(raw, field="forma de pagamento")
                key = "DINHEIRO" if label == "DINHEIRO" else "PIX" if label == "PIX" else "CARTAO" if label.startswith("CART") else "OUTROS"
                parts[key] += value
            return parts
        key = "DINHEIRO" if "DINHEIRO" in text else "PIX" if "PIX" in text else "CARTAO" if "CART" in text else "OUTROS"
        parts[key] = total
        return parts

    def session_summary(self, session_id: int) -> dict[str, Any]:
        conn = self._connection_factory()
        try:
            row = conn.execute("SELECT id,terminal,opened_by,opened_at,opening_balance,opening_mode,status,closed_by,closed_at,expected_cash,counted_cash,difference,closing_note FROM cash_sessions WHERE id=?", (int(session_id),)).fetchone()
            session = self._session(row)
            if session is None:
                raise LookupError("Sessão de caixa não encontrada.")
            end = session.closed_at or "99/99/9999 99:99:99"
            movement_columns = self._columns(conn, "movimentacoes")
            canonical = "valor_decimal" if "valor_decimal" in movement_columns else "NULL"
            status = "COALESCE(status_pagamento,'')" if "status_pagamento" in movement_columns else "''"
            responsible = "COALESCE(responsavel,'')" if "responsavel" in movement_columns else "''"
            description = "COALESCE(descricao,'')" if "descricao" in movement_columns else "''"
            document = "COALESCE(documento_numero,'')" if "documento_numero" in movement_columns else "''"
            source_system = "COALESCE(origem_sistema,'')" if "origem_sistema" in movement_columns else "''"
            source_reference = "COALESCE(origem_id,'')" if "origem_id" in movement_columns else "''"
            movement_sql = (
                f"SELECT id,tipo,COALESCE(forma_pagamento,''),valor,{canonical},data,"
                f"{status},{responsible},{description},{document},{source_system},{source_reference} "
                "FROM movimentacoes WHERE tipo IN ('COMPRA','PAGAMENTO')"
            )
            movement_params: list[str] = []
            date_prefixes = self._session_date_prefixes(session.opened_at, session.closed_at)
            if date_prefixes:
                movement_sql += " AND (" + " OR ".join("data GLOB ?" for _ in date_prefixes) + ")"
                movement_params.extend(f"{prefix} *" for prefix in date_prefixes)
            movements = conn.execute(movement_sql, movement_params).fetchall()
            own = conn.execute(
                "SELECT id,type,amount,user_id,note,created_at "
                "FROM cash_movements WHERE cash_session_id=? ORDER BY id",
                (session.id,),
            ).fetchall()
        finally:
            conn.close()
        totals = {key: Decimal("0.00") for key in ("dinheiro", "pix", "cartao", "outros", "recebimentos_dinheiro", "recebimentos_eletronicos", "sangrias", "suprimentos")}
        def parsed(value: str):
            try: return datetime.strptime(value, "%d/%m/%Y %H:%M:%S")
            except (TypeError, ValueError): return None
        start_dt, end_dt = parsed(session.opened_at), parsed(end)
        history = []
        for source_id, kind, method, legacy, canonical, date_text, status, responsible, description, document, source_system, source_reference in movements:
            when = parsed(date_text)
            if str(status).upper() == "CANCELADO" or not when or (start_dt and when < start_dt) or (end_dt and when > end_dt):
                continue
            value = DecimalStorage.read(canonical, legacy, field="movimento")
            parts = self._payment_parts(method, value)
            if kind == "COMPRA":
                origin = (
                    f"{source_system} #{source_reference}"
                    if source_system and source_reference else f"VENDA #{source_id}"
                )
                for key in ("DINHEIRO", "PIX", "CARTAO", "OUTROS"):
                    totals[key.casefold().replace("cartao", "cartao")] += parts[key]
                for key, value_part in parts.items():
                    if value_part:
                        history.append({"tipo": f"VENDA {key}", "valor": value_part, "usuario": responsible or "", "observacao": description or f"Venda #{source_id}", "data": date_text, "origem": origin, "documento": document or "", "sinal": 1})
            elif kind == "PAGAMENTO":
                origin = (
                    f"{source_system} #{source_reference}"
                    if source_system and source_reference else f"RECEBIMENTO #{source_id}"
                )
                totals["recebimentos_dinheiro"] += parts["DINHEIRO"]
                totals["recebimentos_eletronicos"] += parts["PIX"] + parts["CARTAO"] + parts["OUTROS"]
                for key, value_part in parts.items():
                    if value_part:
                        history.append({"tipo": f"RECEBIMENTO {key}", "valor": value_part, "usuario": responsible or "", "observacao": description or f"Recebimento #{source_id}", "data": date_text, "origem": origin, "documento": document or "", "sinal": 1})
        for movement_id, kind, amount, user, note, created in own:
            value = Decimal(str(amount))
            totals["sangrias" if kind == "SANGRIA" else "suprimentos"] += value
            history.append({"tipo": kind, "valor": value, "usuario": user, "observacao": note, "data": created, "origem": f"CAIXA #{movement_id}", "documento": "", "sinal": -1 if kind == "SANGRIA" else 1})
        history.sort(key=lambda item: parsed(item["data"]) or datetime.min)
        expected = session.opening_balance + totals["dinheiro"] + totals["recebimentos_dinheiro"] + totals["suprimentos"] - totals["sangrias"]
        movement_total = sum(
            (totals[key] for key in ("dinheiro", "pix", "cartao", "outros")),
            Decimal("0"),
        )
        return {"session": session, **totals, "expected_cash": expected, "movement_total": movement_total, "movements": history}

    @staticmethod
    def _session_date_prefixes(opened_at: str, closed_at: str = "") -> list[str]:
        """Dias da sessão para limitar a leitura do histórico sem perder compatibilidade."""

        try:
            start = datetime.strptime(opened_at, "%d/%m/%Y %H:%M:%S")
            end = datetime.strptime(closed_at, "%d/%m/%Y %H:%M:%S") if closed_at else datetime.now()
        except (TypeError, ValueError):
            return []
        if end < start:
            return []
        day_count = (end.date() - start.date()).days + 1
        if day_count > 366:
            return []
        return [(start + timedelta(days=offset)).strftime("%d/%m/%Y") for offset in range(day_count)]

    def close_session(self, terminal: str, counted_cash: Any, user: str, note: str = "",
                      closed_at: Optional[str] = None) -> CashSession:
        session = self.get_open_session(terminal)
        if session is None:
            raise RuntimeError("Não existe caixa aberto neste terminal.")
        counted = self._money(counted_cash, "valor contado")
        if counted < 0:
            raise ValueError("O valor contado não pode ser negativo.")
        summary = self.session_summary(session.id)
        expected = summary["expected_cash"]
        difference = counted - expected
        note = str(note or "").strip()
        if difference != 0 and not note:
            raise ValueError("Informe uma observação para sobra ou falta de caixa.")
        actor = str(user or "Sistema").strip() or "Sistema"
        now = closed_at or datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        conn = self._connection_factory()
        try:
            conn.execute("BEGIN IMMEDIATE")
            updated = conn.execute(
                """UPDATE cash_sessions SET status='FECHADO',closed_by=?,closed_at=?,expected_cash=?,counted_cash=?,difference=?,closing_note=?
                   WHERE id=? AND status='ABERTO'""",
                (actor, now, str(expected), str(counted), str(difference), note, session.id),
            )
            if updated.rowcount != 1:
                raise RuntimeError("A sessão de caixa já foi fechada.")
            self._audit(conn, actor, "CAIXA_FECHADO", session.id, f"esperado={expected:.2f}; contado={counted:.2f}; diferenca={difference:.2f}; observacao={note}", now)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.history(terminal, session.id)[0]

    def history(
        self,
        terminal: str,
        session_id: Optional[int] = None,
        opened_date: Optional[str] = None,
    ) -> list[CashSession]:
        conn = self._connection_factory()
        try:
            sql = "SELECT id,terminal,opened_by,opened_at,opening_balance,opening_mode,status,closed_by,closed_at,expected_cash,counted_cash,difference,closing_note FROM cash_sessions WHERE terminal=?"
            params: list[Any] = [str(terminal).strip()]
            if session_id is not None:
                sql += " AND id=?"; params.append(int(session_id))
            if opened_date is not None:
                try:
                    normalized_date = datetime.strptime(str(opened_date).strip(), "%d/%m/%Y").strftime("%d/%m/%Y")
                except (TypeError, ValueError) as exc:
                    raise ValueError("Informe a data no formato DD/MM/AAAA.") from exc
                sql += " AND opened_at GLOB ?"; params.append(f"{normalized_date} *")
            sql += " ORDER BY id DESC"
            return [self._session(row) for row in conn.execute(sql, params).fetchall()]  # type: ignore[misc]
        finally:
            conn.close()

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
