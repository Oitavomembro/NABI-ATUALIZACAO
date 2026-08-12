from __future__ import annotations

from typing import Callable, TypeVar


T = TypeVar("T")


def cached_instance(owner: object, attribute: str, factory: Callable[[], T]) -> T:
    instance = getattr(owner, attribute, None)
    if instance is None:
        instance = factory()
        setattr(owner, attribute, instance)
    return instance
