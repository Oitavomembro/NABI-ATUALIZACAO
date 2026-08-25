from __future__ import annotations

import re
from collections.abc import Mapping

REDACTION_FAILURE = "<conteudo omitido: falha segura de sanitizacao>"

_PATTERNS = (
    (re.compile(r"(?is)-----BEGIN [^-]*(?:PRIVATE KEY|CERTIFICATE)-----.*?-----END [^-]*(?:PRIVATE KEY|CERTIFICATE)-----"), "<material criptografico omitido>"),
    (re.compile(r"(?is)<(?:NFe|nfeProc|CTe|cteProc|enviNFe|retEnviNFe|evento|procEventoNFe)\b.*?</(?:NFe|nfeProc|CTe|cteProc|enviNFe|retEnviNFe|evento|procEventoNFe)>"), "<xml fiscal omitido>"),
    (re.compile(r"(?i)\b(authorization)\b\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"), r"\1=<omitido>"),
    (re.compile(r"(?i)\b(senha|password|token|access[_-]?token|refresh[_-]?token|client[_-]?secret|api[_-]?key|certificate|certificado|private[_-]?key|chave privada)\b\s*[:=]\s*[^\s,;&]+"), r"\1=<omitido>"),
    (re.compile(r"(?<!\d)(?:\d{3}[.\s-]?\d{3}[.\s-]?\d{3}[-\s]?\d{2}|\d{2}[.\s]?\d{3}[.\s]?\d{3}[\/\s-]?\d{4}[-\s]?\d{2})(?!\d)"), "<documento omitido>"),
    (re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"), "<email omitido>"),
    (re.compile(r"(?<!\d)(?:\+?55\s*)?(?:\(\d{2}\)|\d{2}[-\s])\s*9?\d{4}[-\s]?\d{4}(?!\d)"), "<telefone omitido>"),
    (re.compile(r"(?i)(?:[A-Z]:\\Users\\|/home/|/Users/)[^\\/\s]+"), "<pasta-pessoal>"),
)


def sanitize_text(value: object) -> str:
    try:
        text = str(value)
        for pattern, replacement in _PATTERNS:
            text = pattern.sub(replacement, text)
        return text
    except BaseException:
        return REDACTION_FAILURE


def sanitize(value):
    try:
        if isinstance(value, Mapping):
            return {sanitize_text(key): sanitize(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return tuple(sanitize(item) for item in value)
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, (str, bytes)):
            return sanitize_text(value.decode(errors="replace") if isinstance(value, bytes) else value)
        return value
    except BaseException:
        return REDACTION_FAILURE
