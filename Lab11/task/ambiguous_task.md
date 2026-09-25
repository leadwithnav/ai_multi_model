# Engineering Task — Payment Processing

Implement a small payment processing component.

## Requirements

The system must:

1. Process a payment using an external payment provider.

2. Prevent the same payment from being processed twice.

3. Reject invalid payment amounts.

4. Convert provider failures into a safe application-level error.
   Internal provider details must not be exposed to callers.

5. Allow different payments to be processed concurrently.

6. Prevent concurrent processing of the same payment.

7. Provide a way for callers to determine whether a payment
   completed successfully.

## Constraints

- Python standard library only.
- The external payment provider is supplied by the caller.
- Money must not use binary floating-point arithmetic.
- Do not implement the external payment provider itself.