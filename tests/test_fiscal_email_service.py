import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from services.fiscal_email_service import FiscalEmailService


class Protector:
    def protect(self, value): return b"protected:" + value
    def unprotect(self, value): return value.removeprefix(b"protected:")


class SMTP:
    def __init__(self):
        self.calls = []
        self.message = None

    def ehlo(self): self.calls.append("ehlo")
    def starttls(self, **_kwargs): self.calls.append("starttls")
    def login(self, user, password): self.calls.append(("login", user, password))
    def send_message(self, message): self.message = message
    def quit(self): self.calls.append("quit")


@pytest.fixture
def email_service():
    with tempfile.TemporaryDirectory() as temporary:
        smtp = SMTP()
        service = FiscalEmailService(
            Path(temporary) / "email", secret_protector=Protector(),
            smtp_factory=lambda *_args: smtp,
        )
        yield service, smtp, Path(temporary)


def test_configuracao_protege_senha_e_expoe_so_dados_publicos(email_service):
    service, _smtp, _root = email_service
    config = service.configure(
        host="smtp.example.com", port=587, username="empresa@example.com",
        password="segredo", sender="empresa@example.com", security="TLS",
    )
    assert config["host"] == "smtp.example.com"
    assert "password" not in service.config_path.read_text(encoding="utf-8")
    assert service.secret_path.read_bytes() == b"protected:segredo"


def test_edicao_do_agendamento_preserva_senha_protegida_quando_campo_fica_vazio(email_service):
    service, _smtp, _root = email_service
    service.configure(
        host="smtp.example.com", port=587, username="empresa@example.com",
        password="segredo", sender="empresa@example.com", security="TLS",
    )
    original = service.secret_path.read_bytes()
    config = service.configure(
        host="smtp.example.com", port=587, username="empresa@example.com",
        password="", sender="empresa@example.com", security="TLS",
        accountant_recipient="contador@example.com", accounting_day=10,
        accounting_enabled=True,
    )
    assert service.secret_path.read_bytes() == original
    assert config["accounting_day"] == 10


def test_fila_envia_xml_e_pdf_com_tls(email_service):
    service, smtp, root = email_service
    xml = root / "nota.xml"; xml.write_bytes(b"<nfeProc/>")
    pdf = root / "danfe.pdf"; pdf.write_bytes(b"%PDF-1.4 teste")
    service.configure(
        host="smtp.example.com", port=587, username="empresa@example.com",
        password="segredo", sender="empresa@example.com", security="TLS",
    )
    queued = service.enqueue(
        recipient="cliente@example.com", subject="Nota fiscal", body="Segue.",
        attachments=[xml, pdf], access_key="1" * 44,
    )
    assert queued["status"] == "PENDENTE"
    result = service.process_pending()
    assert result[0]["status"] == "ENVIADO"
    assert smtp.calls[:4] == [
        "ehlo", "starttls", "ehlo", ("login", "empresa@example.com", "segredo")
    ]
    assert len(list(smtp.message.iter_attachments())) == 2
    assert "segredo" not in service.queue_path.read_text(encoding="utf-8")


def test_falha_permanece_na_fila_para_nova_tentativa(email_service):
    service, smtp, root = email_service
    xml = root / "nota.xml"; xml.write_bytes(b"<nfeProc/>")
    service.configure(
        host="smtp.example.com", port=465, username="empresa@example.com",
        password="segredo", sender="empresa@example.com", security="SSL",
    )
    service.enqueue(
        recipient="cliente@example.com", subject="Nota", body="", attachments=[xml]
    )
    smtp.send_message = lambda _message: (_ for _ in ()).throw(RuntimeError("falha simulada"))
    assert service.process_pending()[0]["status"] == "FALHA"
    assert service.list_queue()[0]["attempts"] == 1


def test_rejeita_email_e_anexo_invalidos(email_service):
    service, _smtp, root = email_service
    with pytest.raises(ValueError, match="destinatário"):
        service.enqueue(recipient="invalido", subject="x", body="", attachments=[])
    invalid = root / "arquivo.exe"; invalid.write_bytes(b"x")
    service.configure(
        host="smtp.example.com", port=587, username="empresa@example.com",
        password="segredo", sender="empresa@example.com", security="TLS",
    )
    service.enqueue(
        recipient="cliente@example.com", subject="x", body="", attachments=[invalid]
    )
    assert service.process_pending()[0]["status"] == "FALHA"


def test_remocao_apaga_configuracao_e_segredo(email_service):
    service, _smtp, _root = email_service
    service.configure(
        host="smtp.example.com", port=587, username="empresa@example.com",
        password="segredo", sender="empresa@example.com", security="TLS",
    )
    service.remove_config()
    assert not service.config_path.exists()
    assert not service.secret_path.exists()


def test_envio_mensal_usa_mes_anterior_e_nao_repete_periodo(email_service):
    service, smtp, root = email_service
    package = root / "contabilidade.zip"; package.write_bytes(b"PK\x03\x04teste")
    service.configure(
        host="smtp.example.com", port=587, username="empresa@example.com",
        password="segredo", sender="empresa@example.com", security="TLS",
        accountant_recipient="contador@example.com", accounting_day=5,
        accounting_enabled=True,
    )
    assert service.accounting_period_due(now=datetime(2026, 8, 5, 9)) == (
        "2026-07-01", "2026-07-31"
    )
    service.enqueue(
        recipient="contador@example.com", subject="Fechamento", body="Segue.",
        attachments=[package],
    )
    assert service.process_pending()[0]["status"] == "ENVIADO"
    assert list(smtp.message.iter_attachments())[0].get_filename() == "contabilidade.zip"
    service.mark_accounting_period_sent("2026-07-01")
    assert service.accounting_period_due(now=datetime(2026, 8, 5, 10)) is None


def test_agendamento_contabil_exige_destinatario_e_dia_seguro(email_service):
    service, _smtp, _root = email_service
    with pytest.raises(ValueError, match="contador"):
        service.configure(
            host="smtp.example.com", port=587, username="empresa@example.com",
            password="segredo", sender="empresa@example.com", accounting_enabled=True,
        )
    with pytest.raises(ValueError, match="entre 1 e 28"):
        service.configure(
            host="smtp.example.com", port=587, username="empresa@example.com",
            password="segredo", sender="empresa@example.com", accounting_day=31,
        )
