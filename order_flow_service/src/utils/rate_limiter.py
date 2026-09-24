"""
In-memory sliding-window rate limiter.

Tracks request timestamps per client key and enforces a maximum number
of request "units" (cost) within a configurable sliding time window.
Safe for concurrent access via a single lock guarding all state.
"""

import threading
import time
from collections import deque
from typing import Deque, Dict, Tuple


class RateLimiter:
    """A simple thread-safe, in-memory sliding-window rate limiter.

    Each client (identified by ``key``) is allowed at most
    ``max_requests`` units of cost within any ``window_seconds`` sliding
    window. Requests are recorded as ``(timestamp, cost)`` pairs; entries
    that fall outside of the current window are dropped before each
    check, which naturally recovers capacity over time.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        if not isinstance(max_requests, int) or isinstance(max_requests, bool):
            raise TypeError("max_requests must be an int")
        if max_requests <= 0:
            raise ValueError("max_requests must be a positive integer")
        if not isinstance(window_seconds, (int, float)) or isinstance(window_seconds, bool):
            raise TypeError("window_seconds must be a number")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be a positive number")

        self.max_requests = max_requests
        self.window_seconds = float(window_seconds)

        self._lock = threading.Lock()
        # key -> deque of (timestamp, cost)
        self._history: Dict[str, Deque[Tuple[float, int]]] = {}

    def _prune(self, key: str, now: float) -> Deque[Tuple[float, int]]:
        """Drop entries outside of the sliding window for ``key``.

        Must be called while holding ``self._lock``.
        """
        history = self._history.get(key)
        if history is None:
            history = deque()
            self._history[key] = history

        cutoff = now - self.window_seconds
        while history and history[0][0] <= cutoff:
            history.popleft()
        return history

    def check(self, key: str, cost: int = 1) -> Tuple[bool, int, float]:
        """Check (and, if allowed, record) a request of the given cost.

        Returns a tuple of ``(allowed, remaining, retry_after)``:
          - ``allowed``: whether the request may proceed.
          - ``remaining``: capacity left for the key after this check.
          - ``retry_after``: seconds to wait before capacity is available
            (0.0 if the request was allowed or if capacity never frees up
            within the window because ``cost`` exceeds ``max_requests``).
        """
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")
        if not isinstance(cost, int) or isinstance(cost, bool):
            raise TypeError("cost must be an int")
        if cost <= 0:
            raise ValueError("cost must be a positive integer")

        now = time.monotonic()

        with self._lock:
            history = self._prune(key, now)
            used = sum(c for _, c in history)

            if cost > self.max_requests:
                # This request can never succeed regardless of waiting.
                remaining = max(self.max_requests - used, 0)
                return False, remaining, 0.0

            if used + cost <= self.max_requests:
                history.append((now, cost))
                remaining = self.max_requests - (used + cost)
                return True, remaining, 0.0

            # Not enough capacity right now; compute retry_after based on
            # when enough of the oldest entries will expire.
            remaining = max(self.max_requests - used, 0)
            needed = used + cost - self.max_requests
            retry_after = 0.0
            freed = 0
            for ts, c in history:
                freed += c
                if freed >= needed:
                    retry_after = max((ts + self.window_seconds) - now, 0.0)
                    break

            return False, remaining, retry_after

    def is_allowed(self, key: str) -> bool:
        """Check whether a single-unit request is allowed, consuming
        one unit of capacity if it is."""
        allowed, _remaining, _retry_after = self.check(key, cost=1)
        return allowed

    def get_remaining(self, key: str) -> int:
        """Return the remaining capacity for ``key`` without consuming
        any capacity."""
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")

        now = time.monotonic()
        with self._lock:
            history = self._prune(key, now)
            used = sum(c for _, c in history)
            return max(self.max_requests - used, 0)

    def reset(self, key: str) -> None:
        """Clear all rate-limit state for a single key."""
        with self._lock:
            self._history.pop(key, None)

    def clear(self) -> None:
        """Clear rate-limit state for all keys."""
        with self._lock:
            self._history.clear()
