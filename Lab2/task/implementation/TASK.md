# Task Requirements: Order Cancellation & Inventory Stock Restoration

Implement order cancellation and inventory stock restoration functionality in the `order_flow_service` repository.

## Components Involved
- `src/services/order_service.py`
- `src/services/inventory_service.py`
- `src/main.py`

## Business Requirements

1. **Cancel Order Logic**:
   - Implement an asynchronous method `cancel_order(session: AsyncSession, order_id: str)` in `OrderService`.
   - When an order is cancelled:
     - The order status must transition to `CANCELLED`.
     - Reserved inventory stock for each item in the order must be restored to `InventoryService`.

2. **Idempotency & Invalid State Protection**:
   - If an order is already in `CANCELLED` or `FAILED` status, attempting to cancel it must raise a `ValueError("Order cannot be cancelled in current state")` and must NOT restore stock again.
   - If the `order_id` does not exist in the database, raise `ValueError("Order not found")`.

3. **API Endpoint**:
   - Expose a `POST /orders/{order_id}/cancel` endpoint in `src/main.py`.
   - On success, return status code `200 OK` with response:
     ```json
     {"order_id": "<order_id>", "status": "CANCELLED", "message": "Order cancelled successfully"}
     ```
   - On `ValueError`, return status code `400 Bad Request` with the error message in the detail response.

4. **Constraints**:
   - Preserve existing public function signatures and database models.
   - Maintain atomic database transaction integrity.
   - Do not modify unrelated components.
