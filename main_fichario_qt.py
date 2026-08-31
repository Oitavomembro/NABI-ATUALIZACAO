from __future__ import annotations

import logging
import sys
from dataclasses import replace

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from commercial.infrastructure.runtime import create_commercial_container
from core.runtime_profile import DatabaseUsageLock
from database import DatabaseManager
from fichario.license_policy import FicharioLicensePolicy
from fichario.license_dialog import FicharioLicenseDialog
from fichario.profile import configure_fichario_profile
from fichario.runtime import initialize_fichario_database
from fichario.shell import FicharioWindow, LoginDialog
from fichario.user_service import FicharioSecurityService
from fichario.users_dialog import AccountDialog
from fichario.authenticated_operations import (
    FicharioTransactionService, FicharioFinanceRepository,
    AuthenticatedReceipts, AuthenticatedCustomers,
)
from fichario.update_runtime import FicharioUpdateRuntime
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
        activation = FicharioLicenseDialog(license_service, policy)
        if activation.exec() != QDialog.DialogCode.Accepted:
            return 3
        policy = FicharioLicensePolicy(license_service.evaluate())
        if not policy.operational:
            return 3
    database_path = profile.validate_database(profile.paths.database)
    lock = DatabaseUsageLock(database_path, f"{profile.profile}-FICHARIO")
    window = None
    try:
        lock.acquire()
        database = DatabaseManager(database_path, logger=logging.getLogger("NabiCode.Fichario"))
        initialize_fichario_database(database, profile)
        update_result = FicharioUpdateRuntime(profile, database_path).validate_after_restart()
        if update_result and update_result.get("restart_required"):
            return 4
        system = SystemRepository(database.connect)
        security = FicharioSecurityService(database.connect)
        security.bootstrap_admin(system.get_config("admin_senha_hash"))
        if security.needs_setup():
            if AccountDialog(security, setup=True).exec() != QDialog.DialogCode.Accepted:
                return 0
        login = LoginDialog(security)
        if login.exec() != QDialog.DialogCode.Accepted:
            return 0
        session = security.session
        container = create_commercial_container(
            database, pdf_dir=profile.paths.pdfs,
            transaction_factory=lambda *args, **kwargs: FicharioTransactionService(
                *args, security=security, **kwargs
            ),
            finance_repository_factory=lambda db: FicharioFinanceRepository(db, security=security),
        )
        container = replace(
            container,
            actions=AuthenticatedReceipts(container.actions, security),
            customer_application=AuthenticatedCustomers(container.customer_application, security),
        )
        window = FicharioWindow(
            container, database, profile, security, session
        )
        window.show()
        if update_result and update_result.get("ok"):
            QTimer.singleShot(0, lambda: QMessageBox.information(
                window, "Atualização concluída",
                f"Versão {update_result['report']['versao']} — "
                f"revisão {update_result['report']['revisao']} validada.\n"
                "Banco e vínculos preservados.",
            ))
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
