# Engineering Task — In-Memory Rate Limiter

Implement the in-memory rate limiter in:

order-flow-service/src/utils/rate_limiter.py

The rate limiter should prevent a client from exceeding a configurable
number of requests within a configurable sliding time window.

## Required Public Interface

Implement:

RateLimiter(max_requests: int, window_seconds: float)

with the following methods:

- is_allowed(key: str) -> bool
  Check whether a request is allowed and consume one unit if allowed.

- get_remaining(key: str) -> int
  Return the remaining request capacity for the key.

- check(key: str, cost: int = 1) -> tuple[bool, int, float]
  Return:
  (allowed, remaining, retry_after)

  Support requests that consume more than one unit using `cost`.

- reset(key: str) -> None
  Clear rate-limit state for one key.

- clear() -> None
  Clear rate-limit state for all keys.

## Requirements

- Use sliding-window rate limiting.
- Track different client keys independently.
- Recover capacity as requests expire from the window.
- Support cost-weighted requests.
- Be safe for concurrent access.
- Validate invalid configuration and request parameters.
- Do not modify unrelated files.
- Keep the implementation simple and maintainable.

When finished, return a short summary of what you changed.