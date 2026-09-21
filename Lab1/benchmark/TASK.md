Implement the in-memory rate limiter in:

../order-flow-service/src/utils/rate_limiter.py

The rate limiter should prevent a client from exceeding a configurable
number of requests within a configurable time window.

The implementation should be suitable for use in a concurrent web application.

Requirements:

- Preserve the existing public interface.
- Do not modify unrelated files.
- Keep the implementation simple and maintainable.

When finished, return a short summary of what you changed.