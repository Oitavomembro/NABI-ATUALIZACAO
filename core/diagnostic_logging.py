from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path


_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)\b(senha|password|token|api[_-]?key|chave privada)\b\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.DOTALL),
)


def redact_sensitive(value: object) -> str:
    text = str(value)
    for pattern in _SENSITIVE_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}=<omitido>" if match.lastindex else "<chave privada omitida>", text)
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original_message, original_args = record.msg, record.args
        try:
            record.msg = redact_sensitive(record.getMessage())
            record.args = ()
            return super().format(record)
        finally:
            record.msg, record.args = original_message, original_args

    def formatException(self, exc_info) -> str:
        return redact_sensitive(super().formatException(exc_info))


class SafeRotatingFileHandler(RotatingFileHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except Exception:
            return


def configure_diagnostic_logging(
    logger: logging.Logger,
    log_file: str | Path,
    *,
    app_version: str,
    runtime_profile: str,
    max_bytes: int = 2 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Handler:
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = SafeRotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(
        RedactingFormatter(
            f"%(asctime)s | %(levelname)s | versao={app_version} | perfil={runtime_profile} | modulo=%(name)s | %(message)s"
        )
    )
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return handler
