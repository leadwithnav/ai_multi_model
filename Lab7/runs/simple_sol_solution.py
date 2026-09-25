"""Thread-safe, in-memory sliding-window rate limiter."""

from collections import deque
import threading
import time
from typing import Deque, Dict


class RateLimiter:
    """Limit requests independently for each user over a sliding window."""

    def __init__(
        self, max_requests: int = 5, window_seconds: float = 10
    ) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be greater than zero")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, user_id: str) -> bool:
        """Return whether a request is allowed, recording it if it is."""
        if not user_id:
            raise ValueError("user_id must not be empty")

        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            requests = self._requests.get(user_id)
            if requests is None:
                requests = deque()
                self._requests[user_id] = requests

            while requests and requests[0] <= cutoff:
                requests.popleft()

            if len(requests) >= self.max_requests:
                return False

            requests.append(now)
            return True
