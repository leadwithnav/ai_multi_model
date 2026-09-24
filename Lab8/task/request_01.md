# Engineering Task — Inventory Concurrency Incident INC-9204

## Symptom Report
Production incident INC-9204:
Under high traffic flash sales, customer orders are overcommitted.
Multiple purchase requests for the same SKU succeed even when remaining inventory stock is insufficient.

## Requirements
1. Inspect `src/services/inventory_service.py`.
2. Implement `InventoryService.reserve_stock` to check stock availability and update inventory accordingly.
3. Ensure stock never drops below 0 and over-reservation is strictly prevented.
4. Ensure `reserve_stock` returns `True` if reservation succeeded, and `False` if stock was insufficient.
5. Preserve existing function signature (`async def reserve_stock(session: AsyncSession, sku: str, quantity: int) -> bool:`) and existing interfaces.
