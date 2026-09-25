# Engineering Task — In-Memory Rate Limiter

Implement a thread-safe in-memory rate limiter for a Python application.

## Requirements

Create:

`solution.py`

Implement a class:

`RateLimiter`

Constructor:

RateLimiter(
    max_requests: int = 5,
    window_seconds: float = 10
)

Implement:

allow(user_id: str) -> bool

## Behavior

Each user may make at most `max_requests`
within the configured time window.

Example:

max_requests = 5
window_seconds = 10

For user "alice":

Request 1 → True
Request 2 → True
Request 3 → True
Request 4 → True
Request 5 → True
Request 6 → False

After enough requests expire from the time window,
new requests must be allowed again.

## User Isolation

Users must be tracked independently.

If Alice reaches her limit, Bob must still be able
to make requests.

## Sliding Window

The rate limit must use a sliding time window.

Expired request timestamps must not count toward
the current limit.

## Concurrency

Multiple threads may call:

allow(user_id)

at the same time.

The implementation must be thread-safe.

Concurrent requests must never allow a user to exceed
the configured limit.

## Validation

Reject invalid configuration:

max_requests <= 0

window_seconds <= 0

Reject an empty user_id.

## Constraints

Use Python standard library only.

Do not use:

- Redis
- databases
- external packages
- web frameworks

The implementation is for a single application process.

Keep the solution simple and testable.