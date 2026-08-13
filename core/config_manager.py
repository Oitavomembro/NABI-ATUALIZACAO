from __future__ import annotations

import json
import os
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


class ConfigManager:
    """Gerencia configurações JSON com gravação atômica e acesso por chave pontuada."""

    def __init__(self, path: str | os.PathLike[str], defaults: Mapping[str, Any] | None = None):
        self.path = Path(path)
        self.defaults = deepcopy(dict(defaults or {}))
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self.reload()

    def reload(self) -> dict[str, Any]:
        with self._lock:
            loaded: dict[str, Any] = {}
            if self.path.exists():
                try:
                    with self.path.open("r", encoding="utf-8") as handle:
                        candidate = json.load(handle)
                    if not isinstance(candidate, dict):
                        raise ValueError("O arquivo de configuração deve conter um objeto JSON.")
                    loaded = candidate
                except (OSError, json.JSONDecodeError, ValueError):
                    corrupt_path = self.path.with_suffix(self.path.suffix + ".corrompido")
                    try:
                        self.path.replace(corrupt_path)
                    except OSError:
                        pass
            self._data = self._merge(deepcopy(self.defaults), loaded)
            if not self.path.exists() or self._data != loaded:
                self.save()
            return deepcopy(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        if not key:
            return deepcopy(self._data)
        with self._lock:
            current: Any = self._data
            for part in key.split("."):
                if not isinstance(current, dict) or part not in current:
                    return deepcopy(default)
                current = current[part]
            return deepcopy(current)

    def set(self, key: str, value: Any, *, persist: bool = True) -> None:
        if not key:
            raise ValueError("A chave de configuração não pode ser vazia.")
        with self._lock:
            previous = deepcopy(self._data)
            current = self._data
            parts = key.split(".")
            for part in parts[:-1]:
                child = current.get(part)
                if not isinstance(child, dict):
                    child = {}
                    current[part] = child
                current = child
            current[parts[-1]] = deepcopy(value)
            if persist:
                try:
                    self.save()
                except Exception:
                    self._data = previous
                    raise

    def update(self, values: Mapping[str, Any], *, persist: bool = True) -> None:
        with self._lock:
            previous = deepcopy(self._data)
            self._data = self._merge(self._data, dict(values))
            if persist:
                try:
                    self.save()
                except Exception:
                    self._data = previous
                    raise

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temp_name = tempfile.mkstemp(
                prefix=self.path.name + ".", suffix=".tmp", dir=str(self.path.parent)
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(self._data, handle, ensure_ascii=False, indent=2, sort_keys=True)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, self.path)
            except Exception:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass
                raise

    @classmethod
    def _merge(cls, base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
        for key, value in override.items():
            if isinstance(value, Mapping) and isinstance(base.get(key), dict):
                base[key] = cls._merge(base[key], value)
            else:
                base[key] = deepcopy(value)
        return base
