from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "build_tools" / "pyinstaller" / "nabicode_fichario.spec"
INNO = ROOT / "build_tools" / "inno" / "NabiCode_Fichario_Offline.iss"
OUTPUT = ROOT / "build_output" / "fichario"


def validate_sources() -> None:
    entry = (ROOT / "main_fichario_qt.py").read_text(encoding="utf-8").casefold()
    own = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in sorted((ROOT / "fichario").glob("*.py"))
    )
    forbidden = ("assistant_nabi", "fiscalworker", "sefaz", "certificado", "nfe")
    found = [term for term in forbidden if term in entry or term in own]
    if found:
        raise RuntimeError(f"Composicao FICHARIO contem referencia proibida: {', '.join(found)}")
    spec = SPEC.read_text(encoding="utf-8").casefold()
    if "resources/fiscal" in spec or "main_qt.py\")" in spec:
        raise RuntimeError("Spec FICHARIO incluiu recurso de outra edicao.")


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build offline do NabiCode Fichario")
    parser.add_argument("target", choices=("validate", "app", "installer", "all"))
    parser.add_argument("--iscc", help="Caminho absoluto do ISCC.exe")
    args = parser.parse_args(argv)
    validate_sources()
    if args.target == "validate": return 0
    version = (ROOT / "VERSAO.txt").read_text(encoding="utf-8-sig").strip()
    dist = OUTPUT / "dist"; work = OUTPUT / "work"
    if args.target in {"app", "all"}:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / "BUILD_INFO.txt").write_text(
            datetime.now().strftime("%d/%m/%Y %H:%M:%S") + "\n", encoding="utf-8",
        )
        run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
             "--distpath", str(dist), "--workpath", str(work), str(SPEC)])
        helper_dist = OUTPUT / "helper_dist"
        run([
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--onefile", "--noconsole", "--name", "NabiCode_Fichario_Updater",
            "--distpath", str(helper_dist), "--workpath", str(OUTPUT / "helper_work"),
            "--specpath", str(OUTPUT / "helper_spec"),
            "--paths", str(ROOT), str(ROOT / "build_tools" / "fichario_update_helper.py"),
        ])
        distribution = dist / f"NabiCode_Fichario_v{version.replace('.', '_')}"
        shutil.copy2(helper_dist / "NabiCode_Fichario_Updater.exe", distribution)
    if args.target in {"installer", "all"}:
        iscc = Path(args.iscc).resolve() if args.iscc else Path(
            shutil.which("ISCC.exe") or ""
        )
        if not iscc.is_file():
            raise RuntimeError("Informe --iscc com o caminho absoluto do ISCC.exe.")
        distribution = dist / f"NabiCode_Fichario_v{version.replace('.', '_')}"
        if not distribution.is_dir():
            raise FileNotFoundError("Gere o aplicativo FICHÁRIO antes do instalador.")
        short_root = Path(tempfile.mkdtemp(prefix="NBF_"))
        short_dist = short_root / "app"
        try:
            shutil.copytree(distribution, short_dist)
            run([
                str(iscc), f"/DAppVersion={version}",
                f"/DDistSource={short_dist}", str(INNO),
            ])
        finally:
            shutil.rmtree(short_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
