"""Adaptador de produto para o splash canônico Deep Trust Fluid.

O desenho e a timeline vivem em ``splash_deep_trust_engine.py``, cópia
byte-a-byte do protótipo aprovado. Este módulo acrescenta somente o contrato
operacional do helper: processo pai, pausa para modais, readiness, métricas e
cleanup. O Pygame continua restrito ao processo auxiliar.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from pathlib import Path
from types import ModuleType


BRAND = "NABICODE"
LOGICAL_WIDTH = 1280
LOGICAL_HEIGHT = 720
FPS = 60
FRAME_MS = 16
DURATION = 12.2
READY_HOLD_AT = 11.0
STAR_COUNT = 2050
NAME_STAR_COUNT = 1500
RARE_STAR_COUNT = 8
# O protótipo original converge as estrelas do nome para branco puro.
NAME_IVORY = (255, 255, 255)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def smooth(value: float) -> float:
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


def _load_canonical_engine() -> ModuleType:
    # Import tardio: importar ``main`` ou executar o smoke não inicializa SDL.
    import splash_deep_trust_engine

    return splash_deep_trust_engine


def _enable_windows_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        return


class LightspeedSplash:
    """Executa o protótipo exato com sinais externos de ciclo de vida."""

    def __init__(
        self,
        stop_file: Path,
        pause_file: Path,
        parent_pid: int | None = None,
        metadata_file: Path | None = None,
        error_file: Path | None = None,
    ) -> None:
        self.stop_file = stop_file
        self.pause_file = pause_file
        self.parent_pid = parent_pid
        self.metadata_file = metadata_file
        self.error_file = error_file
        self.engine = _load_canonical_engine()
        self.pygame = self.engine.pygame

        _enable_windows_dpi_awareness()
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        self.pygame.init()
        self.pygame.display.set_caption("NabiCode — Deep Trust Fluid")
        # NOFRAME altera somente a moldura da janela, não o framebuffer canônico.
        self.screen = self.pygame.display.set_mode(
            (self.engine.W, self.engine.H), self.pygame.NOFRAME
        )
        self.clock = self.pygame.time.Clock()
        self.display_width = self.engine.W
        self.display_height = self.engine.H

        # Ordem idêntica à criação de objetos no main do protótipo.
        self.warp_stars = [self.engine.WarpStar() for _ in range(self.engine.STAR_COUNT)]
        self.rare_stars = [self.engine.RareStar() for _ in range(RARE_STAR_COUNT)]
        points = self.engine.build_text_points(BRAND, 96, 3)
        self.name_stars = [self.engine.NameStar(point) for point in points]

        self.started_at = time.perf_counter()
        self.ready_received_at: float | None = None
        self.ready_active_elapsed: float | None = None
        self.pause_started_at: float | None = None
        self.hidden_for_modal = False
        self.closed = False
        self.rendered_frames = 0
        self.first_render_at: float | None = None
        self.last_render_completed_at: float | None = None
        self.total_render_seconds = 0.0
        self.slowest_render_seconds = 0.0
        self._next_parent_check = self.started_at
        self._set_window_visible(True)

    @staticmethod
    def timeline(elapsed: float) -> tuple[float, float, float, float]:
        # Transcrição literal das expressões do protótipo aprovado.
        fade_in = smooth(elapsed / 1.0)
        fade_out = 1.0 - smooth((elapsed - 11.0) / 1.2)
        fade = fade_in * fade_out
        acceleration = smooth((elapsed - 2.0) / 3.6)
        deceleration = smooth((elapsed - 6.35) / 2.35)
        warp = clamp(acceleration * (1.0 - deceleration * 0.88))
        name_cleanup = smooth((elapsed - 4.55) / 1.45)
        warp *= 1.0 - 0.46 * name_cleanup
        speed = 40.0 + 540.0 * warp ** 2.60
        name_progress = smooth((elapsed - 4.70) / 2.85)
        return fade, warp, speed, name_progress

    def _active_elapsed(self, now: float) -> float:
        return max(0.0, now - self.started_at)

    def _visual_elapsed(self, now: float) -> float:
        active = self._active_elapsed(now)
        if self.ready_received_at is None:
            return min(active, READY_HOLD_AT)
        if (self.ready_active_elapsed or 0.0) < READY_HOLD_AT:
            return min(active, DURATION)
        return min(DURATION, READY_HOLD_AT + (now - self.ready_received_at))

    def _window_handle(self) -> int | None:
        try:
            value = self.pygame.display.get_wm_info().get("window")
            return int(value) if value else None
        except Exception:
            return None

    def _set_window_visible(self, visible: bool) -> None:
        handle = self._window_handle()
        if os.name == "nt" and handle:
            try:
                import ctypes

                user32 = ctypes.windll.user32
                if visible:
                    user32.ShowWindow(handle, 5)  # SW_SHOW
                    user32.SetWindowPos(
                        handle, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040
                    )  # HWND_TOPMOST + NOSIZE + NOMOVE + SHOWWINDOW
                else:
                    user32.SetWindowPos(
                        handle, -2, 0, 0, 0, 0, 0x0001 | 0x0002
                    )  # HWND_NOTOPMOST
                    user32.ShowWindow(handle, 0)  # SW_HIDE
                return
            except Exception:
                pass
        if not visible:
            try:
                self.pygame.display.iconify()
            except Exception:
                pass

    def _record_error(self) -> None:
        if self.error_file is None:
            return
        try:
            self.error_file.parent.mkdir(parents=True, exist_ok=True)
            with self.error_file.open("a", encoding="utf-8") as stream:
                stream.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n")
                stream.write(traceback.format_exc())
                stream.write("\n")
        except OSError:
            pass

    def _parent_is_alive(self) -> bool:
        if not self.parent_pid or self.parent_pid <= 0:
            return True
        if os.name == "nt":
            try:
                import ctypes
                from ctypes import wintypes

                handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, self.parent_pid)
                if not handle:
                    return False
                exit_code = wintypes.DWORD()
                try:
                    if not ctypes.windll.kernel32.GetExitCodeProcess(
                        handle, ctypes.byref(exit_code)
                    ):
                        return True
                    return exit_code.value == 259
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                return True
        try:
            os.kill(self.parent_pid, 0)
        except (ProcessLookupError, OSError):
            return False
        return True

    def _handle_controls(self, now: float) -> None:
        paused = self.pause_file.exists()
        if paused and not self.hidden_for_modal:
            self.hidden_for_modal = True
            self.pause_started_at = now
            self._set_window_visible(False)
        elif not paused and self.hidden_for_modal:
            if self.pause_started_at is not None:
                self.started_at += now - self.pause_started_at
            self.pause_started_at = None
            self.hidden_for_modal = False
            self._set_window_visible(True)

        if self.stop_file.exists() and self.ready_received_at is None:
            if self.hidden_for_modal:
                # stop+pause representa abort/erro; não se aguarda transição.
                self.closed = True
                return
            self.ready_received_at = now
            self.ready_active_elapsed = self._active_elapsed(now)

        if now >= self._next_parent_check:
            self._next_parent_check = now + 1.0
            if not self._parent_is_alive():
                self.closed = True

    def _draw_canonical_frame(self, elapsed: float, dt: float, now: float) -> None:
        fade, warp, speed, name_progress = self.timeline(elapsed)
        self.screen.fill(self.engine.SPACE)
        for star in self.warp_stars:
            star.update_draw(self.screen, dt, now, speed, warp, fade)
        for rare_star in self.rare_stars:
            rare_star.draw(self.screen, now, fade, warp)
        if elapsed > 4.45:
            for name_star in self.name_stars:
                name_star.draw(self.screen, name_progress, now, fade)
        self.engine.draw_vignette(self.screen)
        if fade < 0.999:
            mask = self.pygame.Surface((self.engine.W, self.engine.H))
            mask.fill((0, 0, 0))
            mask.set_alpha(int(255 * (1.0 - fade)))
            self.screen.blit(mask, (0, 0))
        self.pygame.display.flip()

    def _write_metrics(self) -> None:
        if self.metadata_file is None:
            return
        elapsed = 0.0
        if self.first_render_at is not None and self.last_render_completed_at is not None:
            elapsed = max(0.0, self.last_render_completed_at - self.first_render_at)
        measured_fps = (self.rendered_frames - 1) / elapsed if elapsed > 0.0 else 0.0
        average_render_ms = (
            self.total_render_seconds * 1000.0 / self.rendered_frames
            if self.rendered_frames
            else 0.0
        )
        payload = {
            "schema": 3,
            "engine": "pygame-ce-canonical",
            "logical_size": [self.engine.W, self.engine.H],
            "display_size": [self.display_width, self.display_height],
            "rendered_frames": self.rendered_frames,
            "measured_fps": round(measured_fps, 3),
            "average_render_ms": round(average_render_ms, 3),
            "slowest_render_ms": round(self.slowest_render_seconds * 1000.0, 3),
        }
        temporary = self.metadata_file.with_suffix(self.metadata_file.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(temporary, self.metadata_file)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def run(self) -> None:
        try:
            while not self.closed:
                dt = self.clock.tick(self.engine.FPS) / 1000.0
                now = time.perf_counter()
                for event in self.pygame.event.get():
                    if event.type == self.pygame.QUIT:
                        self.closed = True
                    elif event.type == self.pygame.KEYDOWN and event.key == self.pygame.K_ESCAPE:
                        self.closed = True
                self._handle_controls(now)
                if self.closed:
                    break
                if self.hidden_for_modal:
                    continue

                visual_elapsed = self._visual_elapsed(now)
                render_started_at = time.perf_counter()
                self._draw_canonical_frame(visual_elapsed, dt, self._active_elapsed(now))
                render_completed_at = time.perf_counter()
                if self.first_render_at is None:
                    self.first_render_at = render_completed_at
                self.last_render_completed_at = render_completed_at
                render_seconds = render_completed_at - render_started_at
                self.total_render_seconds += render_seconds
                self.slowest_render_seconds = max(self.slowest_render_seconds, render_seconds)
                self.rendered_frames += 1
                if self.ready_received_at is not None and visual_elapsed >= DURATION:
                    self.closed = True
        except Exception:
            self._record_error()
        finally:
            self._set_window_visible(False)
            self._write_metrics()
            self.pygame.quit()


def run_splash(
    stop_file: str | os.PathLike[str],
    pause_file: str | os.PathLike[str],
    parent_pid: int | None = None,
    metadata_file: str | os.PathLike[str] | None = None,
    error_file: str | os.PathLike[str] | None = None,
) -> None:
    LightspeedSplash(
        Path(stop_file),
        Path(pause_file),
        parent_pid,
        Path(metadata_file) if metadata_file else None,
        Path(error_file) if error_file else None,
    ).run()


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--stop-file", required=True)
    parser.add_argument("--pause-file", required=True)
    parser.add_argument("--parent-pid", type=int, default=None)
    parser.add_argument("--metadata-file")
    parser.add_argument("--error-file")
    args = parser.parse_args()
    run_splash(
        args.stop_file,
        args.pause_file,
        args.parent_pid,
        args.metadata_file,
        args.error_file,
    )


if __name__ == "__main__":
    main()
