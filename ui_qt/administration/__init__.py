"""Telas Qt administrativas, desacopladas do shell principal."""

from .module_hub import AdministrativeModule, AdministrativeModuleHub
from .composition import build_administrative_modules
from .login_dialog import ApplicationLoginDialog
from .settings_dialog import SettingsDialog
from .help_dialog import HelpDialog

__all__ = ["AdministrativeModule", "AdministrativeModuleHub", "ApplicationLoginDialog", "SettingsDialog", "HelpDialog", "build_administrative_modules"]
