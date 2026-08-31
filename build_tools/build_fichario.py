from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build_tools.product_lane_guard import validate_product_lane


SPEC = ROOT / "build_tools" / "pyinstaller" / "nabicode_fichario.spec"
INNO = ROOT / "build_tools" / "inno" / "NabiCode_Fichario_Offline.iss"
OUTPUT = ROOT / "build_output" / "fichario"
FICHARIO_SOURCE_CONTRACT = {
    "main_fichario_qt.py": "d998c7b588069411b080a4da5b3f1eb6488de9a5fabaec0e4e1f8733153deba3",
    "fichario": "b6f414ca82c0339aa251e7884146d56c5424cbaee67f62904b7b8707206ed132",
    "commercial": "958cb34e396dc6436b07a4a4c943799b2f24c16d9fdaa889fe928a484845c1da",
    "ui_qt/commercial": "8ead05d34625043c47656f338d2e48efb5c6fddc2739f1b2e3a0e5f539f32f5d",
    "licensing": "7c331803c5bdb1ba79c8a817f7c63c9ba1f71cbbc604a27057c8b7ea00a15d0d",
}


def validate_sources() -> None:
    validate_product_lane(
        ROOT,
        product="FICHARIO R21",
        expected_digests=FICHARIO_SOURCE_CONTRACT,
    )
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
            "--uac-admin",
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
