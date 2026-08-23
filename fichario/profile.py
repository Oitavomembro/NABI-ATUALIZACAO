from __future__ import annotations

import os
from pathlib import Path

from core.runtime_profile import RuntimeProfile, load_packaged_profile


def configure_fichario_profile(default: str = "PRODUCAO") -> RuntimeProfile:
    """Mantem dados mutaveis da edicao fora do executavel/Program Files."""

    profile = load_packaged_profile(default)
    roaming = Path(os.environ.get("APPDATA") or Path.home())
    app_dir = roaming / "NabiCode" / "Fichario" / (
        "Producao" if profile == "PRODUCAO" else "Teste"
    )
    app_dir.mkdir(parents=True, exist_ok=True)
    os.environ["NABICODE_PROFILE"] = profile
    os.environ["NABICODE_APP_DIR"] = str(app_dir)
    os.environ["NABICODE_EDITION"] = "FICHARIO"
    return RuntimeProfile(profile=profile, app_dir=app_dir)
