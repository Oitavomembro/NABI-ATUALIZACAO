import logging
from pathlib import Path

from core.diagnostic_logging import RedactingFormatter
from core.sensitive_data import REDACTION_FAILURE, sanitize, sanitize_text


SECRET = "Segredo-Nunca-Pode-Aparecer"


def test_sanitizer_removes_secrets_pii_xml_and_personal_paths():
    raw = (
        f"senha={SECRET} Authorization: Bearer abc token=xyz "
        "CPF 123.456.789-09 CNPJ 12.345.678/0001-95 pessoa@empresa.com "
        "(71) 99999-8888 C:\\Users\\Maria\\certificado.pfx "
        "<NFe><infNFe>conteudo fiscal completo</infNFe></NFe>"
    )
    safe = sanitize_text(raw)
    for forbidden in (SECRET, "abc", "xyz", "123.456.789-09", "12.345.678/0001-95", "pessoa@empresa.com", "99999-8888", "Maria", "conteudo fiscal completo"):
        assert forbidden not in safe
    assert "senha=<omitido>" in safe
    assert "<xml fiscal omitido>" in safe


def test_nested_diagnostic_keeps_technical_support_fields():
    safe = sanitize({"status": "ERRO", "operation_id": "op-7f3a", "detail": "email=a@b.com"})
    assert safe["status"] == "ERRO"
    assert safe["operation_id"] == "op-7f3a"
    assert "a@b.com" not in safe["detail"]


def test_formatter_never_emits_raw_value_when_sanitizer_fails(monkeypatch):
    import core.diagnostic_logging as module

    monkeypatch.setattr(module, "sanitize_text", lambda _value: REDACTION_FAILURE)
    record = logging.LogRecord("teste", logging.ERROR, __file__, 1, "senha=%s", (SECRET,), None)
    rendered = RedactingFormatter("%(levelname)s %(message)s").format(record)
    assert SECRET not in rendered
    assert REDACTION_FAILURE in rendered


def test_sanitizer_failure_is_fail_closed():
    class Hostile:
        def __str__(self):
            raise RuntimeError(SECRET)

    assert sanitize_text(Hostile()) == REDACTION_FAILURE
