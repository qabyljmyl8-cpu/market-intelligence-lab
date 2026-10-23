"""Small thread-safe in-process TTL cache; no disk writes or secret storage."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any

@dataclass
class CacheEntry:
    value: Any
    expires_at: datetime

class TTLCache:
    def __init__(self, ttl_seconds: int = 60):
        self.ttl_seconds = max(0, int(ttl_seconds))
        self._entries: dict[str, CacheEntry] = {}
        self._lock = RLock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= datetime.now(timezone.utc):
                self._entries.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = self.ttl_seconds if ttl_seconds is None else max(0, int(ttl_seconds))
        with self._lock:
            self._entries[key] = CacheEntry(value, datetime.now(timezone.utc) + timedelta(seconds=ttl))

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
