# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import shutil
import sys
import zipfile

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
    (str(project_root / "build_output" / "fichario" / "BUILD_INFO.txt"), "."),
]

# Python 3.14 distribui Tcl/Tk em ZIPs. O hook atual do PyInstaller procura
# diretórios tradicionais e, sem esta extração determinística, gera um EXE que
# falha antes mesmo de a interface Qt abrir.
tcl_source = Path(sys.base_prefix) / "tcl"
tcl_runtime = project_root / "build_output" / "fichario" / "tcl_runtime"
if tcl_runtime.exists():
    shutil.rmtree(tcl_runtime)
tcl_runtime.mkdir(parents=True)
for pattern, prefix, destination in (
    ("libtcl*.zip", "tcl_library/", "_tcl_data"),
    ("libtk*.zip", "tk_library/", "_tk_data"),
):
    archives = sorted(tcl_source.glob(pattern))
    if len(archives) != 1:
        raise RuntimeError(f"Runtime {pattern} não encontrado de forma única.")
    target = tcl_runtime / destination
    target.mkdir()
    with zipfile.ZipFile(archives[0]) as archive:
        for archive_name in archive.namelist():
            if not archive_name.startswith(prefix) or archive_name.endswith("/"):
                continue
            relative = Path(archive_name[len(prefix):])
            output = target / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.read(archive_name))
    datas.append((str(target), destination))
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
