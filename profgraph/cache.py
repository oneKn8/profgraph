"""Simple in-memory TTL cache."""

import time
from typing import Any


class TTLCache:
    """Key-value cache with per-entry expiration."""

    def __init__(self, default_ttl: int = 86400):
        self._store: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        if key in self._store:
            value, expires = self._store[key]
            if time.time() < expires:
                return value
            self._store.pop(key, None)
        return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self._store[key] = (value, time.time() + (self._default_ttl if ttl is None else ttl))

    def clear(self) -> None:
        self._store.clear()
