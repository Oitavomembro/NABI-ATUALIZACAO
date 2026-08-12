"""Runtime hook exclusivo do artefato Windows de PRODUCAO.

O layout onedir moderno mantém datas em ``_internal``. Este hook roda antes de
``main.py`` e publica o perfil/versão empacotados sem alterar o perfil TESTE da
árvore-fonte.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


runtime_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
profile_file = runtime_root / "PERFIL_NABICODE.txt"
version_file = runtime_root / "VERSAO.txt"

try:
    packaged_profile = profile_file.read_text(encoding="utf-8-sig").strip().upper()
except (OSError, UnicodeError) as exc:
    raise RuntimeError(f"Perfil de produção empacotado indisponível: {profile_file}") from exc

if packaged_profile != "PRODUCAO":
    raise RuntimeError(f"Perfil empacotado inválido: {packaged_profile!r}")

# O artefato instalado é deliberadamente PRODUCAO. A árvore-fonte continua
# usando seu marcador TESTE e não é afetada por este hook.
os.environ["NABICODE_PROFILE"] = packaged_profile
os.environ["NABICODE_VERSION_FILE"] = str(version_file)
