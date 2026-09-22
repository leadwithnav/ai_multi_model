# Production Incident — Payment Retry

Production monitoring has detected requests that remain active for
an unexpectedly long time when the external payment provider is
unavailable.

Investigate the payment processing implementation and fix the issue.

Requirements:

- Failed payment requests must not retry indefinitely.
- Temporary failures may be retried.
- Retry behavior must have a clear upper bound.
- Existing public interfaces must remain unchanged.
- Do not modify unrelated functionality.

Target area:

src/services/payment_gateway.py