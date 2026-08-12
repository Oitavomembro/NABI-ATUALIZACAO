from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc

from PIL import Image

from ui.background_manager import BackgroundManager, BackgroundSettings


class FakePhoto:
    def __init__(self, width, height):
        self.width = width
        self.height = height


class FakeLabel:
    def __init__(self):
        self.image = None
        self.configure_calls = 0
        self.place_calls = 0
        self.lower_calls = 0
        self.forgotten = False
        self.destroyed = False

    def configure(self, **kwargs):
        self.configure_calls += 1
        self.image = kwargs.get("image", self.image)

    def place(self, **_kwargs):
        self.place_calls += 1

    def lower(self):
        self.lower_calls += 1

    def place_forget(self):
        self.forgotten = True

    def destroy(self):
        self.destroyed = True


class FakeContainer:
    def __init__(self, width=1280, height=720):
        self.width = width
        self.height = height
        self.after_callbacks = {}
        self.next_after = 1
        self.cancelled = []
        self.bindings = []

    def winfo_width(self): return self.width
    def winfo_height(self): return self.height
    def bind(self, sequence, callback, add=None):
        self.bindings.append((sequence, callback, add))
        return "bind-1"
    def after(self, _delay, callback):
        key = f"after-{self.next_after}"
        self.next_after += 1
        self.after_callbacks[key] = callback
        return key
    def after_cancel(self, key):
        self.cancelled.append(key)
        self.after_callbacks.pop(key, None)


def _logo(path: Path, size=(800, 400)):
    Image.new("RGBA", size, (255, 255, 255, 255)).save(path)


def _manager(path: Path):
    manager = BackgroundManager(logo_path=path, image_factory=lambda image: FakePhoto(image.width, image.height))
    manager._create_label = lambda _container, _photo: FakeLabel()
    return manager


def test_preserves_logo_proportion_across_required_resolutions():
    for width, height in ((1024,768),(1280,720),(1366,768),(1600,900),(1920,1080),(2560,1440),(3840,2160)):
        metrics = BackgroundManager.render_metrics(width, height, 800, 400)
        assert abs((metrics.width / metrics.height) - 2.0) < 0.02
        assert metrics.width <= int(width * BackgroundManager.SCALE_FACTORS["automática"])


def test_settings_normalize_dark_safe_opacity_scale_and_position():
    manager = BackgroundManager(settings=BackgroundSettings(True, 0.9, "inválida", "x"))
    assert manager.settings.opacity == 0.25
    assert manager.settings.scale == "automática"
    assert manager.settings.position == "centro"


def test_enabled_disabled_and_widget_stays_below_components():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "logo.png"; _logo(path)
        manager = _manager(path); container = FakeContainer()
        label = manager.attach(container)
        assert label is not None and label.lower_calls >= 1
        manager.set_enabled(False)
        assert label.forgotten is True
        manager.set_enabled(True)
        assert label.place_calls >= 2


def test_resize_is_debounced_and_does_not_redraw_same_size():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "logo.png"; _logo(path)
        manager = _manager(path); container = FakeContainer()
        manager.attach(container)
        initial = manager.diagnostics["render_count"]
        for _ in range(50): manager.refresh(container)
        assert len(container.after_callbacks) == 1
        callback = next(iter(container.after_callbacks.values())); callback()
        assert manager.diagnostics["render_count"] == initial
        container.width = 1366; manager.refresh(container, immediate=True)
        assert manager.diagnostics["render_count"] == initial + 1


def test_cache_is_bounded_and_memory_does_not_grow_unbounded_during_resizes():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "logo.png"; _logo(path)
        manager = _manager(path); container = FakeContainer()
        manager.attach(container)
        tracemalloc.start(); before = tracemalloc.take_snapshot()
        for width in range(1000, 1800, 7):
            container.width = width
            manager.refresh(container, immediate=True)
        after = tracemalloc.take_snapshot(); tracemalloc.stop()
        growth = sum(stat.size_diff for stat in after.compare_to(before, "filename"))
        assert manager.diagnostics["cache_items"] <= manager.MAX_CACHE_ITEMS
        assert growth < 2_000_000


def test_resize_rendering_performance_is_bounded():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "logo.png"; _logo(path, (1200, 600))
        manager = _manager(path); container = FakeContainer()
        manager.attach(container)
        started = perf_counter()
        for width, height in ((1024,768),(1280,720),(1366,768),(1600,900),(1920,1080),(2560,1440),(3840,2160)):
            container.width, container.height = width, height
            manager.refresh(container, immediate=True)
        elapsed = perf_counter() - started
        assert elapsed < 1.5


def test_opacity_changes_alpha_without_creating_unbounded_cache():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "logo.png"; _logo(path)
        manager = _manager(path); container = FakeContainer()
        manager.attach(container)
        manager.set_opacity(0.05)
        assert manager.settings.opacity == 0.05
        assert manager.diagnostics["cache_items"] <= manager.MAX_CACHE_ITEMS
