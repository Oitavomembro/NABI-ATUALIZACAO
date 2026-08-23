from __future__ import annotations

import shutil
from datetime import datetime, timezone

from services.installation_authorization_service import InstallationAuthorizationService
from services.windows_data_protector import WindowsDataProtectionError, WindowsDataProtector


MACHINE_A = {
    "machine_guid": "machine-guid-a",
    "system_volume_serial": "A1B2C3D4",
}
MACHINE_B = {
    "machine_guid": "machine-guid-b",
    "system_volume_serial": "99887766",
}


class BoundProtector:
    """Simula o vínculo da DPAPI com uma máquina sem depender do Windows."""

    def __init__(self, machine_key: bytes):
        self.prefix = b"DPAPI:" + machine_key + b":"

    def protect(self, data: bytes) -> bytes:
        return self.prefix + bytes(data)[::-1]

    def unprotect(self, data: bytes) -> bytes:
        if not bytes(data).startswith(self.prefix):
            raise WindowsDataProtectionError("Escopo DPAPI diferente.")
        return bytes(data)[len(self.prefix):][::-1]


def make_service(
    folder,
    *,
    profile="PRODUCAO",
    machine=MACHINE_A,
    protector=None,
    clock=None,
):
    return InstallationAuthorizationService(
        profile=profile,
        authorization_file=folder / "authorization" / "installation.dat",
        protector=protector or BoundProtector(b"machine-a"),
        machine_components_provider=lambda: machine,
        now=lambda: datetime(2026, 8, 22, 12, 30, tzinfo=timezone.utc),
        monotonic=clock or (lambda: 100.0),
    )


def master_password_is_valid(password):
    return password == "senha-correta"


def test_producao_sem_arquivo_bloqueia(tmp_path):
    status = make_service(tmp_path).evaluate()
    assert status.required is True
    assert status.authorized is False
    assert status.reason == "MISSING"
    assert status.machine_code.startswith("NABI-")


def test_producao_com_autorizacao_da_propria_maquina_permite_e_persiste(tmp_path):
    service = make_service(tmp_path)
    assert service.authorize("senha-correta", master_password_is_valid) is True

    second_start = make_service(tmp_path)
    status = second_start.evaluate()
    assert status.authorized is True
    assert status.installation_id
    assert status.activated_at == "2026-08-22T12:30:00+00:00"


def test_fingerprint_diferente_bloqueia_o_mesmo_registro(tmp_path):
    service = make_service(tmp_path)
    assert service.authorize("senha-correta", master_password_is_valid)

    other_machine = make_service(tmp_path, machine=MACHINE_B)
    status = other_machine.evaluate()
    assert status.authorized is False
    assert status.reason == "MACHINE_MISMATCH"


def test_arquivo_adulterado_bloqueia(tmp_path):
    service = make_service(tmp_path)
    assert service.authorize("senha-correta", master_password_is_valid)
    saved = service.authorization_file.read_bytes()
    service.authorization_file.write_bytes(saved[:-1] + bytes([saved[-1] ^ 0x01]))

    status = service.evaluate()
    assert status.authorized is False
    assert status.reason == "INVALID"


def test_arquivo_removido_bloqueia_novamente(tmp_path):
    service = make_service(tmp_path)
    assert service.authorize("senha-correta", master_password_is_valid)
    service.authorization_file.unlink()
    assert service.evaluate().reason == "MISSING"


def test_senha_errada_nao_cria_nem_altera_autorizacao(tmp_path):
    service = make_service(tmp_path)
    assert service.authorize("errada", master_password_is_valid) is False
    assert not service.authorization_file.exists()
    assert service.evaluate().authorized is False

    assert service.authorize("senha-correta", master_password_is_valid) is True
    saved = service.authorization_file.read_bytes()
    assert service.authorize("errada", master_password_is_valid) is False
    assert service.authorization_file.read_bytes() == saved


def test_senha_correta_autoriza_somente_o_fingerprint_atual(tmp_path):
    service = make_service(tmp_path)
    assert service.authorize("senha-correta", master_password_is_valid)
    assert service.evaluate().authorized is True
    assert make_service(tmp_path, machine=MACHINE_B).evaluate().authorized is False


def test_copia_ou_restauracao_do_banco_nao_transporta_autorizacao(tmp_path):
    source_appdata = tmp_path / "origem"
    target_appdata = tmp_path / "destino"
    source_service = make_service(source_appdata)
    assert source_service.authorize("senha-correta", master_password_is_valid)
    source_database = source_appdata / "fichario_moveis.db"
    source_database.write_bytes(b"sqlite-simulado")

    target_appdata.mkdir()
    shutil.copy2(source_database, target_appdata / source_database.name)

    target_service = make_service(target_appdata)
    assert (target_appdata / source_database.name).exists()
    assert target_service.evaluate().reason == "MISSING"


def test_appdata_copiado_para_outra_maquina_falha_no_escopo_dpapi(tmp_path):
    source = tmp_path / "origem"
    target = tmp_path / "destino"
    service = make_service(source, protector=BoundProtector(b"machine-a"))
    assert service.authorize("senha-correta", master_password_is_valid)
    shutil.copytree(source, target)

    copied = make_service(
        target,
        machine=MACHINE_B,
        protector=BoundProtector(b"machine-b"),
    )
    assert copied.evaluate().authorized is False
    assert copied.evaluate().reason == "INVALID"


def test_perfil_teste_nao_bloqueia_nem_persiste_autorizacao(tmp_path):
    def unavailable_machine():
        raise AssertionError("Perfil TESTE não deve depender do fingerprint para permitir abertura.")

    service = InstallationAuthorizationService(
        profile="TESTE",
        authorization_file=tmp_path / "authorization.dat",
        protector=BoundProtector(b"test"),
        machine_components_provider=unavailable_machine,
    )
    status = service.evaluate()
    assert status.required is False
    assert status.authorized is True
    assert status.reason == "PROFILE_BYPASS"
    assert not service.authorization_file.exists()


def test_remocao_exige_senha_e_proxima_avaliacao_bloqueia(tmp_path):
    service = make_service(tmp_path)
    assert service.authorize("senha-correta", master_password_is_valid)
    assert service.remove_authorization("errada", master_password_is_valid) is False
    assert service.evaluate().authorized is True
    assert service.remove_authorization("senha-correta", master_password_is_valid) is True
    assert service.evaluate().reason == "MISSING"


def test_tentativas_excessivas_aplicam_cooldown_local_simples(tmp_path):
    current = [100.0]
    service = make_service(tmp_path, clock=lambda: current[0])
    for _ in range(service.MAX_FAILED_ATTEMPTS):
        assert service.authorize("errada", master_password_is_valid) is False
    assert service.authorize("senha-correta", master_password_is_valid) is False
    current[0] += service.COOLDOWN_SECONDS
    assert service.authorize("senha-correta", master_password_is_valid) is True


def test_registro_nao_persiste_identificadores_brutos(tmp_path):
    service = make_service(tmp_path)
    assert service.authorize("senha-correta", master_password_is_valid)
    decrypted = service.protector.unprotect(service.authorization_file.read_bytes())
    assert MACHINE_A["machine_guid"].encode() not in decrypted
    assert MACHINE_A["system_volume_serial"].encode() not in decrypted
    assert b"senha-correta" not in decrypted


def test_dpapi_da_autorizacao_usa_escopo_da_maquina(tmp_path):
    service = InstallationAuthorizationService.for_windows(
        profile="PRODUCAO",
        app_dir=tmp_path,
    )
    assert isinstance(service.protector, WindowsDataProtector)
    assert service.protector.machine_scope is True
    assert service.authorization_file.parent == tmp_path / "authorization"
    assert WindowsDataProtector().machine_scope is False
