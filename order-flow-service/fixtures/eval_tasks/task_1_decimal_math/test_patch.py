import pytest
from src.services.order_service import OrderService
from src.services.inventory_service import InventoryService
from src.models import CreateOrderRequest, OrderItem

@pytest.mark.asyncio
async def test_eval_float_precision_edge_cases(db_session):
    """Verifies that fractional cents aggregate without floating point drift."""
    await InventoryService.set_stock(db_session, "PENNY_SKU_1", 100)
    await InventoryService.set_stock(db_session, "PENNY_SKU_2", 100)
    
    req = CreateOrderRequest(
        customer_id="cust_precision_test",
        items=[
            OrderItem(sku="PENNY_SKU_1", quantity=3, unit_price=0.10),
            OrderItem(sku="PENNY_SKU_2", quantity=1, unit_price=0.20),
        ]
    )
    service = OrderService()
    order = await service.create_order(db_session, req)
    
    # 3 * 0.10 + 0.20 must strictly equal 0.5, not 0.5000000000000001
    assert order.total_amount == 0.50
    assert f"{order.total_amount:.2f}" == "0.50"