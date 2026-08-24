from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_SOURCE = (ROOT / "main.py").read_text(encoding="utf-8")
LEGACY_SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
SECURITY_SOURCE = (ROOT / "services" / "security_service.py").read_text(
    encoding="utf-8"
)


def test_licenca_v2_assinada_precede_banco_e_interface_legacy():
    gate = MAIN_SOURCE.index("license_gate = evaluate_runtime_gate(runtime_profile.app_dir)")
    database = MAIN_SOURCE.index("runtime_profile.validate_database")
    application = MAIN_SOURCE.index("app = legacy.FicharioMoveisApp()")
    assert gate < database < application


def test_legacy_nao_exige_segunda_ativacao_por_senha_embutida():
    assert "InstallationAuthorizationService" not in LEGACY_SOURCE
    assert "verificar_autorizacao_instalacao" not in LEGACY_SOURCE
    assert "forcar_tela_autorizacao_instalacao" not in LEGACY_SOURCE
    assert "verify_master_password" not in LEGACY_SOURCE


def test_seguranca_nao_contem_credencial_mestra_universal():
    assert "MASTER_PASSWORD_SHA256" not in SECURITY_SOURCE
    assert "verify_master_password" not in SECURITY_SOURCE
    assert "LOGIN_MESTRE" not in SECURITY_SOURCE
    assert "CONFIRMACAO_MESTRE" not in SECURITY_SOURCE


def test_operacoes_protegidas_usam_credencial_gerencial_real():
    assert "def _confirmar_senha_gerencial" in LEGACY_SOURCE
    assert "self.security.confirm_manager_password(senha)" in LEGACY_SOURCE
    assert "senha mestra" not in LEGACY_SOURCE.casefold()
