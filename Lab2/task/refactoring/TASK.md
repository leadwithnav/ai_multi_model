# Task Requirements: Refactor Order Service Component

Refactor `src/services/order_service.py` in the `order_flow_service` repository to improve maintainability and readability.

## Target Component
- `src/services/order_service.py`

## Refactoring Goals

1. **Improve Separation of Concerns & Readability**:
   - Decompose complex methods into clean, single-responsibility helper functions.
   - Eliminate duplicated status checks and hardcoded string literals by enforcing proper usage of `OrderStatus` enum values.
   - Improve clarity of item total calculation and stock reservation error handling.

2. **Preserve External Behavior & API Contracts**:
   - Preserve all existing public method signatures (`create_order`, `handle_payment_webhook`).
   - Preserve all exception types (`ValueError`) and error message expectations.
   - Ensure external API endpoints and database transaction semantics remain 100% compatible.

3. **Constraints**:
   - Do not change database schemas or model declarations.
   - Do not modify unrelated services or test suites.
   - Avoid unnecessary external dependencies.
