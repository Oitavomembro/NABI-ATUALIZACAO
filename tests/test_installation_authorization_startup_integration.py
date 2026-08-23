from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_SOURCE = (ROOT / "nabicode_legacy.py").read_text(encoding="utf-8")
SERVICE_SOURCE = (ROOT / "services" / "installation_authorization_service.py").read_text(
    encoding="utf-8"
)


def test_autorizacao_da_instalacao_precede_validade_da_licenca_no_startup():
    authorization = LEGACY_SOURCE.index("self.verificar_autorizacao_instalacao()")
    database = LEGACY_SOURCE.index('mark_startup("database_migrations_started")')
    license_validation = LEGACY_SOURCE.index("self.verificar_bloqueio_expiracao()")
    assert authorization < database < license_validation


def test_startup_usa_perfil_oficial_e_appdata_sem_sqlite_no_servico():
    constructor = LEGACY_SOURCE.split(
        "self.installation_authorization_service =", 1
    )[1].split(")\n", 1)[0]
    assert 'os.environ.get("NABICODE_PROFILE"' in constructor
    assert "app_dir=APP_DIR" in constructor
    assert "sqlite" not in SERVICE_SOURCE.casefold()


def test_bloqueio_de_ativacao_reutiliza_a_raiz_e_nao_abre_segundo_mainloop():
    block = LEGACY_SOURCE.split("def forcar_tela_autorizacao_instalacao", 1)[1].split(
        "def verificar_bloqueio_expiracao", 1
    )[0]
    assert "ctk.CTkToplevel(self)" in block
    assert "self.wait_window(activation_window)" in block
    assert "ctk.CTk()" not in block
    assert ".mainloop()" not in block
    assert "SecurityService.verify_master_password" in block


def test_painel_expoe_status_codigo_data_e_remocao_protegida():
    license_panel = LEGACY_SOURCE.split("# LICENÇA", 1)[1].split("# BANCO", 1)[0]
    assert "AUTORIZAÇÃO DA INSTALAÇÃO" in license_panel
    assert "Código da máquina" in license_panel
    assert "Ativada em" in license_panel
    assert "Remover autorização deste computador" in license_panel
    assert "self.security.verify_master_password" in license_panel
