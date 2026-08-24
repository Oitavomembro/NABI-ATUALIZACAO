"""Telas Qt administrativas, desacopladas do shell principal."""

from .module_hub import AdministrativeModule, AdministrativeModuleHub
from .composition import build_administrative_modules
from .login_dialog import ApplicationLoginDialog
from .settings_dialog import SettingsDialog

__all__ = ["AdministrativeModule", "AdministrativeModuleHub", "ApplicationLoginDialog", "SettingsDialog", "build_administrative_modules"]
