import time
import asyncio
import pytest
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Depends, status
from fastapi.testclient import TestClient

from src.utils.rate_limiter import (
    RateLimiter,
    RateLimitExceeded,
    create_rate_limit_dependency,
)

# ---------------------------------------------------------------------------
# Acceptance Test 1: Basic requests within limit are allowed
# ---------------------------------------------------------------------------
def test_01_basic_allow_within_limit():
    """Verify requests within max_requests capacity are granted."""
    limiter = RateLimiter(max_requests=5, window_seconds=60.0)
    client_ip = "192.168.1.1"

    for i in range(5):
        assert limiter.is_allowed(client_ip) is True, f"Request {i+1} should be allowed"


# ---------------------------------------------------------------------------
# Acceptance Test 2: Requests exceeding limit are blocked
# ---------------------------------------------------------------------------
def test_02_exceed_limit_blocks_request():
    """Verify that making max_requests + 1 requests causes rejection."""
    limiter = RateLimiter(max_requests=3, window_seconds=60.0)
    key = "user_123"

    for _ in range(3):
        assert limiter.is_allowed(key) is True

    # 4th request must fail
    assert limiter.is_allowed(key) is False
    assert limiter.get_remaining(key) == 0


# ---------------------------------------------------------------------------
# Acceptance Test 3: Key isolation across distinct clients
# ---------------------------------------------------------------------------
def test_03_key_isolation():
    """Verify rate limits are tracked independently per key/client IP."""
    limiter = RateLimiter(max_requests=2, window_seconds=60.0)
    key_a = "10.0.0.1"
    key_b = "10.0.0.2"

    # Exhaust key_a capacity
    assert limiter.is_allowed(key_a) is True
    assert limiter.is_allowed(key_a) is True
    assert limiter.is_allowed(key_a) is False

    # key_b should remain completely unaffected
    assert limiter.is_allowed(key_b) is True
    assert limiter.is_allowed(key_b) is True
    assert limiter.get_remaining(key_b) == 0


# ---------------------------------------------------------------------------
# Acceptance Test 4: Window expiration resets capacity
# ---------------------------------------------------------------------------
def test_04_window_expiration():
    """Verify requests are allowed again after the window_seconds elapses."""
    window = 0.2  # 200 ms short window for testing
    limiter = RateLimiter(max_requests=2, window_seconds=window)
    key = "temp_client"

    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is False

    # Wait for window duration to pass
    time.sleep(window + 0.05)

    # Capacity should be recovered
    assert limiter.is_allowed(key) is True


# ---------------------------------------------------------------------------
# Acceptance Test 5: Sliding window partial capacity recovery
# ---------------------------------------------------------------------------
def test_05_sliding_window_partial_recovery():
    """Verify partial recovery as older timestamps slide out of window."""
    limiter = RateLimiter(max_requests=2, window_seconds=0.3)
    key = "sliding_user"

    # First request at t=0
    assert limiter.is_allowed(key) is True
    time.sleep(0.15)
    # Second request at t=0.15
    assert limiter.is_allowed(key) is True

    # Now fully loaded
    assert limiter.is_allowed(key) is False

    # Sleep so first request (t=0) expires but second (t=0.15) remains active
    time.sleep(0.20)  # total time = 0.35s > 0.3s window for request 1

    # Should allow 1 request
    assert limiter.is_allowed(key) is True
    # Immediately second should be blocked
    assert limiter.is_allowed(key) is False


# ---------------------------------------------------------------------------
# Acceptance Test 6: Immediate burst traffic handling
# ---------------------------------------------------------------------------
def test_06_burst_handling():
    """Verify rate limiter handles rapid bursts up to limit without failing."""
    capacity = 100
    limiter = RateLimiter(max_requests=capacity, window_seconds=10.0)
    key = "burst_ip"

    results = [limiter.is_allowed(key) for _ in range(capacity)]
    assert all(results), "All requests in burst under capacity must succeed"
    assert limiter.is_allowed(key) is False, "101st request must be blocked"


# ---------------------------------------------------------------------------
# Acceptance Test 7: Accurately query remaining quota
# ---------------------------------------------------------------------------
def test_07_remaining_tokens_count():
    """Verify get_remaining(key) returns accurate remaining request quota."""
    limiter = RateLimiter(max_requests=5, window_seconds=60.0)
    key = "quota_user"

    assert limiter.get_remaining(key) == 5
    limiter.is_allowed(key)
    assert limiter.get_remaining(key) == 4
    limiter.is_allowed(key)
    limiter.is_allowed(key)
    assert limiter.get_remaining(key) == 2


# ---------------------------------------------------------------------------
# Acceptance Test 8: Metadata check tuple (allowed, remaining, retry_after)
# ---------------------------------------------------------------------------
def test_08_check_tuple_metadata():
    """Verify check() method returns complete metadata tuple."""
    limiter = RateLimiter(max_requests=1, window_seconds=1.0)
    key = "metadata_client"

    allowed, remaining, retry_after = limiter.check(key)
    assert allowed is True
    assert remaining == 0
    assert retry_after == 0.0

    # Exceed limit
    allowed, remaining, retry_after = limiter.check(key)
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0.0, "retry_after must be positive when limit exceeded"


# ---------------------------------------------------------------------------
# Acceptance Test 9: Reset single key capacity
# ---------------------------------------------------------------------------
def test_09_reset_single_key():
    """Verify reset(key) clears history for a specific key only."""
    limiter = RateLimiter(max_requests=1, window_seconds=60.0)
    key1 = "client_1"
    key2 = "client_2"

    limiter.is_allowed(key1)
    limiter.is_allowed(key2)
    assert limiter.get_remaining(key1) == 0
    assert limiter.get_remaining(key2) == 0

    limiter.reset(key1)

    assert limiter.get_remaining(key1) == 1
    assert limiter.get_remaining(key2) == 0, "reset(key1) should not affect key2"


# ---------------------------------------------------------------------------
# Acceptance Test 10: Clear state across all keys
# ---------------------------------------------------------------------------
def test_10_clear_all_keys():
    """Verify clear() clears tracked state across all keys."""
    limiter = RateLimiter(max_requests=2, window_seconds=60.0)
    keys = ["a", "b", "c", "d"]

    for k in keys:
        limiter.is_allowed(k)
        limiter.is_allowed(k)
        assert limiter.get_remaining(k) == 0

    limiter.clear()

    for k in keys:
        assert limiter.get_remaining(k) == 2


# ---------------------------------------------------------------------------
# Acceptance Test 11: Cost-weighted requests support
# ---------------------------------------------------------------------------
def test_11_cost_weighted_requests():
    """Verify cost > 1 consumes multiple tokens and blocks when insufficient."""
    limiter = RateLimiter(max_requests=10, window_seconds=60.0)
    key = "heavy_api"

    # Consume 4 units
    allowed, remaining, _ = limiter.check(key, cost=4)
    assert allowed is True
    assert remaining == 6

    # Attempt to consume 7 units (6 remaining, so should fail)
    allowed, remaining, _ = limiter.check(key, cost=7)
    assert allowed is False
    assert remaining == 6


# ---------------------------------------------------------------------------
# Acceptance Test 12: Parameter validation edge cases
# ---------------------------------------------------------------------------
def test_12_invalid_parameters():
    """Verify ValueError is raised for invalid initialization or call parameters."""
    with pytest.raises(ValueError, match="max_requests must be greater than 0"):
        RateLimiter(max_requests=0, window_seconds=60.0)

    with pytest.raises(ValueError, match="window_seconds must be greater than 0"):
        RateLimiter(max_requests=10, window_seconds=-1.0)

    limiter = RateLimiter(max_requests=5, window_seconds=60.0)

    with pytest.raises(ValueError, match="cost must be greater than 0"):
        limiter.check("key", cost=0)

    with pytest.raises(ValueError, match="key cannot be empty"):
        limiter.check("", cost=1)


# ---------------------------------------------------------------------------
# Acceptance Test 13: Multithreaded concurrency safety
# ---------------------------------------------------------------------------
def test_13_concurrent_requests_thread_safety():
    """Verify thread-safety when multiple threads concurrently make requests."""
    capacity = 50
    limiter = RateLimiter(max_requests=capacity, window_seconds=60.0)
    key = "concurrent_key"

    def make_request(_):
        return limiter.is_allowed(key)

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(make_request, range(100)))

    allowed_count = sum(1 for r in results if r is True)
    blocked_count = sum(1 for r in results if r is False)

    assert allowed_count == capacity, f"Expected exactly {capacity} allowed, got {allowed_count}"
    assert blocked_count == 50, f"Expected 50 blocked, got {blocked_count}"


# ---------------------------------------------------------------------------
# Acceptance Test 14: FastAPI route dependency under limit
# ---------------------------------------------------------------------------
def test_14_fastapi_dependency_allowed():
    """Verify FastAPI dependency allows requests within limit."""
    limiter = RateLimiter(max_requests=2, window_seconds=60.0)
    app = FastAPI()

    @app.get("/test", dependencies=[Depends(create_rate_limit_dependency(limiter))])
    def sample_endpoint():
        return {"message": "success"}

    client = TestClient(app)

    response1 = client.get("/test")
    assert response1.status_code == status.HTTP_200_OK
    assert response1.json() == {"message": "success"}

    response2 = client.get("/test")
    assert response2.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Acceptance Test 15: FastAPI route dependency returns HTTP 429 on exceed
# ---------------------------------------------------------------------------
def test_15_fastapi_dependency_exceeded_429():
    """Verify FastAPI dependency raises HTTP 429 with Retry-After header on limit breach."""
    limiter = RateLimiter(max_requests=1, window_seconds=10.0)
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(create_rate_limit_dependency(limiter))])
    def protected_endpoint():
        return {"data": "ok"}

    client = TestClient(app)

    # 1st request succeeds
    resp1 = client.get("/protected")
    assert resp1.status_code == status.HTTP_200_OK

    # 2nd request fails with HTTP 429
    resp2 = client.get("/protected")
    assert resp2.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in resp2.headers
    assert resp2.json()["detail"].startswith("Rate limit exceeded")
