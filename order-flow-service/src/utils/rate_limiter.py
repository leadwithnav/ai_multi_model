import time
import threading
from typing import Dict, List, Tuple
from fastapi import HTTPException, status, Request

class RateLimitExceeded(HTTPException):
    """Exception raised when a rate limit is exceeded (HTTP 429)."""
    def __init__(self, detail: str = "Rate limit exceeded", retry_after: float = 60.0):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(int(round(retry_after)))}
        )
        self.retry_after = retry_after


class RateLimiter:
    """
    Sliding window log Rate Limiter implementation.
    Thread-safe and supports cost-weighted request tracking, key isolation, 
    remaining token queries, key reset, and retry-after estimations.
    """
    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0):
        if max_requests <= 0:
            raise ValueError("max_requests must be greater than 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than 0")
            
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def _clean_old_entries(self, key: str, now: float) -> None:
        """Removes timestamps outside the current sliding window."""
        cutoff = now - self.window_seconds
        if key in self._history:
            self._history[key] = [t for t in self._history[key] if t > cutoff]
            if not self._history[key]:
                del self._history[key]

    def is_allowed(self, key: str, cost: int = 1) -> bool:
        """
        Check if a request with given cost is allowed under current rate limits.
        If allowed, records the consumption and returns True. Otherwise False.
        """
        allowed, _, _ = self.check(key, cost)
        return allowed

    def check(self, key: str, cost: int = 1) -> Tuple[bool, int, float]:
        """
        Checks rate limit status for key with specified cost.
        Returns: (is_allowed, remaining_quota, retry_after_seconds)
        """
        if cost <= 0:
            raise ValueError("cost must be greater than 0")
        if not key:
            raise ValueError("key cannot be empty")

        now = time.time()
        with self._lock:
            self._clean_old_entries(key, now)
            timestamps = self._history.get(key, [])
            current_usage = len(timestamps)

            if current_usage + cost <= self.max_requests:
                for _ in range(cost):
                    timestamps.append(now)
                self._history[key] = timestamps
                remaining = self.max_requests - len(timestamps)
                return True, remaining, 0.0
            else:
                remaining = max(0, self.max_requests - current_usage)
                # Calculate retry_after based on when enough timestamps will expire
                needed = (current_usage + cost) - self.max_requests
                if timestamps and needed <= len(timestamps):
                    earliest_rel = timestamps[needed - 1]
                    retry_after = max(0.001, (earliest_rel + self.window_seconds) - now)
                else:
                    retry_after = float(self.window_seconds)
                return False, remaining, retry_after

    def get_remaining(self, key: str) -> int:
        """Returns remaining capacity in the current window for key."""
        now = time.time()
        with self._lock:
            self._clean_old_entries(key, now)
            current_usage = len(self._history.get(key, []))
            return max(0, self.max_requests - current_usage)

    def reset(self, key: str) -> None:
        """Resets tracked request history for a single key."""
        with self._lock:
            if key in self._history:
                del self._history[key]

    def clear(self) -> None:
        """Clears all tracked keys and state."""
        with self._lock:
            self._history.clear()


def create_rate_limit_dependency(limiter: RateLimiter):
    """Factory function for FastAPI route dependency."""
    async def dependency(request: Request):
        client_ip = request.client.host if request.client else "127.0.0.1"
        allowed, remaining, retry_after = limiter.check(client_ip)
        if not allowed:
            raise RateLimitExceeded(
                detail=f"Rate limit exceeded. Try again in {retry_after:.1f} seconds.",
                retry_after=retry_after
            )
        return client_ip
    return dependency
