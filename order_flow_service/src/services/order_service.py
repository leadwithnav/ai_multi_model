import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import CreateOrderRequest, OrderStatus
from src.database import OrderRecord
from src.services.inventory_service import InventoryService
from src.services.payment_gateway import PaymentGatewayClient

class OrderService:
    def __init__(self):
        self.payment_client = PaymentGatewayClient()

    async def create_order(self, session: AsyncSession, request: CreateOrderRequest) -> OrderRecord:
        total_amount = sum(item.quantity * item.unit_price for item in request.items)

        # Reserve inventory for all items
        for item in request.items:
            reserved = await InventoryService.reserve_stock(session, item.sku, item.quantity)
            if not reserved:
                raise ValueError(f"Insufficient stock for SKU: {item.sku}")

        order_id = str(uuid.uuid4())
        record = OrderRecord(
            id=order_id,
            customer_id=request.customer_id,
            total_amount=total_amount,
            status=OrderStatus.PENDING.value
        )
        session.add(record)
        await session.commit()
        return record

    async def handle_payment_webhook(self, session: AsyncSession, order_id: str, payment_status: str):
        order = await session.get(OrderRecord, order_id)
        if not order:
            return

        if payment_status == "SUCCESS":
            order.status = OrderStatus.PAID.value
        else:
            order.status = OrderStatus.FAILED.value
        
        await session.commit()