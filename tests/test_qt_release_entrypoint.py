from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main_qt_launcher


ROOT = Path(__file__).resolve().parents[1]


def test_spec_empacota_lancador_qt_sem_apagar_legacy():
    spec = (ROOT / "build_tools" / "pyinstaller" / "nabicode.spec").read_text(
        encoding="utf-8"
    )
    assert 'project_root / "main_qt_launcher.py"' in spec
    assert 'project_root / "main.py")],' not in spec
    assert (ROOT / "main.py").is_file()


def test_lancador_preserva_atualizador_mutex_e_entrada_qt():
    source = (ROOT / "main_qt_launcher.py").read_text(encoding="utf-8")
    assert "_run_update_helper()" in source
    assert "_acquire_installer_app_mutex()" in source
    assert "_release_installer_app_mutex(installer_mutex)" in source
    assert "from main_qt import main as run_qt" in source


def test_auditoria_exige_fontes_e_runtime_qt():
    source = (ROOT / "build_tools" / "build_windows.py").read_text(encoding="utf-8")
    for required in (
        '"main_qt.py"',
        '"main_qt_launcher.py"',
        '"PySide6"',
        '"PySide6_Addons"',
        '"PySide6_Essentials"',
        '"shiboken6"',
    ):
        assert required in source


def test_lock_fixa_wheels_qt_windows_com_hashes_oficiais():
    lock = (ROOT / "build_tools" / "requirements-windows.lock").read_text(
        encoding="utf-8"
    )
    expected = {
        "pyside6==6.11.2": "3201d67e3c10be2eaedd3910ff0f02351eca7e88c95a291cde5e7f2f55ef207f",
        "pyside6-addons==6.11.2": "f449ea4431da20e7b86752cca8d166f93434516fe417f981c27e5f8e1b554407",
        "pyside6-essentials==6.11.2": "c8a29def77032773a30879f7f24415b5395ad08592d147c170824ef4c735dfc1",
        "shiboken6==6.11.2": "6ab0eba1c904455df621f9a6df3ca2bb896bab8670572d2bc4e37804ae91f19a",
    }
    for package, digest in expected.items():
        assert package in lock
        assert f"--hash=sha256:{digest}" in lock


def test_atualizador_encerra_antes_de_importar_aplicacao_qt():
    with (
        patch.object(main_qt_launcher, "_run_update_helper", return_value=7),
        patch.object(main_qt_launcher, "_acquire_installer_app_mutex") as mutex,
    ):
        assert main_qt_launcher.main() == 7
    mutex.assert_not_called()


def test_smoke_empacotado_usa_entrada_canônica_sem_atualizador_ou_mutex():
    with (
        patch.object(sys, "argv", ["NabiCode.exe", "--startup-smoke-test"]),
        patch.object(main_qt_launcher, "run_startup_entry", return_value=0) as smoke,
        patch.object(main_qt_launcher, "_run_update_helper") as updater,
        patch.object(main_qt_launcher, "_acquire_installer_app_mutex") as mutex,
    ):
        assert main_qt_launcher.main() == 0
    smoke.assert_called_once_with()
    updater.assert_not_called()
    mutex.assert_not_called()


def test_helper_da_splash_usa_entrada_canonica_sem_criar_nova_aplicacao():
    with (
        patch.object(sys, "argv", ["NabiCode.exe", "--splash-helper"]),
        patch.object(main_qt_launcher, "run_startup_entry", return_value=0) as helper,
        patch.object(main_qt_launcher, "_run_update_helper") as updater,
        patch.object(main_qt_launcher, "_acquire_installer_app_mutex") as mutex,
    ):
        assert main_qt_launcher.main() == 0
    helper.assert_called_once_with()
    updater.assert_not_called()
    mutex.assert_not_called()


def test_execucao_qt_mantem_mutex_ate_encerrar():
    run_qt = Mock(return_value=0)
    fake_module = SimpleNamespace(main=run_qt)
    with (
        patch.object(main_qt_launcher, "_run_update_helper", return_value=None),
        patch.object(
            main_qt_launcher, "_acquire_installer_app_mutex", return_value=123
        ) as acquire,
        patch.object(main_qt_launcher, "_release_installer_app_mutex") as release,
        patch.dict(sys.modules, {"main_qt": fake_module}),
    ):
        assert main_qt_launcher.main() == 0
    acquire.assert_called_once_with()
    run_qt.assert_called_once_with()
    release.assert_called_once_with(123)


def test_falha_da_aplicacao_qt_ainda_libera_mutex():
    run_qt = Mock(side_effect=RuntimeError("falha controlada"))
    with (
        patch.object(main_qt_launcher, "_run_update_helper", return_value=None),
        patch.object(
            main_qt_launcher, "_acquire_installer_app_mutex", return_value=456
        ),
        patch.object(main_qt_launcher, "_release_installer_app_mutex") as release,
        patch.dict(sys.modules, {"main_qt": SimpleNamespace(main=run_qt)}),
    ):
        try:
            main_qt_launcher.main()
        except RuntimeError as error:
            assert str(error) == "falha controlada"
        else:
            raise AssertionError("A falha da aplicação deveria ser propagada.")
    release.assert_called_once_with(456)
