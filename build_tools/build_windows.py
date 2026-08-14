"""Build Windows onedir reproduzível e validação dos artefatos offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = PROJECT_ROOT / "build_output"
SPEC_FILE = PROJECT_ROOT / "build_tools" / "pyinstaller" / "nabicode.spec"
INNO_SCRIPT = PROJECT_ROOT / "build_tools" / "inno" / "NabiCode_Offline.iss"
LOCK_FILE = PROJECT_ROOT / "build_tools" / "requirements-windows.lock"
REQUIRED_SOURCE_FILES = (
    "main.py",
    "splash_deep_trust_engine.py",
    "VERSAO.txt",
    "REVISAO.txt",
    "requirements.txt",
    "build_tools/pyinstaller/nabicode.spec",
    "build_tools/pyinstaller/runtime_production_profile.py",
    "build_tools/resources/PERFIL_NABICODE.txt",
    "build_tools/requirements-windows.lock",
)
REQUIRED_DISTRIBUTIONS = (
    "customtkinter",
    "Pillow",
    "pygame-ce",
    "requests",
    "cryptography",
    "lxml",
    "reportlab",
    "openpyxl",
    "matplotlib",
    "pywin32",
    "PyInstaller",
    "pyinstaller-hooks-contrib",
)
FORBIDDEN_PARTS = {
    ".venv",
    ".build-venv",
    "__pycache__",
    ".pytest_cache",
    "test",
    "tests",
    "testing",
    "benchmark_tests",
    "stress_tests",
    "soak_tests",
    "wheelhouse",
}
FORBIDDEN_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".py",
    ".pyc",
    ".pyi",
    ".pyw",
    ".pfx",
    ".p12",
    ".pem",
    ".key",
}
PYINSTALLER_CONTENTS_DIR = "_internal"
ALLOWED_PUBLIC_CERTIFICATE_BUNDLES = {"_internal/certifi/cacert.pem"}
MAX_WINDOWS_PROJECT_ROOT_CHARS = 80


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_version(root: Path = PROJECT_ROOT) -> str:
    value = (root / "VERSAO.txt").read_text(encoding="utf-8-sig").strip()
    parts = value.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise RuntimeError(f"VERSAO.txt inválido: {value!r}")
    return value


def distribution_name(root: Path = PROJECT_ROOT) -> str:
    return f"NabiCode_v{read_version(root).replace('.', '_')}"


def validate_source(root: Path = PROJECT_ROOT) -> list[str]:
    errors = [f"Ausente: {item}" for item in REQUIRED_SOURCE_FILES if not (root / item).is_file()]
    if (root / "VERSAO.txt").is_file():
        try:
            read_version(root)
        except RuntimeError as exc:
            errors.append(str(exc))
    revision = root / "REVISAO.txt"
    if revision.is_file():
        try:
            if int(revision.read_text(encoding="utf-8-sig").strip()) < 0:
                raise ValueError
        except (OSError, UnicodeError, TypeError, ValueError):
            errors.append("REVISAO.txt inválido; informe um inteiro não negativo.")
    profile = root / "build_tools" / "resources" / "PERFIL_NABICODE.txt"
    if profile.is_file() and profile.read_text(encoding="utf-8-sig").strip() != "PRODUCAO":
        errors.append("O perfil do artefato final não é PRODUCAO.")
    return errors


def validate_windows_build_path(root: Path = PROJECT_ROOT) -> list[str]:
    resolved = str(root.resolve())
    if len(resolved) <= MAX_WINDOWS_PROJECT_ROOT_CHARS:
        return []
    return [
        "Caminho do projeto excessivamente longo para o build Windows "
        f"({len(resolved)} caracteres; máximo conservador {MAX_WINDOWS_PROJECT_ROOT_CHARS}). "
        r"Use um caminho curto, por exemplo C:\NB\NabiCode."
    ]


def validate_build_environment() -> list[str]:
    errors: list[str] = []
    if platform.system() != "Windows":
        errors.append("O build final deve ser executado no Windows; PyInstaller não faz cross-build.")
    else:
        errors.extend(validate_windows_build_path())
    if sys.version_info[:2] != (3, 14):
        errors.append(f"Python 3.14.x obrigatório; encontrado {platform.python_version()}.")
    for package in REQUIRED_DISTRIBUTIONS:
        try:
            metadata.version(package)
        except metadata.PackageNotFoundError:
            errors.append(f"Dependência de build ausente: {package}")
    return errors


def clean_output(root: Path = BUILD_ROOT) -> None:
    resolved = root.resolve()
    if resolved.name != "build_output" or resolved.parent != PROJECT_ROOT.resolve():
        raise RuntimeError(f"Recusa de limpeza fora de build_output: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    for name in ("dist", "work", "installer", "tcl_tk_runtime", "manifest.json", "SHA256SUMS.txt", "smoke_version.txt", "startup_packaged.json"):
        target = resolved / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def prepare_tcl_tk_build_environment(
    *, python_root: Path | None = None, build_root: Path = BUILD_ROOT
) -> dict[str, str]:
    """Materializa os scripts Tcl/Tk distribuídos em zip pelo Python 3.14.

    O hook atual do PyInstaller espera diretórios físicos. Sem este passo o
    executável onedir nasce sem ``_tcl_data``/``_tk_data`` e encerra antes de
    executar ``main.py``.
    """

    root = (python_root or Path(sys.base_prefix)) / "tcl"
    archives = {
        "TCL_LIBRARY": (next(iter(sorted(root.glob("libtcl*.zip"))), None), "tcl_library"),
        "TK_LIBRARY": (next(iter(sorted(root.glob("libtk*.zip"))), None), "tk_library"),
    }
    if not any(archive is not None for archive, _ in archives.values()):
        return {}
    if not all(archive is not None for archive, _ in archives.values()):
        raise RuntimeError("Distribuição Python possui apenas parte dos arquivos Tcl/Tk.")

    destination = build_root / "tcl_tk_runtime"
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    environment: dict[str, str] = {}
    for variable, (archive, member_root) in archives.items():
        assert archive is not None
        target = destination / member_root
        with zipfile.ZipFile(archive) as bundle:
            prefix = member_root + "/"
            members = [item for item in bundle.infolist() if item.filename.startswith(prefix)]
            if not members:
                raise RuntimeError(f"Conteúdo {member_root} ausente em {archive.name}.")
            for item in members:
                relative = Path(item.filename).relative_to(member_root)
                output = (target / relative).resolve()
                if target.resolve() not in output.parents and output != target.resolve():
                    raise RuntimeError(f"Caminho inseguro no arquivo {archive.name}: {item.filename}")
                if item.is_dir():
                    output.mkdir(parents=True, exist_ok=True)
                else:
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(item) as source, output.open("wb") as sink:
                        shutil.copyfileobj(source, sink)
        environment[variable] = str(target)
    return environment


def forbidden_distribution_files(root: Path) -> list[str]:
    findings: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        folded = {part.casefold() for part in relative.parts}
        if folded & FORBIDDEN_PARTS:
            findings.append(relative.as_posix())
        elif (
            path.is_file()
            and path.suffix.casefold() in FORBIDDEN_SUFFIXES
            and relative.as_posix().casefold() not in ALLOWED_PUBLIC_CERTIFICATE_BUNDLES
        ):
            findings.append(relative.as_posix())
    return sorted(set(findings))


def distribution_resource(root: Path, filename: str) -> Path:
    """Resolve um data file no layout onedir moderno do PyInstaller."""

    return root / PYINSTALLER_CONTENTS_DIR / filename


def validate_distribution(root: Path, *, version: str) -> list[str]:
    name = f"NabiCode_v{version.replace('.', '_')}"
    errors: list[str] = []
    exe = root / f"{name}.exe"
    if not exe.is_file():
        errors.append(f"Executável ausente: {exe.name}")
    version_file = distribution_resource(root, "VERSAO.txt")
    if not version_file.is_file() or version_file.read_text(encoding="utf-8-sig").strip() != version:
        errors.append("_internal/VERSAO.txt ausente ou divergente na distribuição.")
    profile = distribution_resource(root, "PERFIL_NABICODE.txt")
    if not profile.is_file() or profile.read_text(encoding="utf-8-sig").strip() != "PRODUCAO":
        errors.append("_internal/PERFIL_NABICODE.txt ausente ou não PRODUCAO.")
    revision_file = distribution_resource(root, "REVISAO.txt")
    try:
        int(revision_file.read_text(encoding="utf-8-sig").strip())
    except (OSError, UnicodeError, TypeError, ValueError):
        errors.append("_internal/REVISAO.txt ausente ou inválido na distribuição.")
    findings = forbidden_distribution_files(root)
    if findings:
        errors.append("Arquivos proibidos: " + ", ".join(findings))
    return errors


def build_manifest(root: Path, *, version: str) -> dict[str, object]:
    files = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix().casefold()):
        files.append({
            "path": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return {
        "product": "NabiCode",
        "version": version,
        "distribution": "onedir",
        "target": "Windows x64",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "files": files,
    }


def onedir_evidence_paths(evidence_root: Path = BUILD_ROOT) -> tuple[Path, Path]:
    """Localização canônica das evidências externas ao runtime onedir."""

    return evidence_root / "manifest.json", evidence_root / "SHA256SUMS.txt"


def write_manifest(
    manifest: dict[str, object], *, evidence_root: Path = BUILD_ROOT
) -> tuple[Path, Path]:
    evidence_root.mkdir(parents=True, exist_ok=True)
    manifest_path, hashes_path = onedir_evidence_paths(evidence_root)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"{item['sha256']}  {item['path']}" for item in manifest["files"]]  # type: ignore[index]
    hashes_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path, hashes_path


def validate_onedir_evidence(
    distribution: Path, *, version: str, evidence_root: Path = BUILD_ROOT
) -> list[str]:
    manifest_path, hashes_path = onedir_evidence_paths(evidence_root)
    errors: list[str] = []
    if not manifest_path.is_file():
        errors.append(f"Evidência do onedir ausente: {manifest_path.name}")
    if not hashes_path.is_file():
        errors.append(f"Evidência do onedir ausente: {hashes_path.name}")
    if errors:
        return errors

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        items = manifest["files"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        return ["manifest.json do onedir é inválido."]
    if manifest.get("product") != "NabiCode" or manifest.get("version") != version:
        errors.append("Produto ou versão divergente no manifest.json do onedir.")
    if manifest.get("distribution") != "onedir" or not isinstance(items, list):
        errors.append("Tipo de distribuição ou lista de arquivos inválida no manifest.json.")
        return errors
    if any(not isinstance(item, dict) for item in items):
        return errors + ["Entrada inválida no manifest.json do onedir."]

    expected = build_manifest(distribution, version=version)["files"]
    expected_by_path = {item["path"]: item for item in expected}  # type: ignore[index]
    try:
        actual_by_path = {item["path"]: item for item in items}
    except (KeyError, TypeError):
        return errors + ["Entrada inválida no manifest.json do onedir."]
    if len(actual_by_path) != len(items) or set(actual_by_path) != set(expected_by_path):
        errors.append("Inventário do manifest.json diverge do conteúdo atual do onedir.")
    else:
        for path, expected_item in expected_by_path.items():
            actual_item = actual_by_path[path]
            if actual_item.get("size") != expected_item["size"] or actual_item.get("sha256") != expected_item["sha256"]:
                errors.append(f"Tamanho ou SHA-256 divergente no manifest.json: {path}")

    expected_hash_lines = [
        f"{item['sha256']}  {item['path']}" for item in items
        if isinstance(item, dict) and "sha256" in item and "path" in item
    ]
    try:
        actual_hash_lines = hashes_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        actual_hash_lines = []
    if actual_hash_lines != expected_hash_lines:
        errors.append("SHA256SUMS.txt diverge do manifest.json do onedir.")
    return errors


def run(command: Iterable[str], *, cwd: Path = PROJECT_ROOT) -> None:
    completed = subprocess.run(tuple(command), cwd=cwd, check=False)
    if completed.returncode:
        raise RuntimeError(f"Comando falhou ({completed.returncode}): {' '.join(command)}")


def validate_packaged_startup_trace(path: Path) -> list[str]:
    if not path.is_file():
        return ["Trace de startup do executável empacotado ausente."]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        events = payload["events"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        return ["Trace de startup do executável empacotado inválido."]
    profile_events = [event for event in events if event.get("name") == "packaged_profile_resolved"]
    if not profile_events or profile_events[-1].get("details", {}).get("profile") != "PRODUCAO":
        return ["Smoke empacotado não resolveu o marcador físico como PRODUCAO."]
    if profile_events[-1].get("details", {}).get("marker") != "PERFIL_NABICODE.txt":
        return ["Smoke empacotado não identificou o marcador de perfil esperado."]
    engine_events = [event for event in events if event.get("name") == "canonical_splash_engine_ready"]
    if not engine_events:
        return ["Smoke empacotado não carregou o motor canônico da splash."]
    engine = engine_events[-1].get("details", {})
    if (
        engine.get("backend") != "pygame-ce"
        or engine.get("logical_size") != [1280, 720]
        or engine.get("star_count") != 2050
        or engine.get("name_star_count") != 1500
    ):
        return ["Smoke empacotado encontrou motor visual divergente do protótipo."]
    if not any(event.get("name") == "startup_smoke_complete" for event in events):
        return ["Smoke empacotado não chegou à conclusão esperada."]
    forbidden_runtime_events = {
        "runtime_profile_ready",
        "database_path_ready",
        "database_lock_acquired",
        "splash_started",
        "legacy_import_started",
        "main_window_created",
        "mainloop_entered",
    }
    unexpected = sorted(
        {event.get("name") for event in events} & forbidden_runtime_events
    )
    if unexpected:
        return [
            "Smoke empacotado inicializou componentes proibidos do runtime: "
            + ", ".join(unexpected)
            + "."
        ]
    return []


def build_windows() -> Path:
    errors = validate_source() + validate_build_environment()
    if errors:
        raise RuntimeError("\n".join(errors))
    clean_output()
    tcl_tk_environment = prepare_tcl_tk_build_environment()
    version = read_version()
    distribution_name_value = distribution_name()
    dist_root = BUILD_ROOT / "dist"
    work_root = BUILD_ROOT / "work"
    previous_environment = {name: os.environ.get(name) for name in tcl_tk_environment}
    os.environ.update(tcl_tk_environment)
    try:
        run((
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(dist_root),
            "--workpath",
            str(work_root),
            str(SPEC_FILE),
        ))
    finally:
        for environment_name, previous in previous_environment.items():
            if previous is None:
                os.environ.pop(environment_name, None)
            else:
                os.environ[environment_name] = previous
    distribution = dist_root / distribution_name_value
    dist_errors = validate_distribution(distribution, version=version)
    if dist_errors:
        raise RuntimeError("\n".join(dist_errors))
    smoke_output = BUILD_ROOT / "smoke_version.txt"
    startup_trace = BUILD_ROOT / "startup_packaged.json"
    environment = dict(os.environ, NABICODE_STARTUP_TRACE=str(startup_trace))
    completed = subprocess.run(
        (str(distribution / f"{distribution_name_value}.exe"), "--startup-smoke-test", "--smoke-output", str(smoke_output)),
        cwd=distribution,
        env=environment,
        timeout=60,
        check=False,
    )
    smoke_errors: list[str] = []
    if completed.returncode:
        smoke_errors.append(f"Executável retornou código {completed.returncode}.")
    if not smoke_output.is_file() or smoke_output.read_text(encoding="utf-8").strip() != version:
        smoke_errors.append("Versão do smoke empacotado ausente ou divergente.")
    smoke_errors.extend(validate_packaged_startup_trace(startup_trace))
    if smoke_errors:
        raise RuntimeError("Smoke do executável empacotado falhou: " + " ".join(smoke_errors))
    manifest = build_manifest(distribution, version=version)
    write_manifest(manifest, evidence_root=BUILD_ROOT)
    evidence_errors = validate_onedir_evidence(
        distribution, version=version, evidence_root=BUILD_ROOT
    )
    if evidence_errors:
        raise RuntimeError("Validação das evidências onedir falhou: " + " ".join(evidence_errors))
    return distribution


def find_iscc() -> Path | None:
    located = shutil.which("ISCC.exe") or shutil.which("ISCC")
    if located:
        return Path(located)
    roots = [
        os.environ.get("INNO_SETUP_HOME"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("ProgramFiles"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs") if os.environ.get("LOCALAPPDATA") else None,
    ]
    candidates = [Path(item) / "Inno Setup 6" / "ISCC.exe" for item in roots if item]
    if platform.system() == "Windows":
        try:
            import winreg

            registry_keys = (
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
            )
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for key_name in registry_keys:
                    try:
                        with winreg.OpenKey(hive, key_name) as key:
                            install_location, _ = winreg.QueryValueEx(key, "InstallLocation")
                    except OSError:
                        continue
                    candidates.append(Path(install_location) / "ISCC.exe")
        except ImportError:
            pass
    return next((path for path in candidates if path.is_file()), None)


def validate_installer(
    setup: Path,
    *,
    distribution: Path,
    version: str,
    evidence_root: Path = BUILD_ROOT,
) -> list[str]:
    expected_name = f"NabiCode_{version}_Setup_Offline.exe"
    errors = validate_distribution(distribution, version=version)
    if setup.name != expected_name:
        errors.append(f"Nome do instalador divergente: {setup.name}")
    if not setup.is_file() or setup.stat().st_size <= 0:
        errors.append("Instalador offline ausente ou vazio.")
    else:
        with setup.open("rb") as stream:
            if stream.read(2) != b"MZ":
                errors.append("Instalador não possui cabeçalho executável Windows válido.")
    errors.extend(
        validate_onedir_evidence(
            distribution, version=version, evidence_root=evidence_root
        )
    )
    return errors


def build_installer() -> Path:
    version = read_version()
    distribution = BUILD_ROOT / "dist" / distribution_name()
    errors = (
        validate_distribution(distribution, version=version)
        if distribution.is_dir()
        else ["Distribuição onedir ausente."]
    )
    if not errors:
        errors.extend(
            validate_onedir_evidence(
                distribution, version=version, evidence_root=BUILD_ROOT
            )
        )
    if errors:
        distribution = build_windows()
    pre_inno_errors = validate_distribution(distribution, version=version)
    pre_inno_errors.extend(
        validate_onedir_evidence(
            distribution, version=version, evidence_root=BUILD_ROOT
        )
    )
    if pre_inno_errors:
        raise RuntimeError(
            "Distribuição ou evidências reprovadas antes do Inno Setup: "
            + " ".join(pre_inno_errors)
        )
    compiler = find_iscc()
    if compiler is None:
        raise RuntimeError("ISCC.exe (Inno Setup 6) não encontrado na máquina de build.")
    inno_command = [str(compiler), f"/DAppVersion={version}"]
    optional_icon = PROJECT_ROOT / "build_tools" / "resources" / "NabiCode.ico"
    if optional_icon.is_file():
        inno_command.append(f"/DAppIconFile={optional_icon}")
    inno_command.append(str(INNO_SCRIPT))
    run(tuple(inno_command))
    setup = BUILD_ROOT / "installer" / f"NabiCode_{version}_Setup_Offline.exe"
    installer_errors = validate_installer(
        setup,
        distribution=distribution,
        version=version,
        evidence_root=BUILD_ROOT,
    )
    if installer_errors:
        raise RuntimeError("Validação do instalador falhou: " + " ".join(installer_errors))
    (setup.parent / "SHA256SUMS.txt").write_text(
        f"{sha256_file(setup)}  {setup.name}\n", encoding="ascii"
    )
    return setup


def build_update(*, minimum_source: str, revision: int) -> Path:
    from controllers.release_package_controller import ReleasePackageController

    build_windows()
    return ReleasePackageController(PROJECT_ROOT, read_version()).create(
        minimum_source=minimum_source,
        revision=revision,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("audit", "build", "installer", "update"), nargs="?", default="audit")
    parser.add_argument("--minimum-source", default=read_version())
    parser.add_argument("--revision", type=int, default=0)
    args = parser.parse_args()
    errors = validate_source()
    if args.action in {"build", "installer", "update"}:
        try:
            if args.action == "build":
                result = build_windows()
            elif args.action == "installer":
                result = build_installer()
            else:
                if args.revision <= 0:
                    raise ValueError("Informe --revision maior que zero para o pacote incremental.")
                result = build_update(
                    minimum_source=args.minimum_source,
                    revision=args.revision,
                )
        except Exception as exc:
            print(f"BUILD_REPROVADO: {exc}", file=sys.stderr)
            return 2
        print(result)
        return 0
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "version": read_version(), "distribution": distribution_name()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
