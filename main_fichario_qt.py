from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from commercial.infrastructure.runtime import create_commercial_container
from core.runtime_profile import DatabaseUsageLock
from database import DatabaseManager
from fichario.license_policy import FicharioLicensePolicy
from fichario.profile import configure_fichario_profile
from fichario.runtime import initialize_fichario_database
from fichario.shell import FicharioWindow, LoginDialog
from licensing.restricted_commands import handle_restricted_command
from licensing.runtime import build_runtime_license_service
from repositories.system_repository import SystemRepository
from services.security_service import SecurityService


def main(argv=None) -> int:
    arguments = list(argv if argv is not None else sys.argv)
    qt = QApplication.instance() or QApplication(arguments)
    profile = configure_fichario_profile("PRODUCAO")
    restricted = handle_restricted_command(arguments[1:], profile)
    if restricted is not None: return restricted
    license_service = build_runtime_license_service(profile.app_dir)
    policy = FicharioLicensePolicy(license_service.evaluate())
    if not policy.operational:
        QMessageBox.warning(None, "Licenca NabiCode Fichario", policy.message)
        return 3
    database_path = profile.validate_database(profile.paths.database)
    lock = DatabaseUsageLock(database_path, f"{profile.profile}-FICHARIO")
    window = None
    try:
        lock.acquire()
        database = DatabaseManager(database_path, logger=logging.getLogger("NabiCode.Fichario"))
        initialize_fichario_database(database, profile)
        container = create_commercial_container(database, pdf_dir=profile.paths.pdfs)
        system = SystemRepository(database.connect)
        security = SecurityService(database.connect)
        security.bootstrap_admin(system.get_config("admin_senha_hash"))
        login = LoginDialog(security)
        if login.exec() != QDialog.DialogCode.Accepted: return 0
        window = FicharioWindow(
            container, database, profile, security, login.session
        )
        window.show()
        timer = QTimer(qt); timer.setInterval(60_000)

        def monitor_license() -> None:
            current = FicharioLicensePolicy(license_service.evaluate())
            if current.operational: return
            timer.stop()
            QMessageBox.warning(window, "Licenca NabiCode Fichario", current.message)
            qt.quit()

        timer.timeout.connect(monitor_license); timer.start()
        return qt.exec()
    except Exception as error:
        QMessageBox.critical(None, "NabiCode Fichario", str(error) or "Falha ao iniciar.")
        return 1
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
