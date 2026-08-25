from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable


_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class TransportError(RuntimeError):
    """Falha definida: o transporte não aceitou a entrega."""


class TransportCollisionError(TransportError):
    """O destino já contém conteúdo incompatível com a mesma chave."""


class TransportUncertainError(RuntimeError):
    """Falha ambígua: não é seguro repetir antes de consultar."""


@dataclass(frozen=True, slots=True)
class TransportReceipt:
    reference: str
    package_sha256: str
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class ReceiptQuery:
    status: str
    receipt: TransportReceipt | None = None


@runtime_checkable
class AccountantDeliveryTransport(Protocol):
    transport_id: str
    binding_fingerprint: str

    def send(
        self,
        *,
        idempotency_key: str,
        package_path: str,
        package_sha256: str,
    ) -> TransportReceipt: ...

    def query_receipt(
        self,
        *,
        reference: str,
        package_sha256: str,
    ) -> ReceiptQuery: ...


class LocalFolderAccountantTransport:
    """Entrega atômica em pasta local ou já sincronizada, sem rede própria."""

    transport_id = "LOCAL_FOLDER_V1"

    def __init__(self, destination: str | Path) -> None:
        self.destination = Path(destination).expanduser().resolve()
        canonical_destination = os.path.normcase(str(self.destination))
        binding = f"{self.transport_id}\0{canonical_destination}".encode("utf-8")
        self.binding_fingerprint = hashlib.sha256(binding).hexdigest()

    @staticmethod
    def _key(value: str) -> str:
        key = str(value or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,127}", key):
            raise TransportError("Chave idempotente inválida para o transporte local.")
        return key

    @staticmethod
    def _expected_sha256(value: str) -> str:
        digest = str(value or "").strip()
        if not _SHA256_PATTERN.fullmatch(digest):
            raise TransportError("SHA-256 do pacote inválido.")
        return digest

    @staticmethod
    def _sha(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _paths(self, reference: str) -> tuple[Path, Path]:
        key = self._key(reference)
        return (
            self.destination / f"{key}.zip",
            self.destination / f"{key}.receipt.json",
        )

    def _receipt_bytes(self, *, reference: str, package_sha256: str) -> bytes:
        payload = {
            "layout": "nabicode.accountant-delivery-receipt.v1",
            "reference": reference,
            "package_sha256": package_sha256,
            "transport_id": self.transport_id,
            "transport_binding": self.binding_fingerprint,
            "receipt_created_at": datetime.now(timezone.utc).isoformat(),
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _temporary_for(target: Path) -> Path:
        return target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")

    @staticmethod
    def _publish_without_overwrite(temporary: Path, target: Path) -> None:
        """Publica no mesmo volume de forma atômica e sem substituir destino."""
        try:
            os.link(temporary, target)
        except FileExistsError:
            raise
        except OSError:
            if os.name != "nt":
                raise TransportError(
                    "O destino não oferece publicação atômica segura sem sobrescrita."
                )
            os.rename(temporary, target)
        else:
            temporary.unlink()

    @staticmethod
    def _write_temporary(path: Path, content: bytes) -> None:
        with path.open("xb") as writer:
            writer.write(content)
            writer.flush()
            os.fsync(writer.fileno())

    def send(
        self,
        *,
        idempotency_key: str,
        package_path: str,
        package_sha256: str,
    ) -> TransportReceipt:
        key = self._key(idempotency_key)
        expected_hash = self._expected_sha256(package_sha256)
        source = Path(package_path).resolve()
        if not self.destination.is_dir():
            raise TransportError(
                "A pasta de entrega configurada não existe ou não é uma pasta."
            )
        if not source.is_file() or self._sha(source) != expected_hash:
            raise TransportError("O pacote preparado está ausente ou foi alterado.")

        target, receipt_path = self._paths(key)
        if target.exists() or receipt_path.exists():
            query = self.query_receipt(reference=key, package_sha256=expected_hash)
            if query.status == "CONFIRMED" and query.receipt is not None:
                return query.receipt
            if query.status == "UNKNOWN":
                raise TransportUncertainError(
                    "Resultado local incerto; consulte antes de repetir."
                )
            raise TransportCollisionError(
                "Já existe uma entrega incompatível para esta chave."
            )

        temporary = self._temporary_for(target)
        receipt_tmp = self._temporary_for(receipt_path)
        target_published = False
        try:
            with source.open("rb") as reader, temporary.open("xb") as writer:
                shutil.copyfileobj(reader, writer, 1024 * 1024)
                writer.flush()
                os.fsync(writer.fileno())
            if self._sha(temporary) != expected_hash:
                raise TransportError("A cópia local divergiu do pacote preparado.")
            try:
                self._publish_without_overwrite(temporary, target)
            except FileExistsError:
                query = self.query_receipt(reference=key, package_sha256=expected_hash)
                if query.status == "CONFIRMED" and query.receipt is not None:
                    return query.receipt
                raise TransportCollisionError(
                    "Já existe uma entrega incompatível para esta chave."
                )
            target_published = True

            raw_receipt = self._receipt_bytes(
                reference=key,
                package_sha256=expected_hash,
            )
            self._write_temporary(receipt_tmp, raw_receipt)
            try:
                self._publish_without_overwrite(receipt_tmp, receipt_path)
            except FileExistsError:
                query = self.query_receipt(reference=key, package_sha256=expected_hash)
                if query.status == "CONFIRMED" and query.receipt is not None:
                    return query.receipt
                raise TransportCollisionError(
                    "Já existe um recibo incompatível para esta chave."
                )
            return TransportReceipt(
                key,
                expected_hash,
                hashlib.sha256(raw_receipt).hexdigest(),
            )
        except TransportCollisionError:
            raise
        except TransportUncertainError:
            raise
        except TransportError as exc:
            if target_published:
                raise TransportUncertainError(
                    "Resultado local incerto; consulte antes de repetir."
                ) from exc
            raise
        except Exception as exc:
            if target_published:
                raise TransportUncertainError(
                    "Resultado local incerto; consulte antes de repetir."
                ) from exc
            raise TransportError("A pasta local recusou a entrega.") from exc
        finally:
            temporary.unlink(missing_ok=True)
            receipt_tmp.unlink(missing_ok=True)

    def _read_receipt(
        self,
        *,
        reference: str,
        package_sha256: str,
        target: Path,
        receipt_path: Path,
    ) -> ReceiptQuery:
        try:
            raw = receipt_path.read_bytes()
            payload = json.loads(raw)
            target_hash = self._sha(target)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return ReceiptQuery("MISMATCH")
        expected_fields = {
            "layout",
            "reference",
            "package_sha256",
            "transport_id",
            "transport_binding",
            "receipt_created_at",
        }
        if not isinstance(payload, dict) or set(payload) != expected_fields:
            return ReceiptQuery("MISMATCH")
        try:
            created_at = datetime.fromisoformat(str(payload["receipt_created_at"]))
        except (TypeError, ValueError):
            return ReceiptQuery("MISMATCH")
        if created_at.tzinfo is None:
            return ReceiptQuery("MISMATCH")
        if (
            payload.get("layout") != "nabicode.accountant-delivery-receipt.v1"
            or payload.get("reference") != reference
            or payload.get("package_sha256") != package_sha256
            or payload.get("transport_id") != self.transport_id
            or payload.get("transport_binding") != self.binding_fingerprint
            or target_hash != package_sha256
        ):
            return ReceiptQuery("MISMATCH")
        return ReceiptQuery(
            "CONFIRMED",
            TransportReceipt(
                reference,
                package_sha256,
                hashlib.sha256(raw).hexdigest(),
            ),
        )

    def query_receipt(
        self,
        *,
        reference: str,
        package_sha256: str,
    ) -> ReceiptQuery:
        key = self._key(reference)
        expected_hash = self._expected_sha256(package_sha256)
        target, receipt_path = self._paths(key)
        try:
            target_exists = target.exists()
            receipt_exists = receipt_path.exists()
        except OSError:
            return ReceiptQuery("UNKNOWN")
        if not target_exists and not receipt_exists:
            return ReceiptQuery("NOT_FOUND")
        if not target.is_file():
            return ReceiptQuery("MISMATCH")
        if receipt_exists and not receipt_path.is_file():
            return ReceiptQuery("MISMATCH")

        if not receipt_exists:
            try:
                if self._sha(target) != expected_hash:
                    return ReceiptQuery("MISMATCH")
                raw_receipt = self._receipt_bytes(
                    reference=key,
                    package_sha256=expected_hash,
                )
                temporary = self._temporary_for(receipt_path)
                try:
                    self._write_temporary(temporary, raw_receipt)
                    try:
                        self._publish_without_overwrite(temporary, receipt_path)
                    except FileExistsError:
                        pass
                finally:
                    temporary.unlink(missing_ok=True)
            except (OSError, TransportError):
                return ReceiptQuery("UNKNOWN")

        return self._read_receipt(
            reference=key,
            package_sha256=expected_hash,
            target=target,
            receipt_path=receipt_path,
        )
