import pytest
from src.services.order_service import OrderService
from src.services.inventory_service import InventoryService
from src.models import CreateOrderRequest, OrderItem

@pytest.mark.asyncio
async def test_partial_reservation_rollback(db_session):
    """Exposes Defect #7: partial allocation leak."""
    await InventoryService.set_stock(db_session, "ITEM_A", 10)
    await InventoryService.set_stock(db_session, "ITEM_B", 0)  # out of stock

    req = CreateOrderRequest(
        customer_id="cust_999",
        items=[
            OrderItem(sku="ITEM_A", quantity=5, unit_price=20.0),
            OrderItem(sku="ITEM_B", quantity=2, unit_price=15.0),
        ]
    )

    service = OrderService()
    with pytest.raises(ValueError, match="Insufficient stock"):
        await service.create_order(db_session, req)
    remaining_a = await InventoryService.get_stock(db_session, "ITEM_A")
    assert remaining_a == 10, f"Leaked allocation! Expected 10, got {remaining_a}"

@pytest.mark.asyncio
async def test_float_precision_order_total(db_session):
    """Exposes Defect #6: floating point errors."""
    await InventoryService.set_stock(db_session, "CANDY", 100)
    req = CreateOrderRequest(
        customer_id="cust_101",
        items=[
            OrderItem(sku="CANDY", quantity=3, unit_price=0.1),
            OrderItem(sku="CANDY", quantity=1, unit_price=0.2),
        ]
    )
    service = OrderService()
    order = await service.create_order(db_session, req)
    assert order.total_amount == 0.5, f"Precision drift detected: {order.total_amount}"