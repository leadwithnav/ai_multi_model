import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import CreateOrderRequest, OrderItem, OrderStatus
from src.services.order_service import OrderService
from src.services.inventory_service import InventoryService
from src.database import OrderRecord

@pytest.mark.asyncio
async def test_multi_item_partial_reservation_rollback(db_session: AsyncSession):
    """
    Verifies fix for INC-8821:
    When Item A has sufficient stock but Item B fails reservation,
    Item A's stock MUST be restored/rolled back, leaving it at 10.
    """
    await InventoryService.set_stock(db_session, "ITEM_L3_AVAIL_A", 10)
    await InventoryService.set_stock(db_session, "ITEM_L3_UNAVAIL_B", 0)

    req = CreateOrderRequest(
        customer_id="cust_l3_debug_8821",
        items=[
            OrderItem(sku="ITEM_L3_AVAIL_A", quantity=4, unit_price=20.0),
            OrderItem(sku="ITEM_L3_UNAVAIL_B", quantity=1, unit_price=15.0),
        ]
    )

    service = OrderService()
    with pytest.raises(ValueError, match="Insufficient stock"):
        await service.create_order(db_session, req)

    remaining_a = await InventoryService.get_stock(db_session, "ITEM_L3_AVAIL_A")
    assert remaining_a == 10, f"Stock leaked! Expected 10, but got {remaining_a}"

@pytest.mark.asyncio
async def test_payment_failure_restores_inventory(db_session: AsyncSession):
    """
    Verifies fix for INC-8821:
    When payment fails via webhook (DECLINED), reserved inventory stock
    for the order MUST be restored to original level.
    """
    await InventoryService.set_stock(db_session, "ITEM_L3_PAY_FAIL", 20)

    req = CreateOrderRequest(
        customer_id="cust_l3_pay_fail",
        items=[OrderItem(sku="ITEM_L3_PAY_FAIL", quantity=5, unit_price=30.0)]
    )

    service = OrderService()
    order = await service.create_order(db_session, req)
    
    # Stock after order creation should be 15
    stock_after_create = await InventoryService.get_stock(db_session, "ITEM_L3_PAY_FAIL")
    assert stock_after_create == 15

    # Trigger payment failure webhook
    await service.handle_payment_webhook(db_session, order.id, "DECLINED")

    # Stock MUST be restored back to 20 or order status marked FAILED with stock restored
    stock_after_failure = await InventoryService.get_stock(db_session, "ITEM_L3_PAY_FAIL")
    assert stock_after_failure == 20, f"Inventory stock not restored on payment failure! Got {stock_after_failure}"
