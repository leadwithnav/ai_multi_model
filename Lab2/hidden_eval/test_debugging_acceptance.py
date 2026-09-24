import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import CreateOrderRequest, OrderItem
from src.services.order_service import OrderService
from src.services.inventory_service import InventoryService

@pytest.mark.asyncio
async def test_multi_item_partial_reservation_rollback(db_session: AsyncSession):
    """
    Verifies fix for INC-8821:
    When Item A has sufficient stock but Item B fails reservation,
    Item A's stock MUST be restored/rolled back, leaving it at 10.
    """
    await InventoryService.set_stock(db_session, "ITEM_AVAILABLE_A", 10)
    await InventoryService.set_stock(db_session, "ITEM_UNAVAILABLE_B", 0)

    req = CreateOrderRequest(
        customer_id="cust_debug_8821",
        items=[
            OrderItem(sku="ITEM_AVAILABLE_A", quantity=4, unit_price=20.0),
            OrderItem(sku="ITEM_UNAVAILABLE_B", quantity=1, unit_price=15.0),
        ]
    )

    service = OrderService()
    with pytest.raises(ValueError, match="Insufficient stock"):
        await service.create_order(db_session, req)

    # ITEM_AVAILABLE_A stock must remain 10 because the entire order transaction failed
    remaining_a = await InventoryService.get_stock(db_session, "ITEM_AVAILABLE_A")
    assert remaining_a == 10, f"Stock leaked! Expected 10, but got {remaining_a}"


@pytest.mark.asyncio
async def test_successful_multi_item_order_deducts_all_stock(db_session: AsyncSession):
    """Verify that successful multi-item order creation still deducts stock for all items."""
    await InventoryService.set_stock(db_session, "ITEM_OK_1", 15)
    await InventoryService.set_stock(db_session, "ITEM_OK_2", 10)

    req = CreateOrderRequest(
        customer_id="cust_debug_ok",
        items=[
            OrderItem(sku="ITEM_OK_1", quantity=5, unit_price=10.0),
            OrderItem(sku="ITEM_OK_2", quantity=3, unit_price=5.0),
        ]
    )

    service = OrderService()
    order = await service.create_order(db_session, req)
    assert order.id is not None

    rem_1 = await InventoryService.get_stock(db_session, "ITEM_OK_1")
    rem_2 = await InventoryService.get_stock(db_session, "ITEM_OK_2")

    assert rem_1 == 10
    assert rem_2 == 7
