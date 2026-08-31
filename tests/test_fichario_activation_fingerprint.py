from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from fichario.license_dialog import FicharioLicenseDialog
from fichario.license_policy import FicharioLicensePolicy
from licensing.models import LicenseDecision, LicenseState
from licensing.service import LicenseV2Service


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def service(tmp_path, provider):
    return LicenseV2Service(
        license_path=tmp_path / "absent.nabilic", state_store=Mock(),
        public_keys={}, machine_fingerprint=provider,
    )


def policy():
    return FicharioLicensePolicy(LicenseDecision(
        LicenseState.INVALID, "LICENSE_MISSING", "NABI2-FC82-BBBC-BB07-6B27",
    ))


def test_copy_complete_local_identity_without_license_or_state(app, tmp_path, monkeypatch):
    fingerprint = "fc82bbbcbb076b27" + "a" * 48
    warning = Mock()
    monkeypatch.setattr(QMessageBox, "warning", warning)
    provider = Mock(return_value=fingerprint)
    svc = service(tmp_path, provider)
    dialog = FicharioLicenseDialog(svc, policy())
    try:
        dialog.copy_button.click()
        assert app.clipboard().text() == fingerprint
        assert len(app.clipboard().text()) == 64
        assert dialog.copy_button.text() == "Código completo copiado!"
        provider.assert_called_once_with()
        warning.assert_not_called()
        assert not svc.state_store.mock_calls
        assert list(tmp_path.iterdir()) == []
    finally:
        dialog.close()


@pytest.mark.parametrize("invalid", ["NABI2-FC82-BBBC-BB07-6B27", "a" * 63, "g" * 64, None])
def test_invalid_identity_is_rejected_without_writes(tmp_path, invalid):
    svc = service(tmp_path, lambda: invalid)
    with pytest.raises(ValueError, match="indisponível"):
        svc.activation_fingerprint()
    assert not svc.state_store.mock_calls
    assert list(tmp_path.iterdir()) == []


def test_copy_failure_does_not_claim_success_or_replace_clipboard(app, tmp_path, monkeypatch):
    svc = service(tmp_path, Mock(side_effect=RuntimeError("sensitive detail")))
    warning = Mock()
    monkeypatch.setattr(QMessageBox, "warning", warning)
    dialog = FicharioLicenseDialog(svc, policy())
    app.clipboard().setText("previous")
    try:
        dialog.copy_button.click()
        assert app.clipboard().text() == "previous"
        assert dialog.copy_button.text() == "Copiar código da máquina"
        warning.assert_called_once()
        assert "sensitive detail" not in str(warning.call_args)
        assert not svc.state_store.mock_calls
    finally:
        dialog.close()


def test_identity_is_not_read_from_foreign_license(tmp_path):
    svc = service(tmp_path, lambda: "b" * 64)
    svc.license_path.write_text("foreign or damaged license", encoding="utf-8")
    assert svc.activation_fingerprint() == "b" * 64
    assert svc.license_path.read_text(encoding="utf-8") == "foreign or damaged license"
    assert not svc.state_store.mock_calls
