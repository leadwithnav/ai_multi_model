# Engineering Task — Resilient Payment Processing Service

Implement an in-memory payment processing service that safely
interacts with an unreliable external payment provider.

The service must handle retries, idempotency, concurrency,
timeouts, and provider failures without accidentally charging
a payment twice.

Create:

`solution.py`


# Provider Interface

The PaymentProcessor receives an external provider as a dependency.

The provider exposes:

provider.charge(
    payment_id: str,
    customer_id: str,
    amount: float
)

The provider will be mocked during testing.

Do not implement a real HTTP API.


# PaymentProcessor

Implement:

PaymentProcessor(
    provider,
    max_attempts: int = 3,
    initial_backoff: float = 1.0,
    sleep_fn=None
)

Implement:

process_payment(
    payment_id: str,
    customer_id: str,
    amount: float
) -> PaymentResult


# PaymentResult

Return a PaymentResult containing:

- payment_id
- status
- attempts
- provider_reference
- error

Possible status values:

SUCCESS
FAILED


# Requirement 1 — Validation

Reject:

- empty payment_id
- empty customer_id
- amount <= 0

Validation must happen before calling the provider.


# Requirement 2 — Successful Payment

When the provider successfully processes the payment:

return:

status = SUCCESS

and include the provider reference returned by the provider.


# Requirement 3 — Retry Temporary Failures

Retry these failures:

- TimeoutError
- ConnectionError
- RateLimitError

Maximum attempts must be configurable.

Default:

3 attempts.


# Requirement 4 — Do Not Retry Permanent Failures

Do NOT retry:

- ValidationError
- AuthenticationError
- InvalidPaymentError

The payment must immediately return FAILED.


# Requirement 5 — Exponential Backoff

Temporary failures must use exponential backoff.

With:

initial_backoff = 1

the retry delays should be:

1 second
2 seconds
4 seconds
...

The sleep function must be injectable.

Tests must therefore be able to supply a fake sleep function
without actually waiting.


# Requirement 6 — Idempotency

A successfully completed payment_id must never be charged twice.

Example:

process_payment(
    "PAY-100",
    "CUSTOMER-1",
    100
)

→ SUCCESS

Calling the same payment again:

process_payment(
    "PAY-100",
    "CUSTOMER-1",
    100
)

must return the previously successful result.

provider.charge() must NOT be called again.


# Requirement 7 — Idempotency Conflict

If a successful payment_id is reused with different payment data,
the request must be rejected.

Example:

First request:

PAY-100
CUSTOMER-1
100

Later request:

PAY-100
CUSTOMER-1
500

must NOT return the previous success as though the new request
were valid.

It must NOT charge the provider again.


# Requirement 8 — Failed Payments Can Be Retried Later

A FAILED payment must NOT be stored as a successful
idempotency result.

Example:

PAY-200
→ all provider attempts fail
→ FAILED

A later request for PAY-200 must be allowed to try the
provider again.


# Requirement 9 — Concurrent Duplicate Requests

Multiple threads may call process_payment() concurrently.

Two concurrent requests using the same payment_id must NOT
cause two provider charges.

Only one payment operation for a particular payment_id may
execute at a time.

Other callers for the same payment_id must observe the
result of the payment operation rather than independently
charging the provider.


# Requirement 10 — Independent Payments

Different payment IDs should be able to make progress
independently.

Processing:

PAY-100

must not unnecessarily block:

PAY-200

A single global lock around the entire provider operation
does not satisfy this requirement.


# Requirement 11 — Attempt Count

PaymentResult.attempts must represent the number of actual
provider calls made for that processing attempt.

Example:

provider succeeds immediately
→ attempts = 1

provider fails twice and succeeds on third call
→ attempts = 3


# Requirement 12 — Error Handling

When processing fails, PaymentResult must contain useful
error information.

Do not expose stack traces as the error value.


# Constraints

Use Python standard library only.

Do not use:

- Redis
- databases
- external retry libraries
- web frameworks

The solution runs inside a single Python application process.

The implementation should be:

- thread-safe
- testable
- maintainable
- extensible