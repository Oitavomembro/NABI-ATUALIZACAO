from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import uuid
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _TemporaryProtector:
    """Proteção exclusiva do ensaio; não representa DPAPI de produção."""

    prefix = b"NABICODE-FIRST-USE-TEST\0"

    def protect(self, value: bytes) -> bytes:
        return self.prefix + value

    def unprotect(self, value: bytes) -> bytes:
        if not value.startswith(self.prefix):
            raise ValueError("Estado temporário incompatível.")
        return value[len(self.prefix):]


@contextmanager
def _isolated_environment(root: Path):
    names = ("APPDATA", "NABICODE_PROFILE", "NABICODE_APP_DIR", "QT_QPA_PLATFORM")
    previous = {name: os.environ.get(name) for name in names}
    os.environ.update({
        "APPDATA": str(root / "AppData"),
        "NABICODE_PROFILE": "TESTE",
        "QT_QPA_PLATFORM": "offscreen",
    })
    os.environ.pop("NABICODE_APP_DIR", None)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _activate_ephemeral_license(root: Path) -> dict[str, object]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from licensing.gate import Capability, LicenseGate
    from licensing.license_format import create_envelope
    from licensing.models import LicenseEdition, LicensePayload
    from licensing.service import LicenseV2Service
    from licensing.storage import ProtectedStateStore

    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    fingerprint = hashlib.sha256(b"nabicode-first-use-temporary-machine").hexdigest()
    now = datetime.now(timezone.utc)
    license_root = root / "ephemeral_license"
    service = LicenseV2Service(
        license_path=license_root / "current.nabilic",
        state_store=ProtectedStateStore(
            license_root / "state.dat", _TemporaryProtector()
        ),
        public_keys={"temporary-first-use-test": public},
        machine_fingerprint=lambda: fingerprint,
        now=lambda: now,
    )
    payload = LicensePayload(
        schema=2,
        license_id=str(uuid.uuid4()),
        edition=LicenseEdition.COMMERCIAL,
        customer_name="HOMOLOGACAO TEMPORARIA",
        machine_fingerprint=fingerprint,
        issued_at=now,
        valid_until=date.today() + timedelta(days=1),
        grace_days=10,
        features=("commercial", "financial", "legacy", "qt"),
        revoked=False,
    )
    source = root / "temporary-test-license.nabilic"
    source.write_bytes(create_envelope(
        payload, key_id="temporary-first-use-test", signer=private
    ))
    decision = service.activate(source)
    source.unlink(missing_ok=True)
    gate = LicenseGate(decision)
    if not gate.allows(Capability.QT):
        raise RuntimeError("A licença efêmera do ensaio não liberou o Qt.")
    return {"state": decision.state.value, "qt_allowed": True, "private_key_saved": False}


def _runtime_dependency_audit() -> dict[str, object]:
    import sysconfig
    import tkinter
    from PySide6.QtCore import QLibraryInfo

    plugin_root = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
    platforms = plugin_root / "platforms"
    tcl_library_value = str(tkinter.Tcl().eval("info library"))
    tcl_root = Path(sysconfig.get_path("data")) / "tcl"
    tcl_runtime = (
        (not tcl_library_value.startswith("//zipfs:") and Path(tcl_library_value).is_dir())
        or any(tcl_root.glob("libtcl*.zip"))
    )
    tk_runtime = any(tcl_root.glob("libtk*.zip")) or (tcl_root / "tk9.0").is_dir()
    checks = {
        "qt_plugins": plugin_root.is_dir(),
        "qt_platforms": platforms.is_dir() and any(platforms.glob("q*windows*.dll")),
        "tcl_library": tcl_runtime,
        "tk_library": tk_runtime,
        "trusted_public_catalog": (ROOT / "licensing" / "trusted_public_keys.json").is_file(),
        "official_spec": (ROOT / "build_tools" / "pyinstaller" / "nabicode.spec").is_file(),
    }
    if not all(checks.values()):
        missing = ", ".join(name for name, present in checks.items() if not present)
        raise RuntimeError(f"Dependências de runtime ausentes: {missing}")
    return checks


def run(root: Path) -> dict[str, object]:
    root = root.resolve()
    active_appdata = Path(os.environ.get("APPDATA") or Path.home()).resolve()
    active_nabicode = active_appdata / "NabiCode"
    if root == active_nabicode or active_nabicode in root.parents:
        raise RuntimeError("O ensaio não pode usar o diretório ativo do NabiCode.")
    if root.exists() and any(root.iterdir()):
        raise RuntimeError("O diretório do ensaio deve estar vazio.")
    root.mkdir(parents=True, exist_ok=True)
    network_error = RuntimeError("Rede bloqueada durante a homologação descartável.")
    with (
        _isolated_environment(root),
        mock.patch("socket.create_connection", side_effect=network_error),
        mock.patch("socket.socket.connect", side_effect=network_error),
    ):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from core.runtime_profile import configure_profile_environment
        from database import DatabaseManager
        from licensing.gate import Capability
        from licensing.runtime import evaluate_runtime_gate
        import main_qt
        from repositories.system_repository import SystemRepository
        from services.security_service import SecurityService
        from ui_qt.administration.composition import build_administrative_modules
        from ui_qt.app import create_shell_application

        profile = configure_profile_environment("TESTE")
        expected_app_dir = (root / "AppData" / "NabiCode" / "Teste").resolve()
        if profile.profile != "TESTE" or profile.app_dir != expected_app_dir:
            raise RuntimeError("O perfil de homologação escapou do diretório temporário.")

        database_path = profile.validate_database(profile.paths.database)
        absent_gate = evaluate_runtime_gate(profile.app_dir)
        restricted_ok = (
            not absent_gate.allows(Capability.QT)
            and absent_gate.allows(Capability.ACTIVATE)
            and absent_gate.allows(Capability.DIAGNOSTIC)
            and not database_path.exists()
        )
        if not restricted_ok:
            raise RuntimeError("Licença ausente não permaneceu restrita antes do banco.")

        license_result = _activate_ephemeral_license(root)
        database = DatabaseManager(database_path, logger=None)
        first_install = main_qt._initialize(database, profile, False, "local")
        if not first_install or not database_path.is_file():
            raise RuntimeError("O banco descartável de primeira instalação não foi criado.")

        security = SecurityService(database.connect)
        if security.has_users():
            raise RuntimeError("O banco novo nasceu com usuário administrativo.")
        security.complete_initial_setup(
            username="admin_teste",
            display_name="Administrador de Homologação",
            password="Teste-Seguro-2026",
            store_name="Empresa de Homologação",
            document="",
            email="",
        )
        if security.session is not None:
            raise RuntimeError("O primeiro acesso criou sessão implícita.")
        if security.authenticate("admin_teste", "senha-incorreta") is not None:
            raise RuntimeError("O login aceitou senha incorreta.")
        session = security.authenticate("admin_teste", "Teste-Seguro-2026")
        if session is None:
            raise RuntimeError("O administrador recém-criado não conseguiu entrar.")

        container = main_qt.create_commercial_container(
            database, pdf_dir=profile.paths.pdfs
        )
        modules = build_administrative_modules(
            container, database, profile, security,
            terminal="CAIXA-TESTE", app_version="HOMOLOGACAO",
            schema_version=main_qt.SCHEMA_VERSION,
        )
        qt = QApplication.instance() or QApplication([])
        qt.setQuitOnLastWindowClosed(False)
        qt, shell = create_shell_application(
            container.application,
            security,
            modules,
            [],
            store_name="Empresa de Homologação",
            profile_label="TESTE • COMERCIAL / NÃO FISCAL",
        )
        shell.show()
        qt.processEvents()
        pdv = shell.ensure_pdv()
        qt.processEvents()
        if pdv is None or not pdv.isVisible():
            raise RuntimeError("Vendas não abriu pelo shell no perfil descartável.")
        pdv.close()
        shell.close()
        QTimer.singleShot(0, qt.quit)
        qt.exec()

        with closing(database.connect()) as connection:
            schema = int(connection.execute(
                "SELECT valor FROM configuracoes WHERE chave='db_schema_version'"
            ).fetchone()[0])
            users = json.loads(connection.execute(
                "SELECT valor FROM configuracoes WHERE chave=?",
                (SecurityService.CONFIG_KEY,),
            ).fetchone()[0])["users"]

        result = {
            "profile": profile.profile,
            "isolated_root": str(root),
            "license_absent_restricted": restricted_ok,
            "ephemeral_license": license_result,
            "database_created": True,
            "schema_version": schema,
            "first_admin_created": list(users) == ["admin_teste"],
            "login_required_and_validated": True,
            "shell_opened": True,
            "sales_opened": True,
            "fiscal_network_used": False,
            "runtime_dependencies": _runtime_dependency_audit(),
        }
        (root / "homologacao_primeiro_uso.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Homologa o primeiro uso em ambiente descartável.")
    parser.add_argument("--root", type=Path, help="Diretório TEMP vazio a usar e preservar.")
    parser.add_argument("--keep", action="store_true", help="Preserva um TEMP criado automaticamente.")
    args = parser.parse_args(argv)
    if args.root:
        result = run(args.root)
    elif args.keep:
        root = Path(tempfile.mkdtemp(prefix="nabicode-primeiro-uso-"))
        result = run(root)
    else:
        with tempfile.TemporaryDirectory(prefix="nabicode-primeiro-uso-") as folder:
            result = run(Path(folder))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
