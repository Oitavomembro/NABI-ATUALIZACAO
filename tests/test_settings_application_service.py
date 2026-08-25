from __future__ import annotations

from types import SimpleNamespace

import pytest

from administration.settings_application_service import SettingsApplicationService


class Security:
    def __init__(self, permissions=("view", "edit", "backup", "diagnose")):
        self.permissions = set(permissions)
        self.session = SimpleNamespace(user=SimpleNamespace(username="Maria"))
        self.touches = 0

    def is_expired(self): return False
    def require(self, module, action): return module == "configs" and action in self.permissions
    def touch(self): self.touches += 1


class System:
    def __init__(self): self.values = {"backup_diario_ativo": "1"}
    def get_config(self, key, default=""): return self.values.get(key, default)
    def set_config(self, key, value): self.values[key] = str(value)
    def set_configs(self, values): self.values.update({key: str(value) for key, value in values.items()})


class Printing:
    def list_printers(self): return ["Padrão do Sistema", "Térmica TESTE"]


class Backup:
    def __init__(self, directory): self.directory = str(directory); self.calls = 0
    def configured_directories(self): return [self.directory]
    def create_all(self, prefix):
        self.calls += 1
        return SimpleNamespace(created=(f"{self.directory}/{prefix}.db",), errors=())
    def verify_restore_in_temporary(self, path):
        self.calls += 1
        return SimpleNamespace(
            source=str(path), integrity="ok", backup_format="SQLITE_LEGACY_UNENCRYPTED",
            encrypted=False, sha256="a" * 64, schema_version=21,
        )
    def create(self, directory, prefix):
        self.calls += 1; return f"{directory}/{prefix}.db"
    def create_encrypted(self, directory, password, prefix):
        self.calls += 1; return f"{directory}/{prefix}.nabibackup"


class Diagnostics:
    def __init__(self): self.calls = 0
    def run(self, *, save_report): self.calls += 1; return {"aprovado": True}
    def format_report(self, result): return "SISTEMA APROVADO" if result["aprovado"] else "FALHA"


def service(tmp_path, permissions=("view", "edit", "backup", "diagnose")):
    security = Security(permissions); system = System(); backup = Backup(tmp_path / "backups")
    diagnostics = Diagnostics()
    return SettingsApplicationService(
        security=security,
        system_repository=system,
        config_path=tmp_path / "config" / "sistema.json",
        backup_service=backup,
        diagnostics=diagnostics,
        printing_service=Printing(),
    ), security, system, backup, diagnostics


def test_preferencias_sao_normalizadas_e_isoladas_por_usuario(tmp_path):
    application, _security, _system, _backup, _diagnostics = service(tmp_path)
    saved = application.save_preferences({"mode": "Simples", "density": "Confortável"})
    assert saved.username == "maria"
    assert saved.preferences["mode"] == "Simples"
    assert saved.preferences["density"] == "Confortável"
    assert application.load().preferences["mode"] == "Simples"


def test_perfil_somente_leitura_nao_altera_preferencias_ou_backup(tmp_path):
    application, _security, _system, backup, _diagnostics = service(tmp_path, ("view",))
    assert application.load().username == "maria"
    with pytest.raises(PermissionError): application.save_preferences({"mode": "Simples"})
    with pytest.raises(PermissionError):
        application.configure_backup(local_directory=str(tmp_path), daily=True)
    with pytest.raises(PermissionError): application.create_backup()
    assert backup.calls == 0


def test_backup_exige_caminho_absoluto_e_executa_uma_vez(tmp_path):
    application, _security, system, backup, _diagnostics = service(tmp_path)
    with pytest.raises(ValueError):
        application.configure_backup(local_directory="relativo", daily=False)
    snapshot = application.configure_backup(
        local_directory=str(tmp_path / "local"),
        cloud_directory=str(tmp_path / "nuvem"),
        daily=False,
    )
    assert snapshot.daily_backup_enabled is False
    assert system.values["pasta_backup_nuvem"].endswith("nuvem")
    result = application.create_backup()
    assert len(result.created) == 1 and backup.calls == 1


def test_verificacao_de_restore_exige_permissao_e_delega_somente_ao_temp(tmp_path):
    application, _security, _system, backup, _diagnostics = service(tmp_path)
    result = application.verify_backup_restore(tmp_path / "backup.db")
    assert result.integrity == "ok" and backup.calls == 1
    blocked, *_ = service(tmp_path / "blocked", ("view",))
    with pytest.raises(PermissionError):
        blocked.verify_backup_restore(tmp_path / "backup.db")


def test_pacote_criptografado_e_gerado_e_verificado_sem_persistir_senha(tmp_path):
    application, _security, system, backup, _diagnostics = service(tmp_path)
    original_verify = backup.verify_restore_in_temporary
    received = {}

    def verify(path, password=None):
        received["password"] = password
        result = original_verify(path)
        return SimpleNamespace(**{
            **result.__dict__, "backup_format": "NABICODE_ENCRYPTED_V1",
            "encrypted": True,
        })

    backup.verify_restore_in_temporary = verify
    result = application.create_backup_package(
        directory=tmp_path / "secure", encrypted=True,
        password="senha efemera segura",
    )
    assert result.encrypted is True
    assert result.filename.endswith(".nabibackup")
    assert received["password"] == "senha efemera segura"
    assert "senha efemera segura" not in repr(system.values)


def test_pacote_legado_fica_marcado_como_nao_criptografado(tmp_path):
    application, *_ = service(tmp_path)
    result = application.create_backup_package(
        directory=tmp_path / "legacy", encrypted=False
    )
    assert result.encrypted is False
    assert result.backup_format == "SQLITE_LEGACY_UNENCRYPTED"


def test_diagnostico_e_somente_leitura_para_dados_de_negocio(tmp_path):
    application, _security, _system, _backup, diagnostics = service(tmp_path)
    result, report = application.run_diagnostics()
    assert result == {"aprovado": True}
    assert report == "SISTEMA APROVADO" and diagnostics.calls == 1


def test_sessao_ausente_falha_fechado(tmp_path):
    application, security, *_ = service(tmp_path)
    security.session = None
    with pytest.raises(PermissionError): application.load()


def test_impressao_normaliza_formato_e_salva_sem_disparar_spooler(tmp_path):
    application, _security, system, *_ = service(tmp_path)
    values = dict(application.load_printing().values)
    values.update({"impressora_recibo":"Térmica TESTE","formato_impressao_recibo":"Cupom 58 mm","modelo_cupom_visual":"Moderno","impressao_fonte":"Courier","impressao_fonte_tamanho":"12","impressao_corte_automatico":"1","impressao_tipo_corte":"PARCIAL","impressao_linhas_antes_corte":"3"})
    saved = application.save_printing(values)
    assert saved.values["formato_impressao_recibo"] == "Cupom 80 mm"
    assert system.values["impressora_recibo"] == "Térmica TESTE"
    assert "COMPROVANTE DE TESTE" in application.preview_receipt("Moderno")


def test_identidade_da_loja_e_atomica_e_nao_aceita_campos_vazios(tmp_path):
    application,_security,system,*_=service(tmp_path)
    saved=application.save_store_identity(name="  LOJA   TESTE  ",receipt_footer="Obrigado!\r\nVolte sempre.")
    assert saved.name=="LOJA TESTE" and saved.receipt_footer=="Obrigado!\nVolte sempre."
    assert system.values["nome_loja"]=="LOJA TESTE"
    with pytest.raises(ValueError): application.save_store_identity(name=" ",receipt_footer="OK")


def test_identidade_da_loja_rejeita_controle_e_excesso(tmp_path):
    application,*_=service(tmp_path)
    with pytest.raises(ValueError): application.save_store_identity(name="LOJA\x00",receipt_footer="OK")
    with pytest.raises(ValueError): application.save_store_identity(name="LOJA",receipt_footer="x"*501)
