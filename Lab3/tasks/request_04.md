# Engineering Task — Feature Implementation

## Context
The `OrderFlowService` currently supports order creation (`POST /orders`) and payment webhook processing (`POST /webhooks/payment`).
However, customers need the ability to cancel an existing order before payment is finalized and restore any reserved inventory.

## Requirements
1. Implement `cancel_order(session: AsyncSession, order_id: str) -> OrderRecord` in `src/services/order_service.py`:
   - Fetch order record by `order_id`. If order does not exist, raise `ValueError("Order not found")`.
   - If order status is not `PENDING`, raise `ValueError("Only PENDING orders can be cancelled")`.
   - Set order status to `CANCELLED`.
   - For each item in the order request metadata or associated inventory reservations, restore the reserved stock in `InventoryRecord` using `InventoryService.set_stock` or by incrementing stock.
   - Commit session and return updated order record.

2. Expose `POST /orders/{order_id}/cancel` endpoint in `src/main.py`:
   - Returns status 200 OK with `OrderResponse` on success.
   - Returns status 400 Bad Request if order is not found or cannot be cancelled.

3. Preserve all existing API contracts and ensure zero regressions.
