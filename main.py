"""Ponto de entrada do NabiCode."""

from __future__ import annotations

import os
import logging
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from core.startup_metrics import mark_startup


mark_startup("process_imports_ready")


INSTALLER_APP_MUTEX = "NabiCodeApplicationMutex"


def _acquire_installer_app_mutex():
    """Expõe ao instalador que esta instância real ainda está em execução.

    O mutex não substitui o DatabaseUsageLock e não decide single-instance. Ele
    existe somente para o Inno Setup impedir atualização/desinstalação enquanto
    o processo ainda pode estar usando binários da instalação.
    """

    if os.name != "nt":
        return None
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, INSTALLER_APP_MUTEX)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def _release_installer_app_mutex(handle) -> None:
    if not handle or os.name != "nt":
        return
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_bool
    kernel32.CloseHandle(handle)


def _run_update_helper() -> int | None:
    if "--apply-update" not in sys.argv:
        return None
    from services.update_package_service import apply_prepared_update

    try:
        state_index = sys.argv.index("--state") + 1
        pid_index = sys.argv.index("--pid") + 1
        state_file = sys.argv[state_index]
        pid = int(sys.argv[pid_index])
    except (ValueError, IndexError) as exc:
        raise SystemExit(f"Argumentos inválidos do atualizador: {exc}")

    launcher = str(Path(sys.executable).resolve())
    source_main = None if getattr(sys, "frozen", False) else str(Path(__file__).resolve())
    process_started_at = None
    if "--process-started-at" in sys.argv:
        try:
            process_start_index = sys.argv.index("--process-started-at") + 1
            process_started_at = float(sys.argv[process_start_index])
        except (ValueError, IndexError) as exc:
            raise SystemExit(f"Argumentos inválidos do atualizador: {exc}") from exc
    return apply_prepared_update(
        state_file,
        pid=pid,
        launcher=launcher,
        source_main=source_main,
        process_started_at=process_started_at,
    )


def _run_splash_helper() -> bool:
    if "--splash-helper" not in sys.argv:
        return False
    try:
        stop_index = sys.argv.index("--stop-file") + 1
        pause_index = sys.argv.index("--pause-file") + 1
        parent_index = sys.argv.index("--parent-pid") + 1
        metadata_index = sys.argv.index("--metadata-file") + 1
        error_index = sys.argv.index("--error-file") + 1
        stop_file = sys.argv[stop_index]
        pause_file = sys.argv[pause_index]
        parent_pid = int(sys.argv[parent_index])
        metadata_file = sys.argv[metadata_index]
        error_file = sys.argv[error_index]
    except (ValueError, IndexError) as exc:
        raise SystemExit(f"Argumentos inválidos da tela de abertura: {exc}")
    from splash_screen import run_splash

    run_splash(stop_file, pause_file, parent_pid, metadata_file, error_file)
    return True


def _start_splash() -> tuple[subprocess.Popen | None, Path, Path, Path, Path]:
    token = f"nabicode_splash_{os.getpid()}_{os.urandom(4).hex()}.stop"
    stop_file = Path(tempfile.gettempdir()) / token
    pause_file = stop_file.with_suffix(".pause")
    metadata_file = stop_file.with_suffix(".metadata.json")
    error_file = stop_file.with_suffix(".error.log")
    try:
        for path in (stop_file, pause_file, metadata_file, error_file):
            path.unlink(missing_ok=True)
    except OSError:
        pass

    from core.startup_window_coordinator import SPLASH_PAUSE_ENV

    os.environ[SPLASH_PAUSE_ENV] = str(pause_file)

    if getattr(sys, "frozen", False):
        command = [
            str(Path(sys.executable).resolve()),
            "--splash-helper",
            "--stop-file",
            str(stop_file),
            "--pause-file",
            str(pause_file),
            "--parent-pid",
            str(os.getpid()),
            "--metadata-file",
            str(metadata_file),
            "--error-file",
            str(error_file),
        ]
        cwd = str(Path(sys.executable).resolve().parent)
    else:
        command = [
            str(Path(sys.executable).resolve()),
            str(Path(__file__).resolve().with_name("splash_screen.py")),
            "--stop-file",
            str(stop_file),
            "--pause-file",
            str(pause_file),
            "--parent-pid",
            str(os.getpid()),
            "--metadata-file",
            str(metadata_file),
            "--error-file",
            str(error_file),
        ]
        cwd = str(Path(__file__).resolve().parent)

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        process = subprocess.Popen(command, cwd=cwd, creationflags=creationflags)
    except OSError:
        process = None
    return process, stop_file, pause_file, metadata_file, error_file


def _stop_splash(stop_file: Path) -> None:
    try:
        stop_file.touch(exist_ok=True)
    except OSError:
        pass


def _pause_splash(pause_file: Path) -> None:
    try:
        pause_file.touch(exist_ok=True)
    except OSError:
        pass


def _write_splash_metadata(metadata_file: Path) -> None:
    payload = {"schema": 1}
    temporary = metadata_file.with_suffix(metadata_file.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, metadata_file)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _read_splash_metrics(metadata_file: Path) -> dict | None:
    """Lê telemetria visual local sem transformar o arquivo em dado do cliente."""

    try:
        payload = json.loads(metadata_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema") not in {2, 3}:
        return None
    if payload.get("schema") == 3 and payload.get("engine") != "pygame-ce-canonical":
        return None
    if not isinstance(payload.get("measured_fps"), (int, float)):
        return None
    return payload


def _cleanup_splash_files(*paths: Path) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _ensure_process_stopped(process: subprocess.Popen | None, timeout: float = 2.0) -> bool:
    """Aguarda o helper e força encerramento somente se ele não responder."""
    if process is None or process.poll() is not None:
        return True
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                return False
    return process.poll() is not None


def _show_startup_message(title: str, message: str, *, warning: bool = False) -> None:
    """Exibe uma mensagem própria à frente, sem manter uma raiz Tk órfã."""

    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        root.update_idletasks()
        if warning:
            messagebox.showwarning(title, message, parent=root)
        else:
            messagebox.showerror(title, message, parent=root)
    finally:
        try:
            root.attributes("-topmost", False)
        except tk.TclError:
            pass
        root.destroy()


def _instance_conflict_message(profile: str) -> str:
    label = "PRODUÇÃO" if profile == "PRODUCAO" else "TESTE"
    return (
        "NabiCode já está aberto.\n\n"
        f"O banco de {label} está sendo utilizado por outra instância.\n\n"
        "Verifique se existe uma janela do NabiCode aberta, minimizada "
        "ou aguardando confirmação."
    )


def _startup_logger(runtime_profile) -> logging.Logger:
    from core.diagnostic_logging import configure_diagnostic_logging

    logger = logging.getLogger("nabicode.startup")
    if not logger.handlers:
        configure_diagnostic_logging(
            logger,
            runtime_profile.paths.logs / "startup.log",
            app_version="2.5.1",
            runtime_profile=runtime_profile.profile,
        )
    return logger


def _log_window_state(logger, event: str, *, window=None, splash_process=None) -> None:
    details = {"splash_alive": bool(splash_process is not None and splash_process.poll() is None)}
    if window is not None:
        try:
            details.update(state=window.state(), viewable=bool(window.winfo_viewable()), geometry=window.geometry(), alpha=window.attributes("-alpha"), toplevels=len(window.winfo_children()))
        except Exception:
            logger.exception("Falha ao coletar estado visual em %s", event)
    logger.info("%s %s", event, " ".join(f"{key}={value}" for key, value in details.items()))


def _run_startup_smoke_test() -> int | None:
    if "--startup-smoke-test" not in sys.argv:
        return None

    from core.app_version import load_app_version
    from core.runtime_profile import resolve_profile_marker

    # Importa o backend visual sem inicializar SDL ou criar janela. Assim o
    # smoke empacotado prova que pygame/SDL e o motor canônico estão presentes.
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame
    import splash_deep_trust_engine as canonical_splash

    mark_startup(
        "canonical_splash_engine_ready",
        backend="pygame-ce",
        pygame_version=pygame.version.ver,
        logical_size=[canonical_splash.W, canonical_splash.H],
        star_count=canonical_splash.STAR_COUNT,
        name_star_count=canonical_splash.NAME_STAR_COUNT,
    )

    # Evidência real e somente leitura do marcador presente no runtime. No
    # onedir PyInstaller, sys._MEIPASS aponta para ``_internal``.
    packaged_profile, _profile_marker = resolve_profile_marker(
        getattr(sys, "_MEIPASS", None)
    )
    mark_startup(
        "packaged_profile_resolved",
        profile=packaged_profile,
        marker="PERFIL_NABICODE.txt",
    )

    fallback = "2.4.79"
    version = load_app_version(
        fallback,
        source_file=__file__,
        executable=sys.executable,
        runtime_dir=getattr(sys, "_MEIPASS", None),
    )
    try:
        output_index = sys.argv.index("--smoke-output") + 1
        output_file = Path(sys.argv[output_index])
    except (ValueError, IndexError):
        output_file = None

    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(version + "\n", encoding="utf-8")
    return 0


def main() -> int:
    mark_startup("main_entered")

    # O smoke do artefato valida exclusivamente bootloader/imports/versão e não
    # deve criar perfil, logs ou qualquer dado mutável do cliente.
    smoke_result = _run_startup_smoke_test()
    if smoke_result is not None:
        mark_startup("startup_smoke_complete")
        return smoke_result

    # O processo auxiliar da splash também não inicializa perfil, banco ou log
    # do aplicativo; ele recebe apenas arquivos-sinal e o PID do processo pai.
    if _run_splash_helper():
        return 0

    from core.runtime_profile import (
        DatabaseInUseError,
        DatabaseUsageLock,
        configure_profile_environment,
    )
    from core.startup_window_coordinator import SPLASH_PAUSE_ENV

    mark_startup("runtime_profile_imported")

    runtime_profile = configure_profile_environment("TESTE")
    from licensing.gate import Capability
    from licensing.runtime import evaluate_runtime_gate, startup_block_message

    license_gate = evaluate_runtime_gate(runtime_profile.app_dir)
    if not license_gate.allows(Capability.LEGACY):
        _show_startup_message(
            "Licença NabiCode V2",
            startup_block_message(license_gate, Capability.LEGACY),
            warning=True,
        )
        return 3
    startup_logger = _startup_logger(runtime_profile)
    startup_logger.info("START_APP")
    startup_logger.info("APP_START")
    mark_startup("runtime_profile_ready", profile=runtime_profile.profile)
    database_lock = None
    installer_app_mutex = None

    helper_result = _run_update_helper()
    if helper_result is not None:
        raise SystemExit(helper_result)
    try:
        installer_app_mutex = _acquire_installer_app_mutex()
    except OSError as exc:
        startup_logger.exception("Não foi possível registrar o processo para o instalador")
        _show_startup_message(
            "Não foi possível iniciar o NabiCode",
            "O Windows não permitiu registrar o processo do NabiCode para uma "
            "atualização ou desinstalação segura.\n\n"
            f"Resumo: {exc}",
        )
        return 1
    splash_process, stop_file, pause_file, metadata_file, splash_error_file = _start_splash()
    splash_completed = False
    legacy_module = None
    mark_startup("splash_started", running=splash_process is not None)
    startup_logger.info("SPLASH_START")
    _log_window_state(startup_logger, "SPLASH_CREATED", splash_process=splash_process)
    _log_window_state(startup_logger, "SPLASH_VISIBLE", splash_process=splash_process)
    try:
        mark_startup("legacy_import_started")
        import nabicode_legacy as legacy

        legacy_module = legacy
        mark_startup("legacy_import_ready")

        database_path = runtime_profile.validate_database(legacy.DB_NAME)
        mark_startup("database_path_ready", database=str(database_path))
        database_lock = DatabaseUsageLock(database_path, runtime_profile.profile)
        database_lock.acquire()
        mark_startup("database_lock_acquired")

        app = legacy.FicharioMoveisApp()
        _log_window_state(startup_logger, "ROOT_CREATED", window=app, splash_process=splash_process)
        mark_startup("application_created")
        _write_splash_metadata(metadata_file)
        try:
            current_title = app.title()
            app.title(f"{current_title} — {runtime_profile.label}")
        except Exception:
            pass

        # A animação existe apenas no início. A janela principal fica oculta até
        # o processo da splash encerrar, evitando sobreposição ou janela fantasma.
        try:
            app.withdraw()
            _log_window_state(startup_logger, "ROOT_WITHDRAWN", window=app, splash_process=splash_process)
        except Exception:
            pass

        readiness_signaled_at = None
        def finish_splash_lifecycle() -> None:
            nonlocal splash_completed
            if splash_completed:
                return
            splash_completed = True
            startup_logger.info("SPLASH_END")
            splash_metrics = _read_splash_metrics(metadata_file)
            if splash_metrics is not None:
                startup_logger.info(
                    "Splash concluída: %.3f FPS, render médio %.3f ms, "
                    "pior render %.3f ms, %s frames, display %s.",
                    float(splash_metrics["measured_fps"]),
                    float(splash_metrics.get("average_render_ms", 0.0)),
                    float(splash_metrics.get("slowest_render_ms", 0.0)),
                    splash_metrics.get("rendered_frames", 0),
                    splash_metrics.get("display_size", []),
                )
            if splash_error_file.is_file():
                try:
                    details = splash_error_file.read_text(encoding="utf-8", errors="replace")
                    if details.strip():
                        startup_logger.error("Falha(s) recuperada(s) no helper da splash:\n%s", details)
                except OSError:
                    pass
            _cleanup_splash_files(stop_file, pause_file, metadata_file, splash_error_file)
            if os.environ.get(SPLASH_PAUSE_ENV) == str(pause_file):
                os.environ.pop(SPLASH_PAUSE_ENV, None)
        def reveal_application() -> None:
            nonlocal readiness_signaled_at
            try:
                if not app.winfo_exists():
                    _stop_splash(stop_file)
                    return
            except Exception:
                _stop_splash(stop_file)
                return

            if not getattr(app, "_main_window_ready", False):
                app.after(16, reveal_application)
                return
            if readiness_signaled_at is None:
                _log_window_state(startup_logger, "ROOT_LAYOUT_READY", window=app, splash_process=splash_process)
                try:
                    app.update_idletasks()
                except Exception:
                    pass
                readiness_signaled_at = time.monotonic()
                mark_startup("main_window_ready_signaled")
                _stop_splash(stop_file)

            splash_finished = splash_process is None or splash_process.poll() is not None
            if not splash_finished and time.monotonic() - readiness_signaled_at < 15.0:
                app.after(16, reveal_application)
                return

            if splash_process is not None and splash_process.poll() is None:
                startup_logger.error("Helper da splash excedeu 15 s após MAIN_WINDOW_READY; encerrando-o.")
                if not _ensure_process_stopped(splash_process, timeout=1.0):
                    startup_logger.critical("Helper da splash não confirmou encerramento após kill.")
            _log_window_state(startup_logger, "SPLASH_DESTROY_START", window=app, splash_process=splash_process)
            finish_splash_lifecycle()
            _log_window_state(startup_logger, "SPLASH_DESTROY_END", window=app, splash_process=splash_process)
            try:
                app.attributes("-alpha", 1.0)
                app.deiconify()
                _log_window_state(startup_logger, "ROOT_DEICONIFY", window=app, splash_process=splash_process)
                app.update_idletasks()
                app._marcar_startup_revelado()
                app.lift()
                app.focus_force()
                startup_logger.info("MAIN_READY")
                _log_window_state(startup_logger, "ROOT_VISIBLE", window=app, splash_process=splash_process)
                mark_startup("first_screen_usable")
            except Exception:
                startup_logger.exception("Falha ao revelar a janela principal pronta")

        app.after_idle(reveal_application)
        mark_startup("mainloop_entered")
        app.mainloop()
        return 0
    except DatabaseInUseError as exc:
        startup_logger.warning("Segunda instância bloqueada: %s", exc)
        _pause_splash(pause_file)
        _stop_splash(stop_file)
        _show_startup_message(
            "NabiCode já está aberto",
            _instance_conflict_message(runtime_profile.profile),
            warning=True,
        )
        return 0
    except Exception as exc:
        startup_logger.exception("Falha não tratada durante o startup")
        _pause_splash(pause_file)
        _stop_splash(stop_file)
        _show_startup_message(
            "Não foi possível iniciar o NabiCode",
            "O NabiCode encontrou um erro durante a inicialização e foi encerrado.\n\n"
            "Consulte o log de startup ou entre em contato com o suporte.\n\n"
            f"Resumo: {exc}",
        )
        return 1
    finally:
        mark_startup("shutdown_started")
        runtime_shutdown_complete = legacy_module is None
        if legacy_module is not None:
            try:
                legacy_module.shutdown_runtime_resources()
                runtime_shutdown_complete = True
            except Exception:
                startup_logger.exception("Falha ao encerrar recursos de runtime")
        if database_lock is not None and runtime_shutdown_complete:
            database_lock.release()
        elif database_lock is not None:
            startup_logger.critical(
                "Lock do banco preservado porque o worker fiscal ainda pode estar ativo."
            )
        if not splash_completed:
            _pause_splash(pause_file)
            _stop_splash(stop_file)
        if not _ensure_process_stopped(splash_process, timeout=2.0):
            startup_logger.critical("Helper da splash não confirmou encerramento no shutdown.")
        if not splash_completed:
            finish_errors = ""
            if splash_error_file.is_file():
                try:
                    finish_errors = splash_error_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass
            if finish_errors.strip():
                startup_logger.error("Falha(s) no helper da splash:\n%s", finish_errors)
            _cleanup_splash_files(stop_file, pause_file, metadata_file, splash_error_file)
            if os.environ.get(SPLASH_PAUSE_ENV) == str(pause_file):
                os.environ.pop(SPLASH_PAUSE_ENV, None)
        _release_installer_app_mutex(installer_app_mutex)


if __name__ == "__main__":
    raise SystemExit(main())
