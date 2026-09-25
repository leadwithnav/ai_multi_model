"""Thread-safe, in-memory sliding-window rate limiter."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Deque, DefaultDict


class RateLimiter:
    """Limit each user to a fixed number of requests in a sliding window."""

    def __init__(self, max_requests: int = 5, window_seconds: float = 10) -> None:
        if isinstance(max_requests, bool) or not isinstance(max_requests, int):
            raise ValueError("max_requests must be a positive integer")
        if max_requests <= 0:
            raise ValueError("max_requests must be greater than zero")
        if isinstance(window_seconds, bool) or not isinstance(window_seconds, (int, float)):
            raise ValueError("window_seconds must be greater than zero")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")

        self.max_requests = max_requests
        self.window_seconds = float(window_seconds)
        self._requests: DefaultDict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, user_id: str) -> bool:
        """Record and allow a request when that user's window has capacity."""
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("user_id must be a non-empty string")

        now = monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._requests[user_id]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= self.max_requests:
                return False

            timestamps.append(now)
            return True
