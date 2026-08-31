"""Tiny in-memory TTL cache for repeated plate lookups.

Not distributed / not persistent -- fine for a single wrapper instance and
for demonstrating the pattern. In a real deployment with multiple
instances this would move to Redis or similar.
"""
import time
from typing import Optional

_TTL_SECONDS = 60
_store: dict[str, tuple[float, dict]] = {}


def get(key: str) -> Optional[dict]:
    entry = _store.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.time() > expires_at:
        _store.pop(key, None)
        return None
    return value


def set(key: str, value: dict) -> None:
    _store[key] = (time.time() + _TTL_SECONDS, value)
