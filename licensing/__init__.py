"""Licenciamento offline V2 do NabiCode.

Somente chaves públicas pertencem ao runtime. Emissão é uma ferramenta externa.
"""

from .gate import Capability, LicenseGate
from .models import LicenseDecision, LicenseEdition, LicensePayload, LicenseState
from .service import LicenseV2Service

__all__ = [
    "Capability", "LicenseDecision", "LicenseEdition", "LicenseGate",
    "LicensePayload", "LicenseState", "LicenseV2Service",
]
