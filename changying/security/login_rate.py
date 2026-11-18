"""Bounded in-memory login rate state.

Keeps per-client failure history bounded so hostile or accidental high-cardinality
source addresses cannot grow process memory without limit.
"""

from __future__ import annotations

from collections import OrderedDict
import threading
import time
from typing import Callable


class LoginRateLimitExceeded(RuntimeError):
    """Raised when a client is rate-limited or the bounded tracker is saturated."""


class BoundedLoginRateLimiter:
    def __init__(
        self,
        *,
        window_seconds: int,
        max_attempts: int,
        max_keys: int = 2048,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.window_seconds = max(1, int(window_seconds))
        self.max_attempts = max(1, int(max_attempts))
        self.max_keys = max(32, min(int(max_keys), 65536))
        self._clock = clock
        self._hits: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()

    def _fresh(self, hits: list[float], now: float) -> list[float]:
        cutoff = now - self.window_seconds
        return [value for value in hits if value > cutoff]

    def _prune_stale_locked(self, now: float) -> None:
        stale: list[str] = []
        for key, hits in self._hits.items():
            fresh = self._fresh(hits, now)
            if fresh:
                if len(fresh) != len(hits):
                    self._hits[key] = fresh
            else:
                stale.append(key)
        for key in stale:
            self._hits.pop(key, None)

    def _evict_oldest_unlocked_locked(self) -> bool:
        """Drop the oldest key that has not hit its limit, so new clients still work."""
        for key in list(self._hits.keys()):
            if len(self._hits[key]) < self.max_attempts:
                self._hits.pop(key, None)
                return True
        return False

    def _ensure_capacity_locked(self) -> None:
        if len(self._hits) < self.max_keys:
            return
        if not self._evict_oldest_unlocked_locked():
            # Every tracked key is currently locked out; refusing is safer than forgetting.
            raise LoginRateLimitExceeded("login tracker capacity reached")

    def check(self, key: str) -> None:
        normalized = str(key or "unknown")[:256]
        now = self._clock()
        with self._lock:
            self._prune_stale_locked(now)
            hits = self._hits.get(normalized)
            if hits is not None:
                self._hits.move_to_end(normalized)
                if len(hits) >= self.max_attempts:
                    raise LoginRateLimitExceeded("too many login attempts")
                return
            self._ensure_capacity_locked()

    def failure(self, key: str) -> None:
        normalized = str(key or "unknown")[:256]
        now = self._clock()
        with self._lock:
            self._prune_stale_locked(now)
            hits = self._hits.get(normalized)
            if hits is None:
                self._ensure_capacity_locked()
                hits = []
                self._hits[normalized] = hits
            hits.append(now)
            if len(hits) > self.max_attempts:
                del hits[:-self.max_attempts]
            self._hits.move_to_end(normalized)

    def count(self, key: str) -> int:
        """How many failures are still inside the window for this key (0 when unknown)."""
        normalized = str(key or "unknown")[:256]
        now = self._clock()
        with self._lock:
            hits = self._hits.get(normalized)
            if not hits:
                return 0
            return len(self._fresh(hits, now))

    def clear(self, key: str) -> None:
        normalized = str(key or "unknown")[:256]
        with self._lock:
            self._hits.pop(normalized, None)

    def size(self) -> int:
        with self._lock:
            return len(self._hits)


__all__ = ["BoundedLoginRateLimiter", "LoginRateLimitExceeded"]
