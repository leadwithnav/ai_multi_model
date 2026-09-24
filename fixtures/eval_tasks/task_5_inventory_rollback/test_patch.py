import pytest
from src.services.order_service import OrderService
from src.services.inventory_service import InventoryService
from src.models import CreateOrderRequest, OrderItem

@pytest.mark.asyncio
async def test_eval_compensatory_rollback(db_session):
    """Verifies that all previously allocated items are restored if a later item is out of stock."""
    await InventoryService.set_stock(db_session, "ROLLBACK_SKU_A", 15)
    await InventoryService.set_stock(db_session, "ROLLBACK_SKU_B", 20)
    await InventoryService.set_stock(db_session, "ROLLBACK_SKU_C", 0)  # out of stock

    req = CreateOrderRequest(
        customer_id="cust_failover",
        items=[
            OrderItem(sku="ROLLBACK_SKU_A", quantity=5, unit_price=10.0),
            OrderItem(sku="ROLLBACK_SKU_B", quantity=10, unit_price=2.0),
            OrderItem(sku="ROLLBACK_SKU_C", quantity=1, unit_price=50.0),
        ]
    )
    service = OrderService()
    
    with pytest.raises(ValueError, match="Insufficient stock for SKU: ROLLBACK_SKU_C"):
        await service.create_order(db_session, req)

    # Stock for SKU A and SKU B must be completely restored to their original levels
    stock_a = await InventoryService.get_stock(db_session, "ROLLBACK_SKU_A")
    stock_b = await InventoryService.get_stock(db_session, "ROLLBACK_SKU_B")
    
    assert stock_a == 15, f"Leaked allocation on SKU A! Expected 15, got {stock_a}"
    assert stock_b == 20, f"Leaked allocation on SKU B! Expected 20, got {stock_b}"