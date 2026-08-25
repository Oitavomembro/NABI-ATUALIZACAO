from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from services.accountant_delivery_transport import (
    AccountantDeliveryTransport,
    ReceiptQuery,
    TransportCollisionError,
    TransportError,
    TransportReceipt,
    TransportUncertainError,
)
from services.accountant_monthly_package_service import AccountantMonthlyPackageService


_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class AccountantDeliveryRecord:
    idempotency_key: str
    status: str
    cnpj: str
    competence: str
    profile: str
    package_sha256: str
    manifest_sha256: str
    recipient_hash: str
    cnpj_confirmed_at: str
    consent_confirmed_at: str
    transport_id: str
    transport_binding: str
    attempts: int
    transport_reference: str
    receipt_sha256: str
    last_error_code: str


class AccountantDeliveryService:
    """Outbox contábil durável; envio e recebimento nunca são confundidos."""

    STATES = {
        "PREPARADO",
        "ENFILEIRADO",
        "ENVIADO_AO_TRANSPORTE",
        "RECEBIDO_CONFIRMADO",
        "FALHA",
        "DESCONHECIDO",
    }
    QUERY_STATES = {"CONFIRMED", "NOT_FOUND", "MISMATCH", "UNKNOWN"}

    def __init__(
        self,
        *,
        outbox_path: str | Path,
        spool_dir: str | Path,
        transport: AccountantDeliveryTransport,
    ) -> None:
        self.outbox_path = Path(outbox_path).expanduser().resolve()
        self.spool_dir = Path(spool_dir).expanduser().resolve()
        self.transport = transport
        self.transport_id = self._transport_id(transport)
        self.transport_binding = self._transport_binding(transport)
        self.outbox_path.parent.mkdir(parents=True, exist_ok=True)
        self.spool_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @staticmethod
    def _transport_id(transport: AccountantDeliveryTransport) -> str:
        value = str(getattr(transport, "transport_id", "") or "").strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", value):
            raise ValueError("Identificador do transporte contábil inválido.")
        return value

    @staticmethod
    def _transport_binding(transport: AccountantDeliveryTransport) -> str:
        value = str(getattr(transport, "binding_fingerprint", "") or "").strip()
        if not _SHA256_PATTERN.fullmatch(value):
            raise ValueError("Vínculo da configuração do transporte é inválido.")
        return value

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.outbox_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _ensure_schema(self) -> None:
        states = ",".join(f"'{state}'" for state in sorted(self.STATES))
        with self._connect() as connection:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS accountant_delivery_outbox(
                    idempotency_key TEXT PRIMARY KEY,
                    operation_fingerprint TEXT NOT NULL,
                    package_path TEXT NOT NULL,
                    package_sha256 TEXT NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    cnpj TEXT NOT NULL,
                    competence TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    recipient_hash TEXT NOT NULL,
                    cnpj_confirmed_at TEXT NOT NULL,
                    consent_confirmed_at TEXT NOT NULL,
                    transport_id TEXT NOT NULL,
                    transport_binding TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ({states})),
                    attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
                    transport_reference TEXT NOT NULL DEFAULT '',
                    receipt_sha256 TEXT NOT NULL DEFAULT '',
                    last_error_code TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _sha(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _manifest(path: Path) -> tuple[dict[str, object], str]:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read("manifesto.json")
        manifest = json.loads(raw)
        if not isinstance(manifest, dict):
            raise ValueError("Manifesto do pacote contábil inválido.")
        return manifest, hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _key(value: object) -> str:
        key = str(value or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", key):
            raise ValueError("Chave idempotente inválida.")
        return key

    @staticmethod
    def _recipient(value: object) -> str:
        recipient = unicodedata.normalize("NFKC", str(value or "")).strip()
        if not recipient or len(recipient) > 200:
            raise ValueError("Informe um destinatário/contador válido.")
        if any(unicodedata.category(character).startswith("C") for character in recipient):
            raise ValueError("Informe um destinatário/contador válido.")
        return " ".join(recipient.split())

    def _snapshot(self, source: Path) -> tuple[Path, str, dict[str, object], str]:
        if not source.is_file():
            raise ValueError("Pacote mensal não encontrado.")
        temporary = self.spool_dir / (
            f".accounting-package.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with source.open("rb") as reader, temporary.open("xb") as writer:
                shutil.copyfileobj(reader, writer, 1024 * 1024)
                writer.flush()
                os.fsync(writer.fileno())
            package_hash = self._sha(temporary)
            AccountantMonthlyPackageService.validate(temporary)
            manifest, manifest_hash = self._manifest(temporary)
            snapshot = self.spool_dir / f"{package_hash}.zip"
            if snapshot.exists():
                if not snapshot.is_file() or self._sha(snapshot) != package_hash:
                    raise RuntimeError("Colisão no spool de pacotes.")
            else:
                os.replace(temporary, snapshot)
            if self._sha(snapshot) != package_hash:
                raise RuntimeError("Snapshot do pacote divergiu da origem validada.")
            return snapshot, package_hash, manifest, manifest_hash
        finally:
            temporary.unlink(missing_ok=True)

    def prepare(
        self,
        *,
        package_path: str | Path,
        recipient: str,
        cnpj: str,
        cnpj_confirmed: bool,
        consent: bool,
        competence: str,
        profile: str,
        idempotency_key: str,
    ) -> AccountantDeliveryRecord:
        key = self._key(idempotency_key)
        recipient_value = self._recipient(recipient)
        if cnpj_confirmed is not True:
            raise ValueError("Confirme explicitamente o CNPJ da empresa.")
        if consent is not True:
            raise ValueError("O consentimento explícito para entrega é obrigatório.")
        source = Path(package_path).expanduser().resolve()
        expected_cnpj, expected_competence, expected_profile, _ = (
            AccountantMonthlyPackageService.normalize_request(
                cnpj=cnpj,
                competence=competence,
                profile=profile,
                output_path=source,
            )
        )
        snapshot, package_hash, manifest, manifest_hash = self._snapshot(source)
        if (
            manifest.get("cnpj"),
            manifest.get("competence"),
            manifest.get("profile"),
        ) != (expected_cnpj, expected_competence, expected_profile):
            raise ValueError(
                "CNPJ, competência ou perfil divergem do manifesto validado."
            )

        recipient_hash = hashlib.sha256(
            recipient_value.casefold().encode("utf-8")
        ).hexdigest()
        payload = {
            "package_sha256": package_hash,
            "manifest_sha256": manifest_hash,
            "cnpj": expected_cnpj,
            "competence": expected_competence,
            "profile": expected_profile,
            "recipient_hash": recipient_hash,
            "cnpj_confirmed": True,
            "consent_confirmed": True,
            "transport_id": self.transport_id,
            "transport_binding": self.transport_binding,
        }
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        now = self._now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM accountant_delivery_outbox WHERE idempotency_key=?",
                (key,),
            ).fetchone()
            if row is not None:
                if row["operation_fingerprint"] != fingerprint:
                    raise ValueError("Chave idempotente já usada para outra entrega.")
                return self._record(row)
            connection.execute(
                """
                INSERT INTO accountant_delivery_outbox(
                    idempotency_key, operation_fingerprint, package_path,
                    package_sha256, manifest_sha256, cnpj, competence, profile,
                    recipient_hash, cnpj_confirmed_at, consent_confirmed_at,
                    transport_id, transport_binding, status,
                    attempts, transport_reference, receipt_sha256,
                    last_error_code, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'PREPARADO',0,'','','',?,?)
                """,
                (
                    key,
                    fingerprint,
                    str(snapshot),
                    package_hash,
                    manifest_hash,
                    expected_cnpj,
                    expected_competence,
                    expected_profile,
                    recipient_hash,
                    now,
                    now,
                    self.transport_id,
                    self.transport_binding,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM accountant_delivery_outbox WHERE idempotency_key=?",
                (key,),
            ).fetchone()
            return self._record(row)

    def enqueue(self, key: str) -> AccountantDeliveryRecord:
        normalized_key = self._key(key)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._required(connection, normalized_key)
            if row["status"] in {
                "ENFILEIRADO",
                "ENVIADO_AO_TRANSPORTE",
                "RECEBIDO_CONFIRMADO",
            }:
                return self._record(row)
            if row["status"] == "DESCONHECIDO":
                raise RuntimeError(
                    "Consulte o transporte antes de repetir uma entrega desconhecida."
                )
            if row["last_error_code"] in {
                "RECEIPT_MISMATCH",
                "DESTINATION_COLLISION",
                "TRANSPORT_PROTOCOL_ERROR",
            }:
                raise RuntimeError(
                    "A divergência do destino exige intervenção antes de nova tentativa."
                )
            connection.execute(
                """
                UPDATE accountant_delivery_outbox
                SET status='ENFILEIRADO', last_error_code='', updated_at=?
                WHERE idempotency_key=?
                """,
                (self._now(), normalized_key),
            )
            return self.get(normalized_key, connection=connection)

    def _configuration_matches(self, row: sqlite3.Row) -> bool:
        return (
            row["transport_id"] == self.transport_id
            and row["transport_binding"] == self.transport_binding
        )

    def dispatch(self, key: str) -> AccountantDeliveryRecord:
        normalized_key = self._key(key)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._required(connection, normalized_key)
            if row["status"] != "ENFILEIRADO":
                return self._record(row)
            if not self._configuration_matches(row):
                self._update(
                    connection,
                    normalized_key,
                    "FALHA",
                    error="TRANSPORT_CONFIGURATION_CHANGED",
                )
                return self.get(normalized_key, connection=connection)
            try:
                package_matches = (
                    self._sha(Path(row["package_path"])) == row["package_sha256"]
                )
            except OSError:
                package_matches = False
            if not package_matches:
                self._update(
                    connection,
                    normalized_key,
                    "FALHA",
                    attempt=True,
                    error="PACKAGE_TAMPERED",
                )
                return self.get(normalized_key, connection=connection)
            try:
                receipt = self.transport.send(
                    idempotency_key=normalized_key,
                    package_path=row["package_path"],
                    package_sha256=row["package_sha256"],
                )
            except TransportUncertainError:
                self._update(
                    connection,
                    normalized_key,
                    "DESCONHECIDO",
                    attempt=True,
                    error="TRANSPORT_UNKNOWN",
                )
                return self.get(normalized_key, connection=connection)
            except TransportCollisionError:
                self._update(
                    connection,
                    normalized_key,
                    "FALHA",
                    attempt=True,
                    error="DESTINATION_COLLISION",
                )
                return self.get(normalized_key, connection=connection)
            except TransportError:
                self._update(
                    connection,
                    normalized_key,
                    "FALHA",
                    attempt=True,
                    error="TRANSPORT_FAILED",
                )
                return self.get(normalized_key, connection=connection)
            except Exception:
                self._update(
                    connection,
                    normalized_key,
                    "DESCONHECIDO",
                    attempt=True,
                    error="TRANSPORT_UNKNOWN",
                )
                return self.get(normalized_key, connection=connection)
            if not self._receipt_is_valid(receipt, row["package_sha256"]):
                self._update(
                    connection,
                    normalized_key,
                    "DESCONHECIDO",
                    attempt=True,
                    error="TRANSPORT_PROTOCOL_ERROR",
                )
                return self.get(normalized_key, connection=connection)
            self._update(
                connection,
                normalized_key,
                "ENVIADO_AO_TRANSPORTE",
                attempt=True,
                reference=receipt.reference,
                receipt=receipt.receipt_sha256,
            )
            return self.get(normalized_key, connection=connection)

    def confirm_receipt(self, key: str) -> AccountantDeliveryRecord:
        normalized_key = self._key(key)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._required(connection, normalized_key)
            if row["status"] == "RECEBIDO_CONFIRMADO":
                return self._record(row)
            if row["status"] not in {"ENVIADO_AO_TRANSPORTE", "DESCONHECIDO"}:
                raise RuntimeError("A entrega ainda não pode ser confirmada.")
            return self._query_and_apply(connection, row)

    def reconcile_unknown(self, key: str) -> AccountantDeliveryRecord:
        normalized_key = self._key(key)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._required(connection, normalized_key)
            if row["status"] != "DESCONHECIDO":
                return self._record(row)
            return self._query_and_apply(connection, row)

    def _query_and_apply(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> AccountantDeliveryRecord:
        if not self._configuration_matches(row):
            self._update(
                connection,
                row["idempotency_key"],
                "FALHA",
                error="TRANSPORT_CONFIGURATION_CHANGED",
            )
            return self.get(row["idempotency_key"], connection=connection)
        reference = row["transport_reference"] or row["idempotency_key"]
        try:
            query = self.transport.query_receipt(
                reference=reference,
                package_sha256=row["package_sha256"],
            )
        except TransportUncertainError:
            self._update(
                connection,
                row["idempotency_key"],
                "DESCONHECIDO",
                error="RECEIPT_QUERY_UNKNOWN",
            )
            return self.get(row["idempotency_key"], connection=connection)
        except TransportError:
            status = (
                "DESCONHECIDO"
                if row["status"] == "DESCONHECIDO"
                else "ENVIADO_AO_TRANSPORTE"
            )
            self._update(
                connection,
                row["idempotency_key"],
                status,
                error="RECEIPT_QUERY_FAILED",
            )
            return self.get(row["idempotency_key"], connection=connection)
        except Exception:
            status = (
                "DESCONHECIDO"
                if row["status"] == "DESCONHECIDO"
                else "ENVIADO_AO_TRANSPORTE"
            )
            self._update(
                connection,
                row["idempotency_key"],
                status,
                error="RECEIPT_QUERY_FAILED",
            )
            return self.get(row["idempotency_key"], connection=connection)
        return self._apply_query(connection, row, query, reference=reference)

    @staticmethod
    def _receipt_is_valid(receipt: object, package_sha256: str) -> bool:
        return (
            isinstance(receipt, TransportReceipt)
            and bool(str(receipt.reference or "").strip())
            and len(str(receipt.reference)) <= 256
            and not any(
                unicodedata.category(character).startswith("C")
                for character in str(receipt.reference)
            )
            and receipt.package_sha256 == package_sha256
            and bool(_SHA256_PATTERN.fullmatch(str(receipt.receipt_sha256 or "")))
        )

    def _apply_query(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        query: ReceiptQuery,
        *,
        reference: str,
    ) -> AccountantDeliveryRecord:
        key = row["idempotency_key"]
        if not isinstance(query, ReceiptQuery) or query.status not in self.QUERY_STATES:
            self._update(
                connection,
                key,
                "DESCONHECIDO",
                error="TRANSPORT_PROTOCOL_ERROR",
            )
        elif query.status == "CONFIRMED":
            receipt = query.receipt
            if (
                not self._receipt_is_valid(receipt, row["package_sha256"])
                or receipt.reference != reference
            ):
                self._update(
                    connection,
                    key,
                    "FALHA",
                    error="RECEIPT_MISMATCH",
                )
            else:
                self._update(
                    connection,
                    key,
                    "RECEBIDO_CONFIRMADO",
                    reference=receipt.reference,
                    receipt=receipt.receipt_sha256,
                )
        elif query.status == "NOT_FOUND" and query.receipt is None:
            self._update(
                connection,
                key,
                "FALHA",
                error="NOT_FOUND_AFTER_QUERY",
            )
        elif query.status == "MISMATCH":
            self._update(
                connection,
                key,
                "FALHA",
                error="RECEIPT_MISMATCH",
            )
        elif query.status == "UNKNOWN" and query.receipt is None:
            self._update(
                connection,
                key,
                "DESCONHECIDO",
                error="TRANSPORT_UNKNOWN",
            )
        else:
            self._update(
                connection,
                key,
                "DESCONHECIDO",
                error="TRANSPORT_PROTOCOL_ERROR",
            )
        return self.get(key, connection=connection)

    def get(
        self,
        key: str,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> AccountantDeliveryRecord:
        normalized_key = self._key(key)
        own_connection = connection is None
        active_connection = connection or self._connect()
        try:
            return self._record(self._required(active_connection, normalized_key))
        finally:
            if own_connection:
                active_connection.close()

    @staticmethod
    def _required(connection: sqlite3.Connection, key: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM accountant_delivery_outbox WHERE idempotency_key=?",
            (key,),
        ).fetchone()
        if row is None:
            raise ValueError("Entrega contábil não encontrada.")
        return row

    def _update(
        self,
        connection: sqlite3.Connection,
        key: str,
        status: str,
        *,
        attempt: bool = False,
        error: str = "",
        reference: str = "",
        receipt: str = "",
    ) -> None:
        if status not in self.STATES:
            raise ValueError("Estado inválido.")
        connection.execute(
            """
            UPDATE accountant_delivery_outbox
            SET status=?, attempts=attempts+?, last_error_code=?,
                transport_reference=CASE WHEN ?<>'' THEN ? ELSE transport_reference END,
                receipt_sha256=CASE WHEN ?<>'' THEN ? ELSE receipt_sha256 END,
                updated_at=?
            WHERE idempotency_key=?
            """,
            (
                status,
                1 if attempt else 0,
                error,
                reference,
                reference,
                receipt,
                receipt,
                self._now(),
                key,
            ),
        )

    def _record(self, row: sqlite3.Row) -> AccountantDeliveryRecord:
        if row["status"] not in self.STATES:
            raise RuntimeError("Estado persistido da entrega contábil é inválido.")
        return AccountantDeliveryRecord(
            idempotency_key=row["idempotency_key"],
            status=row["status"],
            cnpj=row["cnpj"],
            competence=row["competence"],
            profile=row["profile"],
            package_sha256=row["package_sha256"],
            manifest_sha256=row["manifest_sha256"],
            recipient_hash=row["recipient_hash"],
            cnpj_confirmed_at=row["cnpj_confirmed_at"],
            consent_confirmed_at=row["consent_confirmed_at"],
            transport_id=row["transport_id"],
            transport_binding=row["transport_binding"],
            attempts=int(row["attempts"]),
            transport_reference=row["transport_reference"],
            receipt_sha256=row["receipt_sha256"],
            last_error_code=row["last_error_code"],
        )
