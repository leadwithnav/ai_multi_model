# Production Incident — Duplicate Payments

Production monitoring has detected a small number of orders where
customers were charged more than once.

The issue appears intermittently when:

- multiple requests for the same order arrive close together
- the payment provider is slow or temporarily unavailable
- a request is retried after a timeout

Investigate the order and payment processing flow and implement a fix.

Requirements:

- an order must never result in more than one successful payment
- concurrent requests for the same order must be handled safely
- retrying after temporary payment-provider failure must remain possible
- a failed payment attempt must not incorrectly mark the order as paid
- existing public APIs must remain unchanged
- do not serialize payment processing globally
- do not remove retry behavior simply to avoid duplicate calls
- do not modify unrelated functionality

Start your investigation from:

src/services/order_service.py

Inspect other relevant production code as needed.