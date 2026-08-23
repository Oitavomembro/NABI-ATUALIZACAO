# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_root = Path(SPECPATH).resolve().parents[1]
version_file = project_root / "VERSAO.txt"
revision_file = project_root / "REVISAO.txt"
production_profile = project_root / "build_tools" / "resources" / "PERFIL_NABICODE.txt"
runtime_hook = project_root / "build_tools" / "pyinstaller" / "runtime_production_profile.py"
optional_icon = project_root / "build_tools" / "resources" / "NabiCode.ico"
version = version_file.read_text(encoding="utf-8-sig").strip()
name = f"NabiCode_Fichario_v{version.replace('.', '_')}"

datas = [
    (str(version_file), "."),
    (str(revision_file), "."),
    (str(production_profile), "."),
    (str(project_root / "licensing" / "trusted_public_keys.json"), "licensing"),
]
hiddenimports = [
    "cryptography.hazmat.primitives.asymmetric.ed25519",
    "cryptography.hazmat.bindings._rust",
    "reportlab.pdfgen.canvas",
    "reportlab.graphics.barcode.qr",
    "win32con", "win32print", "win32ui", "pywintypes",
]
excludes = [
    "pytest", "tests", "benchmark_tests", "stress_tests", "soak_tests",
    "assistant_nabi", "ui_qt.assistant_nabi", "license_issuer",
    "services.fiscal_service", "services.fiscal_worker",
    "services.fiscal_outbox_worker", "services.sefaz_service",
    "brazilfiscalreport", "lxml", "requests",
]

a = Analysis(
    [str(project_root / "main_fichario_qt.py")],
    pathex=[str(project_root)], binaries=[], datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[str(runtime_hook)], excludes=excludes,
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
options = {"icon": str(optional_icon)} if optional_icon.is_file() else {}
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name=name, console=False,
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    contents_directory="_internal", **options,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=name)
