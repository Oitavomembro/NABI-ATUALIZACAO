from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from fichario.license_policy import FicharioLicensePolicy
from licensing.models import LicenseDecision, LicenseEdition, LicensePayload, LicenseState


def decision(edition=LicenseEdition.FICHARIO, features=("fichario", "qt", "commercial", "financial")):
    payload = LicensePayload(
        schema=2, license_id=str(uuid4()), edition=edition, customer_name="LOJA TESTE",
        machine_fingerprint="a" * 64, issued_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        valid_until=date(2026, 9, 1), grace_days=10, features=features,
    )
    return LicenseDecision(LicenseState.ACTIVE, "VALID", "NABI2-TESTE", payload)


def test_edicao_exige_declaracao_fichario_assinada_e_recursos_completos():
    assert FicharioLicensePolicy(decision()).operational
    assert not FicharioLicensePolicy(decision(LicenseEdition.COMMERCIAL)).operational
    assert not FicharioLicensePolicy(decision(features=("fichario", "qt"))).operational
    assert not FicharioLicensePolicy(decision(features=(
        "fichario", "qt", "commercial", "financial", "fiscal"
    ))).operational


def test_estado_nao_operacional_falha_fechado():
    blocked = LicenseDecision(LicenseState.BLOCKED, "EXPIRED", "NABI2-TESTE")
    policy = FicharioLicensePolicy(blocked)
    assert not policy.operational
    with pytest.raises(PermissionError): policy.require()


def test_licenca_ausente_abre_ativacao_antes_do_banco():
    blocked = LicenseDecision(LicenseState.INVALID, "LICENSE_MISSING", "NABI2-TESTE")
    assert FicharioLicensePolicy(blocked).message == "Nenhuma licença foi instalada."
    source = (Path(__file__).parents[1] / "main_fichario_qt.py").read_text(encoding="utf-8")
    assert source.index("FicharioLicenseDialog(") < source.index("DatabaseUsageLock(")
    assert source.index("activation.exec()") < source.index("lock.acquire()")
    dialog = (Path(__file__).parents[1] / "fichario/license_dialog.py").read_text(
        encoding="utf-8"
    )
    assert "Copiar código da máquina" in dialog
    assert "self._service.activation_fingerprint()" in dialog


def test_fichario_licenciado_exige_sessao_individual():
    source = (Path(__file__).parents[1] / "main_fichario_qt.py").read_text(encoding="utf-8")
    assert 'security.start_session_without_password("admin")' not in source
    assert "LoginDialog(" in source
    assert source.index("policy.operational") < source.index(
        'login = LoginDialog(security)'
    )


def test_perfil_fichario_isola_dados_fora_do_programa(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("NABICODE_PROFILE", "TESTE")
    from fichario.profile import configure_fichario_profile
    profile = configure_fichario_profile()
    assert profile.app_dir == (tmp_path / "NabiCode" / "Fichario" / "Teste").resolve()
    assert profile.paths.database.parent == profile.app_dir
    assert "Program Files" not in str(profile.app_dir)


def test_composicao_e_pacote_nao_iniciam_componentes_proibidos():
    root = Path(__file__).parents[1]
    own = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in [root / "main_fichario_qt.py", *sorted((root / "fichario").glob("*.py"))]
    )
    for forbidden in (
        "assistant_nabi", "fiscalworker", "fiscal_outbox", "sefaz", "certificado", "nfeimport",
    ):
        assert forbidden not in own
    spec = (root / "build_tools/pyinstaller/nabicode_fichario.spec").read_text(
        encoding="utf-8"
    ).casefold()
    assert "resources/fiscal" not in spec
    assert "main_fichario_qt.py" in spec
    assert "assistant_nabi" in spec  # exclusao explicita do pacote
    assert all(name in spec for name in ("_tcl_data", "_tk_data", "libtcl", "libtk"))
    assert "services.fiscal_service" not in spec  # pode ficar dormente; nao excluir import quebravel
    pdv_view_model = (root / "ui_qt/commercial/pdv_view_model.py").read_text(
        encoding="utf-8"
    )
    assert pdv_view_model.index("def load_assistant_draft") < pdv_view_model.index(
        "from assistant_nabi.confirmations import ConfirmedDraftAuthorization"
    )


def test_instalador_preserva_dados_em_appdata():
    source = (Path(__file__).parents[1] / "build_tools/inno/NabiCode_Fichario_Offline.iss").read_text(
        encoding="utf-8"
    ).casefold()
    assert "nabicode fichario" in source
    assert "deltree" not in source
    assert "{userappdata}" not in source


def test_shell_restaura_cards_importacao_e_politica_exclusiva_do_pdv():
    root = Path(__file__).parents[1]
    shell = (root / "fichario/shell.py").read_text(encoding="utf-8")
    assert all(label in shell for label in (
        "CLIENTES EM DIA", "CLIENTES DEVENDO", "ATRASADOS +60 DIAS",
        "TOTAL A RECEBER", "Importar Fichário antigo",
    ))
    assert "loose_items_only=True" in shell
    assert "require_registered_customer=True" in shell
    assert 'title.setAlignment(Qt.AlignmentFlag.AlignCenter)' in shell
    policy = (root / "fichario/pdv_view_model.py").read_text(encoding="utf-8")
    assert "item.product_id is not None" in policy
    assert "CONSUMIDOR_FINAL" in policy


def test_menu_visivel_e_backup_diario_configuravel():
    root = Path(__file__).parents[1]
    shell = (root / "fichario/shell.py").read_text(encoding="utf-8")
    preferences = (root / "fichario/preferences_dialog.py").read_text(encoding="utf-8")
    assert '"MENU DO SISTEMA"' in shell
    assert 'button.setMinimumHeight(112)' in shell
    assert 'button.setObjectName("mainActionCard")' in shell
    assert 'prefix="fichario_diario"' in shell
    assert 'backup/last_success' in shell
    assert "configured_backup_directory(self.profile)" in shell
    assert "getExistingDirectory" in preferences
    assert "OneDrive" in preferences
    assert "interface/font_size" in preferences
    assert "Aplicar atualização assinada" in shell


def test_build_fichario_inclui_helper_externo_e_metadado_interno():
    root = Path(__file__).parents[1]
    build = (root / "build_tools/build_fichario.py").read_text(encoding="utf-8")
    spec = (root / "build_tools/pyinstaller/nabicode_fichario.spec").read_text(encoding="utf-8")
    runtime = (root / "fichario/update_runtime.py").read_text(encoding="utf-8")
    assert "NabiCode_Fichario_Updater" in build
    assert '"--uac-admin"' in build
    helper = (root / "build_tools/fichario_update_helper.py").read_text(encoding="utf-8")
    assert "use_shell_broker" in helper
    assert "BUILD_INFO.txt" in build and "BUILD_INFO.txt" in spec
    assert "tempfile.mkdtemp" in build
    assert "trusted_public_keys.json" in spec
    assert "antes_atualizacao" in runtime
    assert "validate_installed_files" in runtime
    assert "ROLLBACK_PENDENTE" in runtime
    shell = (root / "fichario/shell.py").read_text(encoding="utf-8")
    assert "BUILD:" not in shell
    assert "Build:" not in shell


def test_shell_exibe_relogio_do_windows_e_exclusao_cadastral_reforcada():
    root = Path(__file__).parents[1]
    shell = (root / "fichario/shell.py").read_text(encoding="utf-8")
    dialog = (root / "ui_qt/commercial/customer_dialog.py").read_text(encoding="utf-8")
    assert "QDateTime.currentDateTime()" in shell
    assert 'toString("dd/MM/yyyy HH:mm:ss")' in shell
    assert "_clock_timer.setInterval(1000)" in shell
    assert "Excluir cadastro vazio  [Del]" in dialog
    assert 'typed.strip().upper() != "EXCLUIR"' in dialog


def test_backup_e_atualizacao_fichario_exigem_schema_21():
    root = Path(__file__).resolve().parents[1]
    shell = (root / "fichario/shell.py").read_text(encoding="utf-8")
    runtime = (root / "fichario/update_runtime.py").read_text(encoding="utf-8")
    assert "expected_schema_version=21" in shell
    assert "expected_schema_version=21" in runtime
    assert "expected_schema_version=20" not in shell + runtime


def test_entradas_qt_e_fichario_inicializam_schema_21():
    root = Path(__file__).resolve().parents[1]
    qt = (root / "main_qt.py").read_text(encoding="utf-8")
    fichario = (root / "fichario/runtime.py").read_text(encoding="utf-8")
    assert "SCHEMA_VERSION = 21" in qt
    assert "SCHEMA_VERSION = 21" in fichario
    assert "SCHEMA_VERSION = 20" not in qt + fichario


def test_recebimento_separa_revisao_confirmacao_e_oferece_comprovante_oficial():
    root = Path(__file__).parents[1]
    dialog = (root / "fichario/receipt_dialog.py").read_text(encoding="utf-8")
    output = (root / "fichario/receipt_output.py").read_text(encoding="utf-8")
    assert "Revisar recebimento" in dialog
    assert "CONFIRMAR RECEBIMENTO" in dialog
    assert "Saldo antes" in dialog and "Saldo após confirmar" in dialog
    assert "Imprimir recibo" in dialog and "Salvar PDF" in dialog
    assert "ReceiptService" in output
    assert "PrintingService" in output
    assert "generate_customer_payment" in output
