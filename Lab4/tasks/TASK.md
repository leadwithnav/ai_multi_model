# Production Incident — Duplicate Payment Processing

Production monitoring has detected a small number of orders where
customers were charged more than once.

The issue appears intermittently when:

- multiple requests for the same order arrive close together,
- the payment provider is slow or temporarily unavailable,
- a request is retried after a timeout.

Investigate the order and payment processing flow and implement a fix.

## Requirements

- An order must never result in more than one successful payment.
- Concurrent requests for the same order must be handled safely.
- Retrying after a temporary payment-provider failure must remain possible.
- A failed payment attempt must not incorrectly mark the order as paid.
- Existing public APIs must remain unchanged.
- Do not serialize payment processing globally.
- Do not remove retry behavior simply to avoid duplicate calls.
- Do not modify unrelated functionality.

## Target Areas

Start your investigation from:

`src/services/order_service.py`

You may inspect and modify other relevant production files if required.