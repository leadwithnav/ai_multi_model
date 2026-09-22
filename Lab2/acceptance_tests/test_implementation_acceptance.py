import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from order_flow_service.src.main import app
from order_flow_service.src.models import CreateOrderRequest, OrderItem, OrderStatus
from order_flow_service.src.services.order_service import OrderService
from order_flow_service.src.services.inventory_service import InventoryService
from order_flow_service.src.database import OrderRecord

@pytest.mark.asyncio
async def test_cancel_pending_order_restores_stock(db_session: AsyncSession):
    """Verify cancelling a PENDING order transitions status to CANCELLED and restores stock."""
    await InventoryService.set_stock(db_session, "SKU_CANCEL_1", 10)
    
    order_service = OrderService()
    req = CreateOrderRequest(
        customer_id="cust_cancel_1",
        items=[OrderItem(sku="SKU_CANCEL_1", quantity=3, unit_price=25.0)]
    )
    order = await order_service.create_order(db_session, req)
    
    # Stock should now be 7
    remaining_before = await InventoryService.get_stock(db_session, "SKU_CANCEL_1")
    assert remaining_before == 7

    # Cancel order
    cancelled_order = await order_service.cancel_order(db_session, order.id)
    assert cancelled_order.status == OrderStatus.CANCELLED.value or cancelled_order.status == "CANCELLED"

    # Stock should be restored to 10
    remaining_after = await InventoryService.get_stock(db_session, "SKU_CANCEL_1")
    assert remaining_after == 10


@pytest.mark.asyncio
async def test_cancel_already_cancelled_order_raises_error(db_session: AsyncSession):
    """Verify cancelling an already CANCELLED order raises ValueError and prevents double restoration."""
    await InventoryService.set_stock(db_session, "SKU_CANCEL_2", 10)
    
    order_service = OrderService()
    req = CreateOrderRequest(
        customer_id="cust_cancel_2",
        items=[OrderItem(sku="SKU_CANCEL_2", quantity=4, unit_price=10.0)]
    )
    order = await order_service.create_order(db_session, req)
    
    await order_service.cancel_order(db_session, order.id)
    
    # Second cancellation attempt must fail
    with pytest.raises(ValueError):
        await order_service.cancel_order(db_session, order.id)

    # Stock must remain 10 (not 14)
    stock = await InventoryService.get_stock(db_session, "SKU_CANCEL_2")
    assert stock == 10


@pytest.mark.asyncio
async def test_cancel_nonexistent_order_raises_error(db_session: AsyncSession):
    """Verify cancelling a non-existent order_id raises ValueError."""
    order_service = OrderService()
    with pytest.raises(ValueError, match="Order not found"):
        await order_service.cancel_order(db_session, "non_existent_id_999")


@pytest.mark.asyncio
async def test_cancel_order_api_endpoint(db_session: AsyncSession):
    """Verify POST /orders/{order_id}/cancel API endpoint returns 200 OK on success."""
    await InventoryService.set_stock(db_session, "SKU_API_CANCEL", 5)
    order_service = OrderService()
    req = CreateOrderRequest(
        customer_id="cust_api_1",
        items=[OrderItem(sku="SKU_API_CANCEL", quantity=2, unit_price=15.0)]
    )
    order = await order_service.create_order(db_session, req)

    client = TestClient(app)
    response = client.post(f"/orders/{order.id}/cancel")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "CANCELLED"
    assert data.get("order_id") == order.id

    # Verify stock restored
    stock = await InventoryService.get_stock(db_session, "SKU_API_CANCEL")
    assert stock == 5
