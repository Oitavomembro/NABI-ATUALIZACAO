"""Gerenciamento centralizado da marca d'água visual do NabiCode.

Não contém regras de negócio. A renderização é desacoplada da configuração e
pode ser usada por qualquer tela Tk/CustomTkinter sem espalhar lógica de imagem.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable


@dataclass(frozen=True)
class BackgroundSettings:
    enabled: bool = True
    opacity: float = 0.10
    scale: str = "automática"
    position: str = "centro"


@dataclass(frozen=True)
class RenderMetrics:
    width: int
    height: int
    x: float
    y: float
    anchor: str


class BackgroundManager:
    """Marca d'água única, responsiva e com cache limitado.

    ``attach`` cria no máximo um widget de fundo por container. ``refresh`` usa
    debounce para resize e só recria a imagem quando dimensões/configuração
    efetivamente mudam. O widget é sempre rebaixado na pilha visual para não
    interceptar componentes funcionais.
    """

    SCALE_FACTORS = {
        "automática": 0.42,
        "pequena": 0.24,
        "média": 0.36,
        "grande": 0.52,
    }
    POSITIONS = {
        "centro": (0.5, 0.5, "center"),
        "superior": (0.5, 0.08, "n"),
        "inferior": (0.5, 0.92, "s"),
    }
    MIN_OPACITY = 0.02
    MAX_OPACITY = 0.25
    DEFAULT_DEBOUNCE_MS = 80
    MAX_CACHE_ITEMS = 4

    def __init__(
        self,
        *,
        logo_path: str | Path | None = None,
        settings: BackgroundSettings | None = None,
        debounce_ms: int = DEFAULT_DEBOUNCE_MS,
        image_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.logo_path = Path(logo_path).expanduser() if logo_path else None
        self.settings = self._normalize_settings(settings or BackgroundSettings())
        self.debounce_ms = max(20, int(debounce_ms))
        self._image_factory = image_factory
        self._targets: dict[int, dict[str, Any]] = {}
        self._image_cache: OrderedDict[tuple[Any, ...], Any] = OrderedDict()
        self._source_image: Any = None
        self._source_signature: tuple[str, int, int] | None = None
        self._render_count = 0
        self._last_render_seconds = 0.0

    @classmethod
    def _normalize_settings(cls, settings: BackgroundSettings) -> BackgroundSettings:
        scale = str(settings.scale or "automática").strip().lower()
        if scale not in cls.SCALE_FACTORS:
            scale = "automática"
        position = str(settings.position or "centro").strip().lower()
        if position not in cls.POSITIONS:
            position = "centro"
        try:
            opacity = float(settings.opacity)
        except (TypeError, ValueError):
            opacity = 0.10
        opacity = max(cls.MIN_OPACITY, min(cls.MAX_OPACITY, opacity))
        return BackgroundSettings(bool(settings.enabled), opacity, scale, position)

    @classmethod
    def render_metrics(
        cls,
        container_width: int,
        container_height: int,
        source_width: int,
        source_height: int,
        *,
        scale: str = "automática",
        position: str = "centro",
    ) -> RenderMetrics:
        if min(container_width, container_height, source_width, source_height) <= 0:
            raise ValueError("Dimensões de container e logo devem ser positivas.")
        normalized_scale = scale if scale in cls.SCALE_FACTORS else "automática"
        factor = cls.SCALE_FACTORS[normalized_scale]
        max_width = max(1, int(container_width * factor))
        max_height = max(1, int(container_height * factor))
        ratio = min(max_width / source_width, max_height / source_height)
        width = max(1, int(round(source_width * ratio)))
        height = max(1, int(round(source_height * ratio)))
        relx, rely, anchor = cls.POSITIONS.get(position, cls.POSITIONS["centro"])
        return RenderMetrics(width, height, relx, rely, anchor)

    def attach(self, container: Any) -> Any | None:
        key = id(container)
        state = self._targets.get(key)
        if state is not None:
            self.refresh(container, immediate=True)
            return state.get("label")
        state = {"container": container, "label": None, "after_id": None, "last_key": None}
        self._targets[key] = state
        try:
            bind_id = container.bind("<Configure>", lambda _event, c=container: self.refresh(c), add="+")
        except TypeError:
            bind_id = container.bind("<Configure>", lambda _event, c=container: self.refresh(c))
        state["bind_id"] = bind_id
        self.refresh(container, immediate=True)
        return state.get("label")

    def detach(self, container: Any) -> None:
        state = self._targets.pop(id(container), None)
        if not state:
            return
        after_id = state.get("after_id")
        if after_id:
            try:
                container.after_cancel(after_id)
            except Exception:
                pass
        label = state.get("label")
        if label is not None:
            try:
                label.destroy()
            except Exception:
                pass

    def refresh(self, container: Any | None = None, *, immediate: bool = False) -> None:
        targets = [self._targets.get(id(container))] if container is not None else list(self._targets.values())
        for state in (item for item in targets if item):
            owner = state["container"]
            old_after = state.get("after_id")
            if old_after:
                try:
                    owner.after_cancel(old_after)
                except Exception:
                    pass
                state["after_id"] = None
            if immediate:
                self._render_state(state)
            else:
                state["after_id"] = owner.after(self.debounce_ms, lambda s=state: self._render_state(s))

    def set_enabled(self, enabled: bool) -> None:
        self.settings = BackgroundSettings(bool(enabled), self.settings.opacity, self.settings.scale, self.settings.position)
        self.refresh(immediate=True)

    def set_opacity(self, opacity: float) -> None:
        self.settings = self._normalize_settings(BackgroundSettings(self.settings.enabled, opacity, self.settings.scale, self.settings.position))
        self._image_cache.clear()
        self.refresh(immediate=True)

    def set_scale(self, scale: str) -> None:
        self.settings = self._normalize_settings(BackgroundSettings(self.settings.enabled, self.settings.opacity, scale, self.settings.position))
        self.refresh(immediate=True)

    def set_position(self, position: str) -> None:
        self.settings = self._normalize_settings(BackgroundSettings(self.settings.enabled, self.settings.opacity, self.settings.scale, position))
        self.refresh(immediate=True)

    def set_logo_path(self, logo_path: str | Path | None) -> None:
        path = Path(logo_path).expanduser() if logo_path else None
        if path == self.logo_path:
            return
        self.logo_path = path
        self._source_image = None
        self._source_signature = None
        self._image_cache.clear()
        self.refresh(immediate=True)

    @property
    def diagnostics(self) -> dict[str, Any]:
        return {
            "attached": len(self._targets),
            "cache_items": len(self._image_cache),
            "render_count": self._render_count,
            "last_render_seconds": self._last_render_seconds,
        }

    def _render_state(self, state: dict[str, Any]) -> None:
        state["after_id"] = None
        container = state["container"]
        label = state.get("label")
        if not self.settings.enabled or not self._valid_logo_path():
            if label is not None:
                try:
                    label.place_forget()
                except Exception:
                    pass
            return
        try:
            width = int(container.winfo_width())
            height = int(container.winfo_height())
        except Exception:
            return
        if width <= 1 or height <= 1:
            return

        source = self._load_source()
        if source is None:
            return
        metrics = self.render_metrics(width, height, source.width, source.height, scale=self.settings.scale, position=self.settings.position)
        cache_key = (self._source_signature, metrics.width, metrics.height, round(self.settings.opacity, 4))
        if state.get("last_key") == cache_key and label is not None:
            self._place_and_lower(label, metrics)
            return

        started = perf_counter()
        photo = self._get_photo(source, cache_key, metrics)
        if photo is None:
            return
        if label is None:
            label = self._create_label(container, photo)
            state["label"] = label
        else:
            label.configure(image=photo)
        label.image = photo
        state["last_key"] = cache_key
        self._place_and_lower(label, metrics)
        self._render_count += 1
        self._last_render_seconds = perf_counter() - started

    def _valid_logo_path(self) -> bool:
        return bool(self.logo_path and self.logo_path.is_file())

    def _load_source(self) -> Any | None:
        if not self._valid_logo_path():
            return None
        assert self.logo_path is not None
        try:
            stat = self.logo_path.stat()
            signature = (str(self.logo_path.resolve()), int(stat.st_mtime_ns), int(stat.st_size))
        except OSError:
            return None
        if self._source_image is not None and signature == self._source_signature:
            return self._source_image
        try:
            from PIL import Image
            source = Image.open(self.logo_path).convert("RGBA")
        except Exception:
            return None
        self._source_image = source
        self._source_signature = signature
        self._image_cache.clear()
        return source

    def _get_photo(self, source: Any, cache_key: tuple[Any, ...], metrics: RenderMetrics) -> Any | None:
        cached = self._image_cache.get(cache_key)
        if cached is not None:
            self._image_cache.move_to_end(cache_key)
            return cached
        try:
            from PIL import Image
            resized = source.resize((metrics.width, metrics.height), Image.Resampling.LANCZOS)
            alpha = resized.getchannel("A").point(lambda value: int(value * self.settings.opacity))
            resized.putalpha(alpha)
            factory = self._image_factory
            if factory is None:
                from PIL import ImageTk
                factory = ImageTk.PhotoImage
            photo = factory(resized)
        except Exception:
            return None
        self._image_cache[cache_key] = photo
        while len(self._image_cache) > self.MAX_CACHE_ITEMS:
            self._image_cache.popitem(last=False)
        return photo

    @staticmethod
    def _create_label(container: Any, photo: Any) -> Any:
        import tkinter as tk
        return tk.Label(container, image=photo, borderwidth=0, highlightthickness=0, takefocus=0)

    @staticmethod
    def _place_and_lower(label: Any, metrics: RenderMetrics) -> None:
        label.place(relx=metrics.x, rely=metrics.y, anchor=metrics.anchor)
        try:
            label.lower()
        except Exception:
            pass
