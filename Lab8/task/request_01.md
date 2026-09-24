# Engineering Task — Implement Inventory Stock Reservation

## Feature Request
We need to implement stock reservation logic in the `order_flow_service`.

When a customer initiates an order, `InventoryService.reserve_stock` should verify whether there is enough stock for the requested SKU. If stock is available, decrement the inventory quantity and return `True`. If stock is insufficient, return `False`.

## Requirements
1. Inspect `src/services/inventory_service.py`.
2. Implement `InventoryService.reserve_stock` to check stock availability and decrement stock accordingly.
3. Ensure `reserve_stock` returns `True` if reservation succeeded, and `False` if stock was insufficient.
4. Preserve function signature (`async def reserve_stock(session: AsyncSession, sku: str, quantity: int) -> bool:`).
