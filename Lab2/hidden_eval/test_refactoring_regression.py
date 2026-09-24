import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from order_flow_service.src.models import CreateOrderRequest, OrderItem, OrderStatus
from order_flow_service.src.services.order_service import OrderService
from order_flow_service.src.services.inventory_service import InventoryService
from order_flow_service.src.database import OrderRecord

@pytest.mark.asyncio
async def test_refactoring_create_order_single_item(db_session: AsyncSession):
    """Verify create_order works correctly for single item after refactoring."""
    await InventoryService.set_stock(db_session, "SKU_REF_1", 20)
    service = OrderService()
    req = CreateOrderRequest(
        customer_id="cust_ref_1",
        items=[OrderItem(sku="SKU_REF_1", quantity=5, unit_price=10.0)]
    )
    order = await service.create_order(db_session, req)
    assert isinstance(order, OrderRecord)
    assert order.customer_id == "cust_ref_1"
    assert order.total_amount == 50.0
    assert order.status == OrderStatus.PENDING.value or order.status == "PENDING"


@pytest.mark.asyncio
async def test_refactoring_create_order_insufficient_stock_error(db_session: AsyncSession):
    """Verify create_order raises ValueError when stock is insufficient."""
    await InventoryService.set_stock(db_session, "SKU_REF_2", 2)
    service = OrderService()
    req = CreateOrderRequest(
        customer_id="cust_ref_2",
        items=[OrderItem(sku="SKU_REF_2", quantity=10, unit_price=15.0)]
    )
    with pytest.raises(ValueError, match="Insufficient stock"):
        await service.create_order(db_session, req)


@pytest.mark.asyncio
async def test_refactoring_handle_payment_webhook_success(db_session: AsyncSession):
    """Verify handle_payment_webhook updates order status to PAID on SUCCESS."""
    await InventoryService.set_stock(db_session, "SKU_REF_3", 10)
    service = OrderService()
    req = CreateOrderRequest(
        customer_id="cust_ref_3",
        items=[OrderItem(sku="SKU_REF_3", quantity=1, unit_price=100.0)]
    )
    order = await service.create_order(db_session, req)
    await service.handle_payment_webhook(db_session, order.id, "SUCCESS")

    updated = await db_session.get(OrderRecord, order.id)
    assert updated.status == OrderStatus.PAID.value or updated.status == "PAID"


@pytest.mark.asyncio
async def test_refactoring_handle_payment_webhook_failed(db_session: AsyncSession):
    """Verify handle_payment_webhook updates order status to FAILED on payment failure."""
    await InventoryService.set_stock(db_session, "SKU_REF_4", 10)
    service = OrderService()
    req = CreateOrderRequest(
        customer_id="cust_ref_4",
        items=[OrderItem(sku="SKU_REF_4", quantity=1, unit_price=100.0)]
    )
    order = await service.create_order(db_session, req)
    await service.handle_payment_webhook(db_session, order.id, "DECLINED")

    updated = await db_session.get(OrderRecord, order.id)
    assert updated.status == OrderStatus.FAILED.value or updated.status == "FAILED"
