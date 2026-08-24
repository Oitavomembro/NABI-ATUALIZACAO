"""Telas Qt administrativas, desacopladas do shell principal."""

from .module_hub import AdministrativeModule, AdministrativeModuleHub
from .composition import build_administrative_modules
from .login_dialog import ApplicationLoginDialog
from .settings_dialog import SettingsDialog
from .help_dialog import HelpDialog
from .audit_dialog import AuditDialog

__all__ = ["AdministrativeModule", "AdministrativeModuleHub", "ApplicationLoginDialog", "SettingsDialog", "HelpDialog", "AuditDialog", "build_administrative_modules"]
