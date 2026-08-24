from __future__ import annotations

import json
import os
import runpy
import sys
import tempfile
import zipfile
from pathlib import Path

from build_tools import build_windows


ROOT = Path(__file__).resolve().parents[1]


def canonical_engine_event() -> dict:
    return {"name": "canonical_splash_engine_ready", "details": {
        "backend": "pygame-ce",
        "logical_size": [1280, 720],
        "star_count": 2050,
        "name_star_count": 1500,
    }}


def test_source_audit_accepts_checkpoint_tree() -> None:
    assert build_windows.validate_source(ROOT) == []
    assert build_windows.read_version(ROOT) == "2.5.1"
    assert (ROOT / "REVISAO.txt").read_text(encoding="utf-8").strip() == "21"


def test_wheelhouse_catalog_never_hashes_its_own_output_file():
    script = (ROOT / "build_tools" / "prepare_wheelhouse.ps1").read_text(encoding="utf-8")
    assert "Get-ChildItem $Wheelhouse -Filter '*.whl' -File" in script


def test_installer_removes_only_the_known_legacy_r6_identity():
    script = (ROOT / "build_tools" / "inno" / "NabiCode_Offline.iss").read_text(encoding="utf-8")
    assert "{D8DD09BC-A699-4E77-A011-786A02A19596}_is1" in script
    assert "function PrepareToInstall" in script
    assert "RemoveLegacyR6()" in script
    assert "NabiCode TESTE R6.lnk" in script
    assert "VERYSILENT /SUPPRESSMSGBOXES /NORESTART" in script
    assert "RegDeleteKeyIncludingSubkeys(HKLM64, LegacyR6UninstallKey)" in script


def test_uninstaller_always_preserves_operational_data():
    script = (ROOT / "build_tools" / "inno" / "NabiCode_Offline.iss").read_text(encoding="utf-8")
    assert "function InitializeUninstall" in script
    assert "MB_YESNOCANCEL or MB_DEFBUTTON2" in script
    assert "if UninstallSilent then" in script
    assert "DeleteAllNabiCodeData" not in script
    assert "Dados operacionais do NabiCode preservados em AppData" in script


def test_single_setup_offers_repair_and_safe_uninstall():
    script = (ROOT / "build_tools" / "inno" / "NabiCode_Offline.iss").read_text(encoding="utf-8")
    assert "OfficialUninstallKey" in script
    assert "CreateInputOptionPage" in script
    assert "Atualizar ou reparar o NabiCode" in script
    assert "Desinstalar o programa e manter banco" in script
    assert "Desinstalar e apagar completamente" not in script
    assert "function NextButtonClick" in script
    assert "RunRegisteredUninstaller(HKLM64, OfficialUninstallKey)" in script


def test_installer_never_embeds_master_password_or_deletes_operational_data():
    script = (ROOT / "build_tools" / "inno" / "NabiCode_Offline.iss").read_text(encoding="utf-8")
    security = (ROOT / "services" / "security_service.py").read_text(encoding="utf-8")
    assert "MasterPasswordSHA256" not in script
    assert "RequestMasterPassword" not in script
    assert "MASTER_PASSWORD_SHA256" not in security
    assert "Desinstalar e apagar completamente" not in script
    assert "DeleteAllNabiCodeData" not in script
    assert "OfficialInstallLocation" in script
    assert "LegacyInstallLocation" in script


def test_installer_discovers_other_registered_nabicode_versions_without_disk_wildcards():
    script = (ROOT / "build_tools" / "inno" / "NabiCode_Offline.iss").read_text(encoding="utf-8")
    assert "procedure RemoveOtherRegisteredNabiCodeInstalls" in script
    assert "RemoveRegisteredNabiCodeInstallsAtRoot(HKLM64)" in script
    assert "RemoveRegisteredNabiCodeInstallsAtRoot(HKLM32)" in script
    assert "RemoveRegisteredNabiCodeInstallsAtRoot(HKCU)" in script
    assert "(RootKey = HKLM64) and (CompareText(RegistryKey, OfficialUninstallKey) = 0)" in script
    assert "Pos('NABICODE', Uppercase(DisplayName)) = 1" in script
    assert "CompareText(Publisher, 'NabiCode') = 0" in script
    assert "OldInstallLocations.Add(InstallLocation)" in script
    assert "{commondesktop}\\NabiCode*.lnk" in script
    assert "{userdesktop}\\NabiCode*.lnk" in script
    assert str(ROOT) in build_windows.sys.path
    assert build_windows.distribution_name(ROOT) == "NabiCode_v2_5_1"
    assert (ROOT / "PERFIL_NABICODE.txt").read_text(encoding="utf-8").strip() == "TESTE"
    assert (ROOT / "build_tools/resources/PERFIL_NABICODE.txt").read_text(encoding="utf-8").strip() == "PRODUCAO"


def test_distribution_validation_rejects_database_and_cache() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "NabiCode_v2_5_1.exe").write_bytes(b"MZ")
        internal = root / "_internal"
        internal.mkdir()
        (internal / "VERSAO.txt").write_text("2.5.1\n", encoding="utf-8")
        (internal / "PERFIL_NABICODE.txt").write_text("PRODUCAO\n", encoding="utf-8")
        (internal / "REVISAO.txt").write_text("6\n", encoding="utf-8")
        (root / "dados.db").write_bytes(b"SQLite format 3")
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "x.pyc").write_bytes(b"x")
        errors = build_windows.validate_distribution(root, version="2.5.1")
        assert any("dados.db" in error for error in errors)
        assert any("__pycache__" in error for error in errors)


def test_distribution_manifest_has_hashes_and_relative_paths() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        build_root = Path(temporary) / "build_output"
        root = build_root / "dist" / "NabiCode_v2_5_1"
        root.mkdir(parents=True)
        (root / "NabiCode_v2_5_1.exe").write_bytes(b"MZ-nabicode")
        (root / "NabiCode.ico").write_bytes(b"icon")
        internal = root / "_internal"
        internal.mkdir()
        (internal / "VERSAO.txt").write_text("2.5.1\n", encoding="utf-8")
        (internal / "PERFIL_NABICODE.txt").write_text("PRODUCAO\n", encoding="utf-8")
        (internal / "REVISAO.txt").write_text("6\n", encoding="utf-8")
        assert build_windows.validate_distribution(root, version="2.5.1") == []
        manifest = build_windows.build_manifest(root, version="2.5.1")
        assert manifest["distribution"] == "onedir"
        files = manifest["files"]
        assert files and all(len(item["sha256"]) == 64 for item in files)
        assert all(not Path(item["path"]).is_absolute() for item in files)
        manifest_path, hashes_path = build_windows.write_manifest(
            manifest, evidence_root=build_root
        )
        assert manifest_path == build_root / "manifest.json"
        assert hashes_path == build_root / "SHA256SUMS.txt"
        assert not (build_root / "dist" / "manifest.json").exists()
        assert build_windows.validate_onedir_evidence(
            root, version="2.5.1", evidence_root=build_root
        ) == []


def test_onedir_evidence_detects_distribution_tampering() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        build_root = Path(temporary) / "build_output"
        distribution = build_root / "dist" / "NabiCode_v2_5_1"
        internal = distribution / "_internal"
        internal.mkdir(parents=True)
        executable = distribution / "NabiCode_v2_5_1.exe"
        executable.write_bytes(b"MZ-original")
        (internal / "VERSAO.txt").write_text("2.5.1\n", encoding="utf-8")
        (internal / "PERFIL_NABICODE.txt").write_text("PRODUCAO\n", encoding="utf-8")
        (internal / "REVISAO.txt").write_text("6\n", encoding="utf-8")
        manifest = build_windows.build_manifest(distribution, version="2.5.1")
        build_windows.write_manifest(manifest, evidence_root=build_root)
        executable.write_bytes(b"MZ-alterado")
        errors = build_windows.validate_onedir_evidence(
            distribution, version="2.5.1", evidence_root=build_root
        )

    assert any("divergente" in error for error in errors)


def test_spec_is_onedir_production_without_upx() -> None:
    spec = (ROOT / "build_tools" / "pyinstaller" / "nabicode.spec").read_text(encoding="utf-8")
    assert "COLLECT(" in spec
    assert "exclude_binaries=True" in spec
    assert "upx=False" in spec
    assert 'resources" / "PERFIL_NABICODE.txt"' in spec
    assert 'revision_file = project_root / "REVISAO.txt"' in spec
    assert 'contents_directory="_internal"' in spec
    assert "runtime_production_profile.py" in spec
    assert '"win32print"' in spec
    assert '"PIL.ImageTk"' in spec
    assert '"pygame"' in spec
    assert '"splash_deep_trust_engine"' in spec
    assert "collect_all" not in spec
    assert '"matplotlib.tests"' in spec


def test_distribution_accepts_only_the_certifi_public_ca_bundle() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        allowed = root / "_internal" / "certifi" / "cacert.pem"
        allowed.parent.mkdir(parents=True)
        allowed.write_text("PUBLIC CA BUNDLE", encoding="ascii")
        forbidden = root / "_internal" / "other" / "cacert.pem"
        forbidden.parent.mkdir(parents=True)
        forbidden.write_text("NOT ALLOWED", encoding="ascii")
        key = root / "_internal" / "private.key"
        key.write_text("PRIVATE KEY", encoding="ascii")

        findings = build_windows.forbidden_distribution_files(root)

    assert "_internal/certifi/cacert.pem" not in findings
    assert "_internal/other/cacert.pem" in findings
    assert "_internal/private.key" in findings


def test_distribution_requires_markers_in_modern_internal_layout() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "NabiCode_v2_5_1.exe").write_bytes(b"MZ")
        (root / "VERSAO.txt").write_text("2.5.1\n", encoding="utf-8")
        (root / "PERFIL_NABICODE.txt").write_text("PRODUCAO\n", encoding="utf-8")
        errors = build_windows.validate_distribution(root, version="2.5.1")

    assert any("_internal/VERSAO.txt" in error for error in errors)
    assert any("_internal/PERFIL_NABICODE.txt" in error for error in errors)


def test_packaged_smoke_trace_requires_production_profile() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        trace = Path(temporary) / "startup.json"
        trace.write_text(json.dumps({"events": [
            canonical_engine_event(),
            {"name": "packaged_profile_resolved", "details": {
                "profile": "PRODUCAO", "marker": "PERFIL_NABICODE.txt",
            }},
            {"name": "startup_smoke_complete"},
        ]}), encoding="utf-8")
        assert build_windows.validate_packaged_startup_trace(trace) == []
        trace.write_text(json.dumps({"events": [
            {"name": "packaged_profile_resolved", "details": {
                "profile": "TESTE", "marker": "PERFIL_NABICODE.txt",
            }},
            {"name": "startup_smoke_complete"},
        ]}), encoding="utf-8")
        errors = build_windows.validate_packaged_startup_trace(trace)

    assert any("PRODUCAO" in error for error in errors)


def test_packaged_smoke_reproduces_old_impossible_contract_and_accepts_new_contract() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        trace = Path(temporary) / "startup.json"
        # Trace real do Checkpoint 35: o smoke encerra antes do runtime completo.
        trace.write_text(json.dumps({"events": [
            {"name": "process_imports_ready"},
            {"name": "main_entered"},
            {"name": "startup_smoke_complete"},
        ]}), encoding="utf-8")
        old_errors = build_windows.validate_packaged_startup_trace(trace)
        assert any("marcador físico" in error for error in old_errors)

        trace.write_text(json.dumps({"events": [
            {"name": "process_imports_ready"},
            {"name": "main_entered"},
            canonical_engine_event(),
            {"name": "packaged_profile_resolved", "details": {
                "profile": "PRODUCAO", "marker": "PERFIL_NABICODE.txt",
            }},
            {"name": "startup_smoke_complete"},
        ]}), encoding="utf-8")
        assert build_windows.validate_packaged_startup_trace(trace) == []


def test_packaged_smoke_rejects_runtime_side_effect_events() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        trace = Path(temporary) / "startup.json"
        trace.write_text(json.dumps({"events": [
            canonical_engine_event(),
            {"name": "packaged_profile_resolved", "details": {
                "profile": "PRODUCAO", "marker": "PERFIL_NABICODE.txt",
            }},
            {"name": "runtime_profile_ready", "details": {"profile": "PRODUCAO"}},
            {"name": "database_lock_acquired"},
            {"name": "startup_smoke_complete"},
        ]}), encoding="utf-8")
        errors = build_windows.validate_packaged_startup_trace(trace)

    assert any("componentes proibidos" in error for error in errors)


def test_packaged_smoke_requires_the_exact_canonical_splash_contract() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        trace = Path(temporary) / "startup.json"
        base = [
            {"name": "packaged_profile_resolved", "details": {
                "profile": "PRODUCAO", "marker": "PERFIL_NABICODE.txt",
            }},
            {"name": "startup_smoke_complete"},
        ]
        trace.write_text(json.dumps({"events": base}), encoding="utf-8")
        assert any(
            "motor canônico" in error
            for error in build_windows.validate_packaged_startup_trace(trace)
        )

        divergent = canonical_engine_event()
        divergent["details"]["star_count"] = 500
        trace.write_text(json.dumps({"events": [divergent, *base]}), encoding="utf-8")
        assert any(
            "divergente" in error
            for error in build_windows.validate_packaged_startup_trace(trace)
        )


def test_runtime_hook_forces_only_packaged_profile_to_production() -> None:
    hook = ROOT / "build_tools" / "pyinstaller" / "runtime_production_profile.py"
    with tempfile.TemporaryDirectory() as temporary:
        runtime = Path(temporary)
        (runtime / "PERFIL_NABICODE.txt").write_text("PRODUCAO\n", encoding="utf-8")
        (runtime / "VERSAO.txt").write_text("2.5.1\n", encoding="utf-8")
        sentinel = object()
        previous_meipass = getattr(sys, "_MEIPASS", sentinel)
        previous_profile = os.environ.get("NABICODE_PROFILE")
        previous_version = os.environ.get("NABICODE_VERSION_FILE")
        try:
            sys._MEIPASS = str(runtime)  # type: ignore[attr-defined]
            os.environ["NABICODE_PROFILE"] = "TESTE"
            runpy.run_path(str(hook))
            assert os.environ["NABICODE_PROFILE"] == "PRODUCAO"
            assert os.environ["NABICODE_VERSION_FILE"] == str(runtime / "VERSAO.txt")
        finally:
            if previous_meipass is sentinel:
                delattr(sys, "_MEIPASS")
            else:
                sys._MEIPASS = previous_meipass  # type: ignore[attr-defined]
            if previous_profile is None:
                os.environ.pop("NABICODE_PROFILE", None)
            else:
                os.environ["NABICODE_PROFILE"] = previous_profile
            if previous_version is None:
                os.environ.pop("NABICODE_VERSION_FILE", None)
            else:
                os.environ["NABICODE_VERSION_FILE"] = previous_version


def test_installer_validation_uses_validated_onedir_as_input() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary)
        distribution = temporary_root / "dist" / "NabiCode_v2_5_1"
        internal = distribution / "_internal"
        internal.mkdir(parents=True)
        (distribution / "NabiCode_v2_5_1.exe").write_bytes(b"MZ-app")
        (distribution / "NabiCode.ico").write_bytes(b"icon")
        (internal / "VERSAO.txt").write_text("2.5.1\n", encoding="utf-8")
        (internal / "PERFIL_NABICODE.txt").write_text("PRODUCAO\n", encoding="utf-8")
        (internal / "REVISAO.txt").write_text("6\n", encoding="utf-8")
        installer = temporary_root / "installer" / "NabiCode_2.5.1_Setup_Offline.exe"
        installer.parent.mkdir()
        installer.write_bytes(b"MZ-setup")
        manifest = build_windows.build_manifest(distribution, version="2.5.1")
        build_windows.write_manifest(manifest, evidence_root=temporary_root)
        assert build_windows.validate_installer(
            installer,
            distribution=distribution,
            version="2.5.1",
            evidence_root=temporary_root,
        ) == []


def test_windows_build_path_guard_recommends_short_root() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        # Não derive o caso curto do TEMP: em algumas instalações Windows o
        # próprio caminho temporário já ultrapassa o limite conservador.
        short = Path(r"C:\NB\NabiCode")
        long = Path(temporary) / ("projeto_muito_longo_" * 8)
        assert build_windows.validate_windows_build_path(short) == []
        errors = build_windows.validate_windows_build_path(long)

    assert any(r"C:\NB\NabiCode" in error for error in errors)


def test_cleanup_preserves_wheelhouse_and_build_venv() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        project = Path(temporary)
        build_root = project / "build_output"
        for name in ("dist", "work", "installer"):
            folder = build_root / name
            folder.mkdir(parents=True)
            (folder / "generated.txt").write_text("x", encoding="utf-8")
        wheelhouse = build_root / "wheelhouse"
        wheelhouse.mkdir()
        (wheelhouse / "SHA256SUMS.txt").write_text("preserve", encoding="ascii")
        build_venv = build_root / ".build-venv"
        build_venv.mkdir()
        (build_venv / "marker.txt").write_text("preserve", encoding="ascii")

        original_project_root = build_windows.PROJECT_ROOT
        build_windows.PROJECT_ROOT = project
        try:
            build_windows.clean_output(build_root)
        finally:
            build_windows.PROJECT_ROOT = original_project_root

        assert not (build_root / "dist").exists()
        assert not (build_root / "work").exists()
        assert not (build_root / "installer").exists()
        assert (wheelhouse / "SHA256SUMS.txt").read_text(encoding="ascii") == "preserve"
        assert (build_venv / "marker.txt").read_text(encoding="ascii") == "preserve"


def test_python_314_zipfs_tcl_tk_is_materialized_for_pyinstaller() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        python_root = root / "python"
        tcl_root = python_root / "tcl"
        tcl_root.mkdir(parents=True)
        with zipfile.ZipFile(tcl_root / "libtcl9.0.zip", "w") as bundle:
            bundle.writestr("tcl_library/init.tcl", "package provide Tcl 9.0")
        with zipfile.ZipFile(tcl_root / "libtk9.0.zip", "w") as bundle:
            bundle.writestr("tk_library/tk.tcl", "package provide Tk 9.0")

        environment = build_windows.prepare_tcl_tk_build_environment(
            python_root=python_root,
            build_root=root / "build_output",
        )

        assert Path(environment["TCL_LIBRARY"], "init.tcl").is_file()
        assert Path(environment["TK_LIBRARY"], "tk.tcl").is_file()


def test_tcl_environment_restore_does_not_shadow_distribution_name() -> None:
    source = Path(build_windows.__file__).read_text(encoding="utf-8")
    build_source = source.split("def build_windows()", 1)[1].split("def find_iscc", 1)[0]
    assert "distribution = dist_root / distribution_name_value" in build_source
    assert "for environment_name, previous in previous_environment.items()" in build_source


def test_inno_installer_is_offline_and_preserves_appdata() -> None:
    script = (ROOT / "build_tools" / "inno" / "NabiCode_Offline.iss").read_text(encoding="utf-8")
    assert "Setup_Offline" in script
    assert "PrivilegesRequired=admin" in script
    assert "{autoprograms}\\NabiCode" in script
    assert "desktopicon" in script
    assert "Dados operacionais do NabiCode preservados em AppData" in script
    assert "{ Dados em {userappdata}" not in script
    assert "OutputDir=..\\..\\build_output\\installer" in script
    assert 'Source: "..\\..\\build_output\\dist\\{#DistName}\\*"' in script
    assert "http://" not in script and "https://" not in script
    assert "pip install" not in script.casefold()


def test_offline_pipeline_validates_every_wheel_hash_and_recreates_build_venv() -> None:
    script = (ROOT / "build_tools" / "build_offline_windows.ps1").read_text(encoding="utf-8-sig")
    assert "Get-FileHash -LiteralPath $WheelPath -Algorithm SHA256" in script
    assert "Wheel sem hash registrado em SHA256SUMS.txt" in script
    assert "Caminho inseguro em wheelhouse\\SHA256SUMS.txt" in script
    assert "Remove-Item -LiteralPath $BuildVenv -Recurse -Force" in script
    assert 'Remove-Item -LiteralPath $Wheelhouse' not in script
    assert script.index("Get-FileHash") < script.index("python -m venv $BuildVenv")
