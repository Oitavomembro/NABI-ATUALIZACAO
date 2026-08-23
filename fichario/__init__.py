"""Composicao independente da edicao NabiCode Fichario."""

from .license_policy import FicharioLicensePolicy
from .profile import configure_fichario_profile

__all__ = ["FicharioLicensePolicy", "configure_fichario_profile"]
