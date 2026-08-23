# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_root = Path(SPECPATH).resolve().parents[1]

# O emissor é deliberadamente separado: não incorpora catálogo real, chave,
# banco, perfil, runtime do NabiCode, IA ou serviços fiscais.
a = Analysis(
    [str(project_root / "license_issuer_app.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "cryptography.hazmat.primitives.asymmetric.ed25519",
        "cryptography.hazmat.primitives.serialization",
        "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "assistant_nabi", "ui_qt.assistant_nabi", "commercial", "services",
        "nabicode_legacy", "main", "main_qt", "tests", "pytest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="NabiCode_Emissor_Licencas_V2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
