from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


class FiscalOutboxService:
    """Persistência transacional da fila fiscal, sem executar transmissão."""

    LEGACY_KEY = "fiscal.fila_transmissao.v1"
    MIGRATION_KEY = "fiscal.outbox.migracao_fila_v1"
    CLAIMABLE = {"PENDENTE", "ERRO"}
    TERMINAL = {"CONCLUIDO", "CANCELADO"}

    def __init__(self, connection_factory) -> None:
        self.connection_factory = connection_factory

    @staticmethod
    def ensure_schema(connection: Any) -> None:
        connection.execute("""CREATE TABLE IF NOT EXISTS fiscal_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER, fiscal_document_id INTEGER,
            access_key TEXT NOT NULL DEFAULT '', environment TEXT NOT NULL,
            operation TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDENTE',
            attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 5,
            retry_minutes INTEGER NOT NULL DEFAULT 5, next_attempt_at TEXT,
            worker_id TEXT NOT NULL DEFAULT '', claimed_at TEXT, lease_until TEXT,
            receipt TEXT NOT NULL DEFAULT '', last_error_code TEXT NOT NULL DEFAULT '',
            last_error_message TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '55',
            reservation_id TEXT NOT NULL DEFAULT '', xml_b64 TEXT NOT NULL DEFAULT '',
            original_xml_b64 TEXT NOT NULL DEFAULT '', actor TEXT NOT NULL DEFAULT '',
            contingency INTEGER NOT NULL DEFAULT 0, contingency_deadline_at TEXT NOT NULL DEFAULT '',
            legacy_id TEXT NOT NULL DEFAULT '', metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES movimentacoes(id),
            FOREIGN KEY(fiscal_document_id) REFERENCES fiscal_sale_documents(id))""")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_fiscal_outbox_document ON fiscal_outbox(fiscal_document_id) WHERE fiscal_document_id IS NOT NULL")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_fiscal_outbox_legacy ON fiscal_outbox(legacy_id) WHERE legacy_id != ''")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_fiscal_outbox_authorization_key ON fiscal_outbox(access_key) WHERE access_key != '' AND operation IN ('autorizacao','recibo')")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_fiscal_outbox_claim ON fiscal_outbox(status,next_attempt_at,lease_until,created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_fiscal_outbox_sale ON fiscal_outbox(sale_id,fiscal_document_id)")
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(fiscal_outbox)")}
        if "metadata_json" not in columns:
            connection.execute("ALTER TABLE fiscal_outbox ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")

    @staticmethod
    def enqueue_in_transaction(
        connection: Any, *, sale_id: int | None, fiscal_document_id: int | None,
        access_key: str, environment: str, operation: str, model: str,
        reservation_id: str, xml_b64: str, actor: str,
        original_xml_b64: str = "", max_attempts: int = 5,
        retry_minutes: int = 5, contingency: bool = False,
        contingency_deadline_at: str = "", legacy_id: str = "", created_at: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = str(created_at or datetime.now(timezone.utc).isoformat())
        operation = str(operation or "").strip().lower()
        FiscalOutboxService.ensure_schema(connection)
        cursor = connection.execute(
            """INSERT OR IGNORE INTO fiscal_outbox
               (sale_id,fiscal_document_id,access_key,environment,operation,status,
                attempts,max_attempts,retry_minutes,next_attempt_at,worker_id,claimed_at,
                lease_until,receipt,last_error_code,last_error_message,model,reservation_id,
                xml_b64,original_xml_b64,actor,contingency,contingency_deadline_at,
                legacy_id,metadata_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                sale_id, fiscal_document_id, str(access_key), str(environment).upper(), operation,
                "PENDENTE", 0, max(1, int(max_attempts)), max(1, int(retry_minutes)), now,
                "", None, None, "", "", "", str(model), str(reservation_id),
                str(xml_b64), str(original_xml_b64 or xml_b64),
                str(actor or "").strip(), 1 if contingency else 0,
                str(contingency_deadline_at or ""), str(legacy_id or ""),
                json.dumps(dict(metadata or {}), ensure_ascii=False, sort_keys=True), now, now,
            ),
        )
        if fiscal_document_id:
            row = connection.execute(
                "SELECT * FROM fiscal_outbox WHERE fiscal_document_id=?", (int(fiscal_document_id),)
            ).fetchone()
        elif cursor.lastrowid:
            row = connection.execute(
                "SELECT * FROM fiscal_outbox WHERE id=?", (int(cursor.lastrowid),)
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT * FROM fiscal_outbox WHERE access_key=? AND operation IN ('autorizacao','recibo')",
                (str(access_key),),
            ).fetchone()
        if row is None:
            raise RuntimeError("Não foi possível persistir o item da outbox fiscal.")
        result = FiscalOutboxService._row_dict(connection, row)
        if fiscal_document_id:
            connection.execute(
                """UPDATE fiscal_sale_documents
                      SET queue_id=?,status='ENFILEIRADO',last_error='',updated_at=?
                    WHERE id=?""",
                (str(result["id"]), now, int(fiscal_document_id)),
            )
        return result

    def list_items(self, *, status: str = "") -> list[dict[str, Any]]:
        connection = self.connection_factory()
        try:
            self.ensure_schema(connection)
            self.migrate_legacy_in_transaction(connection)
            sql = "SELECT * FROM fiscal_outbox"
            params: tuple[Any, ...] = ()
            if status:
                sql += " WHERE status=?"
                params = (str(status).upper(),)
            rows = connection.execute(sql + " ORDER BY created_at,id", params).fetchall()
            connection.commit()
            return [self._row_dict(connection, row) for row in rows]
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def enqueue_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        connection = self.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self.ensure_schema(connection)
            key = str(record.get("access_key") or "")
            document = None
            if self._table_exists(connection, "fiscal_sale_documents"):
                columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(fiscal_sale_documents)")}
                required = {"id", "sale_id", "environment", "model", "reservation_id", "access_key"}
                if required.issubset(columns):
                    document = connection.execute(
                        "SELECT id,sale_id,environment,model,reservation_id FROM fiscal_sale_documents WHERE access_key=?",
                        (key,),
                    ).fetchone()
            result = self.enqueue_in_transaction(
                connection, sale_id=int(document[1]) if document else None,
                fiscal_document_id=int(document[0]) if document else None,
                access_key=key,
                environment=str((document[2] if document else record.get("environment")) or "HOMOLOGACAO"),
                operation=str(record.get("operation") or ""),
                model=str((document[3] if document else record.get("model")) or "55"),
                reservation_id=str((document[4] if document else record.get("reservation_id")) or ""),
                xml_b64=str(record.get("xml_b64") or ""),
                original_xml_b64=str(record.get("original_xml_b64") or ""),
                actor=str(record.get("actor") or ""),
                max_attempts=int(record.get("max_attempts") or 5),
                retry_minutes=int(record.get("retry_minutes") or 5),
                contingency=bool(record.get("contingency")),
                contingency_deadline_at=str(record.get("contingency_deadline_at") or ""),
                legacy_id=str(record.get("legacy_id") or ""),
                created_at=str(record.get("created_at") or ""), metadata=dict(record),
            )
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def save_records(self, records: list[Mapping[str, Any]]) -> None:
        connection = self.connection_factory()
        now = datetime.now(timezone.utc).isoformat()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self.ensure_schema(connection)
            for record in records:
                connection.execute(
                    """UPDATE fiscal_outbox SET operation=?,status=?,attempts=?,max_attempts=?,
                           retry_minutes=?,next_attempt_at=?,worker_id=?,claimed_at=?,lease_until=?,
                           receipt=?,last_error_code=?,last_error_message=?,xml_b64=?,
                           original_xml_b64=?,contingency=?,contingency_deadline_at=?,metadata_json=?,updated_at=?
                         WHERE id=?""",
                    (str(record.get("operation") or ""), str(record.get("status") or "PENDENTE").upper(),
                     int(record.get("attempts") or 0), int(record.get("max_attempts") or 5),
                     int(record.get("retry_minutes") or 5), str(record.get("next_attempt_at") or ""),
                     str(record.get("worker_id") or ""), record.get("claimed_at"), record.get("lease_until"),
                     str(record.get("receipt") or ""), str(record.get("last_status_code") or record.get("last_error_code") or ""),
                     str(record.get("last_error") or record.get("last_error_message") or record.get("last_message") or ""),
                     str(record.get("xml_b64") or ""), str(record.get("original_xml_b64") or ""),
                     1 if record.get("contingency") else 0, str(record.get("contingency_deadline_at") or ""),
                     json.dumps(dict(record), ensure_ascii=False, sort_keys=True, default=str),
                     now, int(record["id"])),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def save_claimed_record(self, record: Mapping[str, Any], *, worker_id: str,
                            finish: bool) -> dict[str, Any]:
        """Salva somente se o claim ainda pertence ao worker informado."""
        connection = self.connection_factory()
        now = datetime.now(timezone.utc).isoformat()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self.ensure_schema(connection)
            changed = connection.execute(
                """UPDATE fiscal_outbox SET operation=?,status=?,attempts=?,max_attempts=?,
                       retry_minutes=?,next_attempt_at=?,worker_id=?,claimed_at=?,
                       lease_until=CASE WHEN ?=1 THEN NULL ELSE lease_until END,
                       receipt=?,last_error_code=?,last_error_message=?,xml_b64=?,
                       original_xml_b64=?,contingency=?,contingency_deadline_at=?,
                       metadata_json=?,updated_at=?
                     WHERE id=? AND status='PROCESSANDO' AND worker_id=?""",
                (
                    str(record.get("operation") or ""),
                    (str(record.get("status") or "PROCESSANDO").upper() if finish else "PROCESSANDO"),
                    int(record.get("attempts") or 0), int(record.get("max_attempts") or 5),
                    int(record.get("retry_minutes") or 5), str(record.get("next_attempt_at") or ""),
                    "" if finish else str(worker_id),
                    None if finish else record.get("claimed_at"),
                    1 if finish else 0,
                    str(record.get("receipt") or ""),
                    str(record.get("last_status_code") or record.get("last_error_code") or ""),
                    str(record.get("last_error") or record.get("last_error_message") or record.get("last_message") or ""),
                    str(record.get("xml_b64") or ""), str(record.get("original_xml_b64") or ""),
                    1 if record.get("contingency") else 0,
                    str(record.get("contingency_deadline_at") or ""),
                    json.dumps(dict(record), ensure_ascii=False, sort_keys=True, default=str),
                    now, int(record["id"]), str(worker_id),
                ),
            ).rowcount
            if changed != 1:
                raise ValueError("O claim fiscal não pertence mais a este worker.")
            result = self._by_id(connection, int(record["id"]))
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def renew_lease(self, item_id: int, *, worker_id: str, lease_seconds: int = 120,
                    now: datetime | None = None) -> dict[str, Any] | None:
        """Renova um claim ativo somente quando o worker ainda é seu proprietário."""
        owner = str(worker_id or "").strip()
        if not owner:
            raise ValueError("Identificação do worker é obrigatória.")
        current = self._utc(now)
        lease_until = (current + timedelta(seconds=max(1, int(lease_seconds)))).isoformat()
        connection = self.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self.ensure_schema(connection)
            changed = connection.execute(
                """UPDATE fiscal_outbox
                      SET lease_until=?,updated_at=?
                    WHERE id=? AND status='PROCESSANDO' AND worker_id=?""",
                (lease_until, current.isoformat(), int(item_id), owner),
            ).rowcount
            if changed != 1:
                connection.rollback()
                return None
            result = self._by_id(connection, int(item_id))
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def claim_next(self, *, worker_id: str, lease_seconds: int = 120,
                   now: datetime | None = None,
                   operations: tuple[str, ...] = ("autorizacao", "recibo")) -> dict[str, Any] | None:
        if not str(worker_id or "").strip():
            raise ValueError("Identificação do worker é obrigatória.")
        current = self._utc(now)
        connection = self.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self.ensure_schema(connection)
            expired = connection.execute(
                """SELECT id,metadata_json FROM fiscal_outbox
                     WHERE status='PROCESSANDO' AND lease_until IS NOT NULL AND lease_until<=?""",
                (current.isoformat(),),
            ).fetchall()
            for item_id, metadata_json in expired:
                try:
                    metadata = json.loads(str(metadata_json or "{}"))
                except (TypeError, ValueError):
                    metadata = {}
                uncertain = bool(metadata.get("transmission_started_at"))
                connection.execute(
                    """UPDATE fiscal_outbox
                          SET status=?,worker_id='',claimed_at=NULL,lease_until=NULL,
                              next_attempt_at=?,last_error_message=?,updated_at=? WHERE id=?""",
                    (
                        "RESPOSTA_DESCONHECIDA" if uncertain else "PENDENTE",
                        "" if uncertain else current.isoformat(),
                        ("Lease venceu após início da transmissão; reconciliação obrigatória."
                         if uncertain else ""),
                        current.isoformat(), int(item_id),
                    ),
                )
            allowed = tuple(str(value).lower() for value in operations if str(value).strip())
            if not allowed:
                connection.commit()
                return None
            placeholders = ",".join("?" for _ in allowed)
            row = connection.execute(
                f"""SELECT id FROM fiscal_outbox
                    WHERE status IN ('PENDENTE','ERRO')
                      AND operation IN ({placeholders})
                      AND (next_attempt_at IS NULL OR next_attempt_at='' OR next_attempt_at<=?)
                    ORDER BY created_at,id LIMIT 1""",
                (*allowed, current.isoformat()),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            item_id = int(row[0])
            lease_until = (current + timedelta(seconds=max(1, int(lease_seconds)))).isoformat()
            changed = connection.execute(
                """UPDATE fiscal_outbox
                      SET status='PROCESSANDO',worker_id=?,claimed_at=?,lease_until=?,
                          attempts=attempts+1,updated_at=?
                    WHERE id=? AND status IN ('PENDENTE','ERRO')""",
                (str(worker_id).strip(), current.isoformat(), lease_until,
                 current.isoformat(), item_id),
            ).rowcount
            if changed != 1:
                connection.rollback()
                return None
            result = self._by_id(connection, item_id)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def claim_item(self, item_id: int, *, worker_id: str, lease_seconds: int = 120,
                   now: datetime | None = None) -> dict[str, Any] | None:
        """Reivindica um item específico sem permitir furar claim de outra instância."""
        if not str(worker_id or "").strip():
            raise ValueError("Identificação do worker é obrigatória.")
        current = self._utc(now)
        connection = self.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self.ensure_schema(connection)
            lease_until = (current + timedelta(seconds=max(1, int(lease_seconds)))).isoformat()
            changed = connection.execute(
                """UPDATE fiscal_outbox
                      SET status='PROCESSANDO',worker_id=?,claimed_at=?,lease_until=?,
                          attempts=attempts+1,updated_at=?
                    WHERE id=? AND status IN ('PENDENTE','ERRO')
                      AND (next_attempt_at IS NULL OR next_attempt_at='' OR next_attempt_at<=?)""",
                (str(worker_id).strip(), current.isoformat(), lease_until,
                 current.isoformat(), int(item_id), current.isoformat()),
            ).rowcount
            if changed != 1:
                connection.rollback()
                return None
            result = self._by_id(connection, int(item_id))
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def claim_unknown(self, *, worker_id: str, lease_seconds: int = 120,
                      now: datetime | None = None) -> dict[str, Any] | None:
        """Reivindica incerteza somente para consulta, nunca para retransmissão."""
        if not str(worker_id or "").strip():
            raise ValueError("Identificação do worker é obrigatória.")
        current = self._utc(now)
        connection = self.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self.ensure_schema(connection)
            row = connection.execute(
                """SELECT id FROM fiscal_outbox
                    WHERE status='RESPOSTA_DESCONHECIDA'
                      AND operation IN ('autorizacao','recibo','consulta')
                      AND (next_attempt_at IS NULL OR next_attempt_at='' OR next_attempt_at<=?)
                    ORDER BY updated_at,id LIMIT 1""",
                (current.isoformat(),),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            item_id = int(row[0])
            lease_until = (current + timedelta(seconds=max(1, int(lease_seconds)))).isoformat()
            changed = connection.execute(
                """UPDATE fiscal_outbox
                      SET status='PROCESSANDO',worker_id=?,claimed_at=?,lease_until=?,
                          attempts=attempts+1,updated_at=?
                    WHERE id=? AND status='RESPOSTA_DESCONHECIDA'""",
                (str(worker_id).strip(), current.isoformat(), lease_until,
                 current.isoformat(), item_id),
            ).rowcount
            if changed != 1:
                connection.rollback()
                return None
            result = self._by_id(connection, item_id)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def await_credential(self, item_id: int, *, worker_id: str,
                         retry_at: datetime, preserve_unknown: bool = False) -> dict[str, Any]:
        return self._finish_claim(
            item_id, worker_id=worker_id,
            status="RESPOSTA_DESCONHECIDA" if preserve_unknown else "ERRO",
            next_attempt_at=self._utc(retry_at).isoformat(),
            error_code="AGUARDANDO_CREDENCIAL",
            error_message="Certificado A1 aguarda credencial segura do Windows.",
        )

    def block_production(self, item_id: int, *, worker_id: str) -> dict[str, Any]:
        return self._finish_claim(
            item_id, worker_id=worker_id, status="FALHA", next_attempt_at="",
            error_code="PRODUCAO_BLOQUEADA",
            error_message="Produção fiscal permanece bloqueada nesta versão.",
        )

    def reschedule(self, item_id: int, *, worker_id: str, next_attempt_at: datetime,
                   error_code: str = "", error_message: str = "") -> dict[str, Any]:
        return self._finish_claim(
            item_id, worker_id=worker_id, status="ERRO",
            next_attempt_at=self._utc(next_attempt_at).isoformat(),
            error_code=error_code, error_message=error_message,
        )

    def mark_unknown(self, item_id: int, *, worker_id: str,
                     error_code: str = "", error_message: str = "") -> dict[str, Any]:
        return self._finish_claim(
            item_id, worker_id=worker_id, status="RESPOSTA_DESCONHECIDA",
            next_attempt_at="", error_code=error_code, error_message=error_message,
        )

    def complete(self, item_id: int, *, worker_id: str, receipt: str = "") -> dict[str, Any]:
        return self._finish_claim(
            item_id, worker_id=worker_id, status="CONCLUIDO",
            next_attempt_at="", receipt=receipt,
        )

    def migrate_legacy(self) -> dict[str, int]:
        connection = self.connection_factory()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self.ensure_schema(connection)
            result = self.migrate_legacy_in_transaction(connection)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @classmethod
    def migrate_legacy_in_transaction(cls, connection: Any) -> dict[str, int]:
        if not cls._table_exists(connection, "fiscal_outbox"):
            return {"found": 0, "migrated": 0, "preserved": 0}
        row = connection.execute(
            "SELECT valor FROM configuracoes WHERE chave=?", (cls.LEGACY_KEY,)
        ).fetchone()
        try:
            records = json.loads(str(row[0])) if row and row[0] else []
        except (TypeError, ValueError):
            records = []
        if not isinstance(records, list):
            records = []
        migrated = 0
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            legacy_id = str(record.get("id") or f"legacy-{index}")
            if connection.execute(
                "SELECT 1 FROM fiscal_outbox WHERE legacy_id=?", (legacy_id,)
            ).fetchone():
                continue
            key = str(record.get("access_key") or "")
            document = connection.execute(
                "SELECT id,sale_id,environment,model,reservation_id FROM fiscal_sale_documents WHERE access_key=?",
                (key,),
            ).fetchone() if cls._table_exists(connection, "fiscal_sale_documents") else None
            fiscal_document_id = int(document[0]) if document else None
            sale_id = int(document[1]) if document else None
            status = str(record.get("status") or "PENDENTE").upper()
            if status == "PROCESSANDO":
                status = "PENDENTE"
            now = str(record.get("created_at") or datetime.now(timezone.utc).isoformat())
            connection.execute(
                """INSERT OR IGNORE INTO fiscal_outbox
                   (sale_id,fiscal_document_id,access_key,environment,operation,status,attempts,
                    max_attempts,retry_minutes,next_attempt_at,receipt,last_error_code,
                    last_error_message,model,reservation_id,xml_b64,original_xml_b64,actor,
                    contingency,contingency_deadline_at,legacy_id,metadata_json,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    sale_id, fiscal_document_id, key,
                    str((document[2] if document else record.get("environment")) or "HOMOLOGACAO"),
                    str(record.get("operation") or "autorizacao").lower(), status,
                    int(record.get("attempts") or 0), int(record.get("max_attempts") or 5),
                    int(record.get("retry_minutes") or 5), str(record.get("next_attempt_at") or now),
                    str(record.get("receipt") or ""), str(record.get("last_status_code") or ""),
                    str(record.get("last_error") or record.get("last_message") or ""),
                    str((document[3] if document else record.get("model")) or "55"),
                    str((document[4] if document else record.get("reservation_id")) or ""),
                    str(record.get("xml_b64") or ""), str(record.get("original_xml_b64") or ""),
                    str(record.get("actor") or ""), 1 if record.get("contingency") else 0,
                    str(record.get("contingency_deadline_at") or ""), legacy_id,
                    json.dumps(record, ensure_ascii=False, sort_keys=True, default=str), now,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            migrated += int(connection.execute("SELECT changes()").fetchone()[0] > 0)
        report = {"found": len(records), "migrated": migrated, "preserved": len(records)}
        connection.execute(
            "INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES(?,?)",
            (cls.MIGRATION_KEY, json.dumps(report, sort_keys=True)),
        )
        return report

    def _finish_claim(self, item_id: int, *, worker_id: str, status: str,
                      next_attempt_at: str, receipt: str = "", error_code: str = "",
                      error_message: str = "") -> dict[str, Any]:
        connection = self.connection_factory()
        now = datetime.now(timezone.utc).isoformat()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self.ensure_schema(connection)
            changed = connection.execute(
                """UPDATE fiscal_outbox SET status=?,next_attempt_at=?,receipt=?,
                       last_error_code=?,last_error_message=?,worker_id='',claimed_at=NULL,
                       lease_until=NULL,updated_at=?
                     WHERE id=? AND status='PROCESSANDO' AND worker_id=?""",
                (status, next_attempt_at, receipt, error_code, error_message, now,
                 int(item_id), str(worker_id)),
            ).rowcount
            if changed != 1:
                raise ValueError("O item não está reivindicado por este worker.")
            result = self._by_id(connection, int(item_id))
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @classmethod
    def _by_id(cls, connection: Any, item_id: int) -> dict[str, Any]:
        row = connection.execute("SELECT * FROM fiscal_outbox WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise ValueError("Item da outbox fiscal não encontrado.")
        return cls._row_dict(connection, row)

    @staticmethod
    def _row_dict(connection: Any, row: Any) -> dict[str, Any]:
        names = [column[1] for column in connection.execute("PRAGMA table_info(fiscal_outbox)")]
        result = dict(zip(names, row))
        try:
            metadata = json.loads(str(result.get("metadata_json") or "{}"))
        except (TypeError, ValueError):
            metadata = {}
        if isinstance(metadata, dict):
            metadata.update(result)
            result = metadata
        result["id"] = str(result["id"])
        result["last_error"] = str(result.get("last_error_message") or "")
        result["last_status_code"] = str(result.get("last_error_code") or "")
        result["last_message"] = str(result.get("last_error_message") or "")
        result["contingency"] = bool(result.get("contingency"))
        return result

    @staticmethod
    def _table_exists(connection: Any, name: str) -> bool:
        return bool(connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone())

    @staticmethod
    def _utc(value: datetime | None) -> datetime:
        current = value or datetime.now(timezone.utc)
        return current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)
