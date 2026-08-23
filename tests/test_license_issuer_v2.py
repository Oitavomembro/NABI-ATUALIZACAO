from __future__ import annotations

import base64
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from license_issuer.emitter import generate_key_pair
from license_issuer.workflow import (
    IssuanceRequest, load_public_catalog, parse_machine_request,
    request_from_existing, review_request, sign_review, verify_license_file,
)
from licensing.license_format import verify_envelope
from licensing.models import LicenseEdition, LicenseState
from licensing.service import LicenseV2Service
from licensing.storage import ProtectedStateStore
import license_issuer_cli


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 23, 12, tzinfo=timezone.utc)
FINGERPRINT = "a" * 64


class Protector:
    def protect(self, data):
        return b"TEST:" + data

    def unprotect(self, data):
        if not data.startswith(b"TEST:"):
            raise ValueError("estado inválido")
        return data[5:]


class Clock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


def create_keys(tmp_path):
    private = tmp_path / "external-secrets" / "owner.pem"
    public = tmp_path / "public.json"
    password = b"senha-forte-teste"
    generate_key_pair(private, public, key_id="owner-2026", password=password)
    return private, public, password


def new_request(**changes):
    values = dict(
        key_id="owner-2026", machine_fingerprint=FINGERPRINT,
        customer_name="CLIENTE TESTE", edition=LicenseEdition.COMMERCIAL,
        valid_until=date(2026, 8, 31), features=("qt", "commercial"),
        issued_at=NOW,
    )
    values.update(changes)
    return IssuanceRequest(**values)


def emit(tmp_path, request=None, output_name="cliente.nabilic"):
    private, public, password = create_keys(tmp_path)
    review = review_request(request or new_request())
    artifact = sign_review(
        review, private_key_path=private, public_catalog_path=public, password=password,
        output_path=tmp_path / output_name,
    )
    return artifact, private, public, password


def test_revisao_e_deterministica_imutavel_e_exibe_tolerancia_normativa():
    request = new_request()
    first = review_request(request)
    second = review_request(request)
    assert first.digest == second.digest
    assert first.summary["tolerancia_dias"] == 10
    assert first.summary["codigo_maquina"].startswith("NABI2-")
    with pytest.raises(TypeError):
        first.summary["cliente"] = "ALTERADO"


def test_emissao_assina_verifica_e_nao_expoe_chave_privada(tmp_path):
    artifact, private, public, _password = emit(tmp_path)
    payload = verify_license_file(artifact.path, public)
    assert payload.customer_name == "CLIENTE TESTE"
    assert payload.machine_fingerprint == FINGERPRINT
    raw = artifact.path.read_bytes()
    assert artifact.sha256 and len(artifact.sha256) == 64
    assert b"PRIVATE KEY" not in raw
    assert private.read_bytes() not in raw


def test_mesma_revisao_e_chave_produzem_saida_deterministica(tmp_path):
    private, public, password = create_keys(tmp_path)
    review = review_request(new_request())
    first = sign_review(
        review, private_key_path=private, public_catalog_path=public,
        password=password, output_path=tmp_path / "primeira.nabilic",
    )
    second = sign_review(
        review, private_key_path=private, public_catalog_path=public,
        password=password, output_path=tmp_path / "segunda.nabilic",
    )
    assert first.sha256 == second.sha256
    assert first.path.read_bytes() == second.path.read_bytes()


def test_adulteracao_chave_incorreta_e_catalogo_ausente_falham(tmp_path):
    artifact, _private, public, _password = emit(tmp_path)
    altered = tmp_path / "alterada.nabilic"
    raw = bytearray(artifact.path.read_bytes())
    raw[len(raw) // 2] ^= 1
    altered.write_bytes(raw)
    with pytest.raises(ValueError):
        verify_license_file(altered, public)

    other = Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    wrong_catalog = tmp_path / "wrong.json"
    wrong_catalog.write_text(json.dumps({
        "schema": 1, "keys": {"owner-2026": base64.b64encode(other).decode("ascii")},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Assinatura"):
        verify_license_file(artifact.path, wrong_catalog)
    with pytest.raises(ValueError, match="não pôde ser lido"):
        load_public_catalog(tmp_path / "ausente.json")


def test_senha_errada_chave_ausente_e_arquivo_existente_nao_geram_saida(tmp_path):
    private, public, password = create_keys(tmp_path)
    review = review_request(new_request())
    with pytest.raises((ValueError, TypeError)):
        sign_review(
            review, private_key_path=private, public_catalog_path=public,
            password=b"senha-incorreta",
            output_path=tmp_path / "wrong.nabilic",
        )
    assert not (tmp_path / "wrong.nabilic").exists()
    with pytest.raises(FileNotFoundError):
        sign_review(
            review, private_key_path=tmp_path / "missing.pem",
            public_catalog_path=public, password=password,
            output_path=tmp_path / "missing.nabilic",
        )
    existing = tmp_path / "existing.nabilic"
    existing.write_bytes(b"preservar")
    with pytest.raises(FileExistsError, match="não será sobrescrito"):
        sign_review(
            review, private_key_path=private, public_catalog_path=public,
            password=password, output_path=existing,
        )
    assert existing.read_bytes() == b"preservar"


def test_chave_privada_incorreta_para_o_catalogo_e_recusada(tmp_path):
    _private, public, _password = create_keys(tmp_path)
    other_private = tmp_path / "other-secrets" / "other.pem"
    other_public = tmp_path / "other-public.json"
    generate_key_pair(
        other_private, other_public, key_id="owner-2026",
        password=b"outra-senha-forte",
    )
    with pytest.raises(ValueError, match="não corresponde"):
        sign_review(
            review_request(new_request()), private_key_path=other_private,
            public_catalog_path=public, password=b"outra-senha-forte",
            output_path=tmp_path / "nao-gerada.nabilic",
        )
    assert not (tmp_path / "nao-gerada.nabilic").exists()


def test_solicitacao_da_maquina_valida_codigo_e_fingerprint():
    from licensing.machine import machine_code

    raw = json.dumps({
        "machine_code": machine_code(FINGERPRINT),
        "machine_fingerprint": FINGERPRINT,
    }).encode()
    assert parse_machine_request(raw) == (FINGERPRINT, machine_code(FINGERPRINT))
    forged = json.dumps({
        "machine_code": "NABI2-FORJADO", "machine_fingerprint": FINGERPRINT,
    }).encode()
    with pytest.raises(ValueError, match="não correspondem"):
        parse_machine_request(forged)


def test_renovacao_preserva_identidade_e_exige_validade_maior(tmp_path):
    artifact, private, public, password = emit(tmp_path)
    renewed_request = request_from_existing(
        artifact.path, public, valid_until=date(2027, 8, 31),
        issued_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )
    assert renewed_request.license_id == artifact.payload.license_id
    assert renewed_request.machine_fingerprint == artifact.payload.machine_fingerprint
    renewed = sign_review(
        review_request(renewed_request), private_key_path=private,
        public_catalog_path=public, password=password,
        output_path=tmp_path / "renovada.nabilic",
    )
    assert renewed.payload.valid_until == date(2027, 8, 31)
    assert renewed.path != artifact.path
    with pytest.raises(ValueError, match="ampliar"):
        request_from_existing(
            artifact.path, public, valid_until=date(2026, 8, 31),
            issued_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
        )


def test_revogacao_assinada_preserva_id_e_e_reconhecida(tmp_path):
    artifact, private, public, password = emit(tmp_path)
    revoked_request = request_from_existing(
        artifact.path, public, valid_until=date(2026, 9, 30),
        issued_at=datetime(2026, 8, 24, tzinfo=timezone.utc), revoked=True,
    )
    revoked = sign_review(
        review_request(revoked_request), private_key_path=private,
        public_catalog_path=public, password=password,
        output_path=tmp_path / "revogada.nabilic",
    )
    assert revoked.payload.revoked
    assert revoked.payload.license_id == artifact.payload.license_id


def test_runtime_comprova_maquina_tolerancia_bloqueio_e_revogacao(tmp_path):
    artifact, private, public_path, password = emit(tmp_path)
    public = load_public_catalog(public_path)
    clock = Clock(NOW)
    service = LicenseV2Service(
        license_path=tmp_path / "runtime" / "current.nabilic",
        state_store=ProtectedStateStore(tmp_path / "runtime" / "state.dat", Protector()),
        public_keys=public, machine_fingerprint=lambda: FINGERPRINT, now=clock,
    )
    assert service.activate(artifact.path).state is LicenseState.ACTIVE
    clock.value = datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert service.evaluate().state is LicenseState.GRACE
    clock.value = datetime(2026, 9, 11, tzinfo=timezone.utc)
    assert service.evaluate().state is LicenseState.BLOCKED

    copied = LicenseV2Service(
        license_path=artifact.path,
        state_store=service.state_store,
        public_keys=public, machine_fingerprint=lambda: "b" * 64, now=clock,
    )
    assert copied.evaluate().reason == "MACHINE_MISMATCH"

    revoked_request = request_from_existing(
        artifact.path, public_path, valid_until=date(2026, 9, 30),
        issued_at=datetime(2026, 9, 10, 23, tzinfo=timezone.utc), revoked=True,
    )
    revoked = sign_review(
        review_request(revoked_request), private_key_path=private,
        public_catalog_path=public_path, password=password,
        output_path=tmp_path / "runtime-revogada.nabilic",
    )
    assert service.activate(revoked.path).state is LicenseState.REVOKED


def test_avaliacao_tem_limite_e_nao_existe_licenca_ilimitada():
    with pytest.raises(ValueError, match="trinta dias"):
        new_request(
            edition=LicenseEdition.EVALUATION,
            valid_until=date(2026, 9, 30),
        )
    with pytest.raises(TypeError):
        IssuanceRequest(
            key_id="owner-2026", machine_fingerprint=FINGERPRINT,
            customer_name="CLIENTE", edition=LicenseEdition.COMMERCIAL,
            features=("commercial",), issued_at=NOW,
        )


def test_empacotamento_externo_nao_inclui_runtime_catalogo_ou_segredos():
    spec = (ROOT / "build_tools" / "pyinstaller" / "nabicode_license_issuer.spec").read_text(
        encoding="utf-8"
    )
    normalized = spec.replace(" ", "")
    assert "datas=[]" in normalized
    assert "trusted_public_keys" not in spec
    assert "assistant_nabi" in spec and "services" in spec
    assert "license_issuer_app.py" in spec
    private_files = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in {".p12", ".pfx"}:
            private_files.append(path)
        elif suffix in {".pem", ".key"} and b"PRIVATE KEY" in path.read_bytes():
            private_files.append(path)
    assert private_files == []


def test_interface_exige_revisao_e_invalida_apos_alteracao(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication
    from license_issuer.ui_qt import LicenseIssuerWindow

    app = QApplication.instance() or QApplication([])
    window = LicenseIssuerWindow()
    window.key_id.setText("owner-2026")
    window.machine_fingerprint.setText(FINGERPRINT)
    window.customer.setText("CLIENTE TESTE")
    window.valid_until.setDate(QDate(2026, 8, 31))
    window.output.setText("C:/temporario/cliente.nabilic")
    window._review_request()
    assert window._review is not None
    assert window.sign_button.isEnabled()
    assert "NENHUM ARQUIVO FOI ASSINADO" in window.review_text.toPlainText()
    window.customer.setText("CLIENTE ALTERADO")
    assert window._review is None
    assert not window.sign_button.isEnabled()
    window.close()
    app.processEvents()


def test_interface_facil_descobre_chaves_e_configura_fichario(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    import base64
    import json
    from PySide6.QtWidgets import QApplication
    from license_issuer.ui_qt import LicenseIssuerWindow

    keys = tmp_path / "segredos"; keys.mkdir()
    private = keys / "nabicode-prod-2026-01-private.pem"
    private.write_text("ARQUIVO EXTERNO SIMULADO", encoding="utf-8")
    catalog = keys / "trusted_public_keys.json"
    catalog.write_text(json.dumps({
        "schema": 1,
        "keys": {"nabicode-prod-2026-01": base64.b64encode(b"p" * 32).decode("ascii")},
    }), encoding="utf-8")
    output = tmp_path / "licencas"
    app = QApplication.instance() or QApplication([])
    window = LicenseIssuerWindow(key_directory=keys, output_directory=output)

    assert window.private_key.text() == str(private)
    assert window.public_catalog.text() == str(catalog)
    assert window.key_id.text() == "nabicode-prod-2026-01"
    assert window.edition.currentText() == "FICHARIO"
    assert window.features.text() == "commercial,fichario,financial,qt"
    assert window.features.isReadOnly()
    assert window.advanced_panel.isHidden()
    window.advanced_button.click()
    assert not window.advanced_panel.isHidden()
    assert window.advanced_button.text() == "Ocultar opções avançadas"
    assert window.output.text().endswith("fichario-cliente-" + window.valid_until.date().toString("yyyyMMdd") + ".nabilic")
    window.close(); app.processEvents()


def test_interface_facil_usuario_escolhe_edicao_periodo_e_nome(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication
    from license_issuer.ui_qt import LicenseIssuerWindow

    app = QApplication.instance() or QApplication([])
    window = LicenseIssuerWindow(key_directory=tmp_path / "sem-chave", output_directory=tmp_path)
    window.customer.setText("Pedro Miranda")
    window.edition.setCurrentText("COMERCIAL")
    window.duration.setCurrentIndex(window.duration.findData(3))
    assert window.features.text() == "commercial,legacy,qt"
    assert window.valid_until.date() == QDate.currentDate().addMonths(3)
    assert "comercial-pedro-miranda" in window.output.text()
    window.edition.setCurrentText("AVALIACAO")
    assert not window.duration.isEnabled()
    assert window.valid_until.date() == QDate.currentDate().addDays(29)
    window.close(); app.processEvents()


def test_interface_facil_usa_maquina_local_e_minimiza(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from license_issuer import ui_qt
    from license_issuer.ui_qt import LicenseIssuerWindow

    fingerprint = "f" * 64
    monkeypatch.setattr(ui_qt, "current_machine_fingerprint", lambda: fingerprint)
    app = QApplication.instance() or QApplication([])
    window = LicenseIssuerWindow(key_directory=tmp_path, output_directory=tmp_path)
    window.local_machine_button.click()
    assert window.machine_fingerprint.text() == fingerprint
    assert window.machine_code.text() != "—"
    window.show(); app.processEvents()
    window.minimize_button.click()
    app.processEvents()
    assert window.isMinimized()
    window.close(); app.processEvents()


def test_cli_cancela_antes_de_pedir_senha_e_nao_cria_arquivo(tmp_path, monkeypatch):
    private, public, _password = create_keys(tmp_path)
    output = tmp_path / "cancelada.nabilic"
    monkeypatch.setattr("builtins.input", lambda _prompt: "CANCELAR")

    def senha_nao_deve_ser_pedida(_prompt):
        raise AssertionError("senha foi solicitada antes da confirmação")

    monkeypatch.setattr(license_issuer_cli.getpass, "getpass", senha_nao_deve_ser_pedida)
    result = license_issuer_cli.main([
        "issue", "--private", str(private), "--public-catalog", str(public),
        "--key-id", "owner-2026", "--machine-fingerprint", FINGERPRINT,
        "--customer", "CLIENTE TESTE", "--edition", "COMERCIAL",
        "--valid-until", "2026-08-31", "--feature", "commercial",
        "--output", str(output),
    ])
    assert result == 2
    assert not output.exists()


def test_cli_emite_e_verifica_sem_senha_em_argumentos(tmp_path, monkeypatch, capsys):
    private, public, password = create_keys(tmp_path)
    output = tmp_path / "cli.nabilic"
    monkeypatch.setattr("builtins.input", lambda _prompt: "EMITIR")
    monkeypatch.setattr(
        license_issuer_cli.getpass, "getpass", lambda _prompt: password.decode("utf-8")
    )
    args = [
        "issue", "--private", str(private), "--public-catalog", str(public),
        "--key-id", "owner-2026", "--machine-fingerprint", FINGERPRINT,
        "--customer", "CLIENTE TESTE", "--edition", "COMERCIAL",
        "--valid-until", "2026-08-31", "--feature", "commercial",
        "--output", str(output),
    ]
    assert password.decode("utf-8") not in args
    assert license_issuer_cli.main(args) == 0
    emitted = capsys.readouterr().out
    assert "REVISÃO" in emitted and "SHA-256" in emitted
    assert password.decode("utf-8") not in emitted
    assert license_issuer_cli.main([
        "verify", "--license", str(output), "--public-catalog", str(public),
    ]) == 0
    verified = capsys.readouterr().out
    assert '"assinatura": "VALIDA"' in verified
    assert password.decode("utf-8") not in verified
