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
    assert "QApplication.clipboard().setText(self._machine_code_value)" in dialog


def test_fichario_licenciado_abre_sessao_local_sem_tela_de_login():
    source = (Path(__file__).parents[1] / "main_fichario_qt.py").read_text(encoding="utf-8")
    assert 'security.start_session_without_password("admin")' in source
    assert "LoginDialog(" not in source
    assert source.index("policy.operational") < source.index(
        'security.start_session_without_password("admin")'
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
    assert 'prefix="fichario_diario"' in shell
    assert 'backup/last_success' in shell
    assert "configured_backup_directory(self.profile)" in shell
    assert "getExistingDirectory" in preferences
    assert "OneDrive" in preferences
    assert "interface/font_size" in preferences


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
