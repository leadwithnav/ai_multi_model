"""A thread-safe, in-memory sliding-window rate limiter."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class RateLimiter:
    """Limit each user's allowed requests within a sliding time window.

    Instances are process-local.  A single lock protects the check-and-record
    operation so concurrent calls cannot admit more than the configured limit.
    """

    def __init__(self, max_requests: int = 5, window_seconds: float = 10):
        if max_requests <= 0:
            raise ValueError("max_requests must be greater than zero")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")

        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests = defaultdict(deque)
        self._lock = Lock()

    def allow(self, user_id: str) -> bool:
        """Return whether a request from *user_id* may proceed.

        Only allowed requests are recorded.  Timestamps exactly one window old
        are expired, so they no longer consume capacity.
        """
        if user_id == "":
            raise ValueError("user_id must not be empty")

        # Reading the clock while holding the lock keeps queue insertion order
        # consistent even when threads are scheduled between clock reads and
        # lock acquisition.
        with self._lock:
            now = monotonic()
            history = self._requests[user_id]
            boundary = now - self._window_seconds

            while history and history[0] <= boundary:
                history.popleft()

            if len(history) >= self._max_requests:
                return False

            history.append(now)
            return True
