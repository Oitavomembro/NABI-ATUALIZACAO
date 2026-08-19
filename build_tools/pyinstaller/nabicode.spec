# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).resolve().parents[1]
version_file = project_root / "VERSAO.txt"
revision_file = project_root / "REVISAO.txt"
production_profile = project_root / "build_tools" / "resources" / "PERFIL_NABICODE.txt"
production_runtime_hook = project_root / "build_tools" / "pyinstaller" / "runtime_production_profile.py"
optional_app_icon = project_root / "build_tools" / "resources" / "NabiCode.ico"
version = version_file.read_text(encoding="utf-8-sig").strip()
name = f"NabiCode_v{version.replace('.', '_')}"

datas = [
    (str(version_file), "."),
    (str(revision_file), "."),
    (str(production_profile), "."),
    (str(project_root / "resources" / "fiscal" / "schemas"), "resources/fiscal/schemas"),
    (str(project_root / "resources" / "fiscal" / "catalogs"), "resources/fiscal/catalogs"),
    (str(project_root / "resources" / "fiscal" / "icp_brasil"), "resources/fiscal/icp_brasil"),
]
binaries = []
hiddenimports = [
    "cryptography.x509",
    "cryptography.hazmat.backends.openssl",
    "cryptography.hazmat.primitives.serialization.pkcs12",
    "cryptography.hazmat.bindings._rust",
    "lxml.etree",
    "requests.adapters",
    "urllib3",
    "certifi",
    "openpyxl",
    "openpyxl.styles",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.figure",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "PIL.ImageTk",
    "pygame",
    "splash_deep_trust_engine",
    "reportlab.lib.colors",
    "reportlab.lib.pagesizes",
    "reportlab.lib.styles",
    "reportlab.lib.units",
    "reportlab.platypus",
    "reportlab.pdfgen.canvas",
    "reportlab.graphics.renderPDF",
    "reportlab.graphics.barcode.qr",
    "reportlab.graphics.shapes",
    "brazilfiscalreport.danfe",
    "brazilfiscalreport.utils",
    "fpdf",
    "barcode",
    "phonenumbers",
    "defusedxml.ElementTree",
    "win32con",
    "win32print",
    "win32ui",
    "pywintypes",
]

datas = list(dict.fromkeys(datas))
hiddenimports = list(dict.fromkeys(hiddenimports))
hiddenimports.extend(collect_submodules("brazilfiscalreport"))
hiddenimports.extend(collect_submodules("barcode"))
hiddenimports = list(dict.fromkeys(hiddenimports))

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(production_runtime_hook)],
    excludes=[
        "pytest",
        "tests",
        "benchmark_tests",
        "stress_tests",
        "soak_tests",
        "matplotlib.tests",
        "matplotlib.testing",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe_options = {}
if optional_app_icon.is_file():
    exe_options["icon"] = str(optional_app_icon)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    contents_directory="_internal",
    **exe_options,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=name,
)
