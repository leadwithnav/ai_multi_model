# Engineering Task — Refactoring

## Context
`src/services/order_service.py` currently handles financial calculations, stock reservation loops, database record creation, and webhook handling in monolithic methods.
It contains repetitive logic and lacks modular sub-functions.

## Requirements
1. Refactor `src/services/order_service.py` to improve readability, modularity, and maintainability.
2. Extract helper methods for calculation, reservation validation, and order record building.
3. Preserve all existing public method signatures and API behavior exactly (`create_order`, `handle_payment_webhook`).
4. Ensure all existing tests continue to pass without modification.
