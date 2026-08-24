"""Telas Qt administrativas, desacopladas do shell principal."""

from .module_hub import AdministrativeModule, AdministrativeModuleHub
from .composition import build_administrative_modules
from .login_dialog import ApplicationLoginDialog

__all__ = ["AdministrativeModule", "AdministrativeModuleHub", "ApplicationLoginDialog", "build_administrative_modules"]
