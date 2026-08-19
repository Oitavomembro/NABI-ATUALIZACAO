from __future__ import annotations

import json
import re
import smtplib
import ssl
import threading
import uuid
from datetime import datetime
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Callable, Iterable

from services.windows_data_protector import WindowsDataProtector


class FiscalEmailService:
    """Fila local de e-mails fiscais sem persistir a senha em texto aberto."""

    MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
    VALID_SECURITY = {"TLS", "SSL"}

    def __init__(
        self,
        storage_dir: str | Path,
        *,
        secret_protector: Any | None = None,
        smtp_factory: Callable[[str, int, int, bool], Any] | None = None,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.storage_dir / "smtp.json"
        self.secret_path = self.storage_dir / "smtp.secret"
        self.queue_path = self.storage_dir / "queue.json"
        self.secret_protector = secret_protector or WindowsDataProtector()
        self.smtp_factory = smtp_factory or self._default_smtp_factory
        self._lock = threading.RLock()

    def configure(
        self, *, host: str, port: int, username: str, password: str,
        sender: str, security: str = "TLS",
    ) -> dict[str, Any]:
        host = str(host or "").strip()
        username = str(username or "").strip()
        sender = self._valid_email(sender, "remetente")
        security = str(security or "TLS").strip().upper()
        if not host or any(char.isspace() for char in host):
            raise ValueError("Informe um servidor SMTP válido.")
        if not 1 <= int(port) <= 65535:
            raise ValueError("A porta SMTP deve estar entre 1 e 65535.")
        if security not in self.VALID_SECURITY:
            raise ValueError("A segurança SMTP deve ser TLS ou SSL.")
        if not username or not password:
            raise ValueError("Informe o usuário e a senha de aplicativo do e-mail.")
        protected = self.secret_protector.protect(str(password).encode("utf-8"))
        config = {
            "host": host, "port": int(port), "username": username,
            "sender": sender, "security": security,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._atomic_write(self.secret_path, protected)
        try:
            self._atomic_write(
                self.config_path,
                json.dumps(config, ensure_ascii=False, sort_keys=True).encode("utf-8"),
            )
        except Exception:
            self.secret_path.unlink(missing_ok=True)
            raise
        return dict(config)

    def public_config(self) -> dict[str, Any]:
        if not self.config_path.is_file():
            return {}
        try:
            value = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return dict(value) if isinstance(value, dict) else {}

    def remove_config(self) -> None:
        self.config_path.unlink(missing_ok=True)
        self.secret_path.unlink(missing_ok=True)

    def enqueue(
        self, *, recipient: str, subject: str, body: str,
        attachments: Iterable[str | Path], access_key: str = "",
    ) -> dict[str, Any]:
        recipient = self._valid_email(recipient, "destinatário")
        files = tuple(Path(item).resolve() for item in attachments)
        if not files:
            raise ValueError("Inclua o XML autorizado e o documento auxiliar.")
        total = 0
        normalized: list[str] = []
        for path in files:
            if not path.is_file():
                raise ValueError(f"Anexo fiscal não encontrado: {path.name}.")
            size = path.stat().st_size
            if size <= 0:
                raise ValueError(f"Anexo fiscal vazio: {path.name}.")
            total += size
            normalized.append(str(path))
        if total > self.MAX_ATTACHMENT_BYTES:
            raise ValueError("Os anexos fiscais excedem o limite de 15 MB.")
        now = datetime.now().isoformat(timespec="seconds")
        item = {
            "id": uuid.uuid4().hex, "recipient": recipient,
            "subject": str(subject or "Documentos fiscais").strip()[:200],
            "body": str(body or "").strip(), "attachments": normalized,
            "access_key": re.sub(r"\D", "", str(access_key or ""))[:44],
            "status": "PENDENTE", "attempts": 0, "last_error": "",
            "created_at": now, "updated_at": now,
        }
        with self._lock:
            queue = self.list_queue()
            queue.append(item)
            self._save_queue(queue)
        return dict(item)

    def list_queue(self) -> list[dict[str, Any]]:
        if not self.queue_path.is_file():
            return []
        try:
            data = json.loads(self.queue_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        return [dict(item) for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    def process_pending(self, *, limit: int = 20) -> list[dict[str, Any]]:
        config = self.public_config()
        if not config or not self.secret_path.is_file():
            raise ValueError("Configure o servidor de e-mail fiscal antes de enviar.")
        password = self.secret_protector.unprotect(self.secret_path.read_bytes()).decode("utf-8")
        results: list[dict[str, Any]] = []
        with self._lock:
            queue = self.list_queue()
            for item in queue:
                if len(results) >= max(1, int(limit)) or item.get("status") not in {"PENDENTE", "FALHA"}:
                    continue
                item["attempts"] = int(item.get("attempts") or 0) + 1
                item["updated_at"] = datetime.now().isoformat(timespec="seconds")
                try:
                    self._send(item, config, password)
                    item["status"] = "ENVIADO"
                    item["last_error"] = ""
                except Exception as exc:
                    item["status"] = "FALHA"
                    item["last_error"] = str(exc)[:500]
                results.append(dict(item))
                self._save_queue(queue)
        password = ""
        return results

    def _send(self, item: dict[str, Any], config: dict[str, Any], password: str) -> None:
        message = EmailMessage()
        message["From"] = config["sender"]
        message["To"] = item["recipient"]
        message["Subject"] = item["subject"]
        message.set_content(item["body"] or "Seguem os documentos fiscais.")
        for raw_path in item["attachments"]:
            path = Path(raw_path)
            data = path.read_bytes()
            if path.suffix.lower() == ".xml":
                maintype, subtype = "application", "xml"
            elif path.suffix.lower() == ".pdf" and data.startswith(b"%PDF"):
                maintype, subtype = "application", "pdf"
            else:
                raise ValueError(f"Tipo de anexo fiscal não permitido: {path.name}.")
            message.add_attachment(data, maintype=maintype, subtype=subtype, filename=path.name)
        use_ssl = config["security"] == "SSL"
        client = self.smtp_factory(config["host"], int(config["port"]), 30, use_ssl)
        try:
            client.ehlo()
            if not use_ssl:
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            client.login(config["username"], password)
            client.send_message(message)
        finally:
            try:
                client.quit()
            except Exception:
                pass

    @staticmethod
    def _default_smtp_factory(host: str, port: int, timeout: int, use_ssl: bool):
        cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        return cls(host, port, timeout=timeout, context=ssl.create_default_context()) if use_ssl else cls(host, port, timeout=timeout)

    @staticmethod
    def _valid_email(value: str, label: str) -> str:
        address = parseaddr(str(value or "").strip())[1]
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address):
            raise ValueError(f"Informe um e-mail de {label} válido.")
        return address

    def _save_queue(self, queue: list[dict[str, Any]]) -> None:
        self._atomic_write(
            self.queue_path,
            json.dumps(queue, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        )

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
