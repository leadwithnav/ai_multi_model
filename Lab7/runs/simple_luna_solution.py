"""Thread-safe in-memory sliding-window rate limiter."""

from collections import defaultdict, deque
import threading
import time


class RateLimiter:
    """Limit the number of requests made by each user in a time window."""

    def __init__(self, max_requests: int = 5, window_seconds: float = 10):
        if max_requests <= 0:
            raise ValueError("max_requests must be greater than zero")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, user_id: str) -> bool:
        """Return whether ``user_id`` may make a request now."""
        if not user_id:
            raise ValueError("user_id must not be empty")

        now = time.monotonic()
        with self._lock:
            timestamps = self._requests[user_id]
            cutoff = now - self.window_seconds

            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= self.max_requests:
                return False

            timestamps.append(now)
            return True
