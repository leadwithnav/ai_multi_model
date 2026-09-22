from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from src.database import init_db, AsyncSessionLocal
from src.models import CreateOrderRequest, OrderResponse, PaymentWebhookPayload
from src.services.order_service import OrderService

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="OrderFlowService", lifespan=lifespan)
order_service = OrderService()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(payload: CreateOrderRequest, db: AsyncSession = Depends(get_db)):
    try:
        order = await order_service.create_order(db, payload)
        return OrderResponse(
            order_id=order.id,
            customer_id=order.customer_id,
            total_amount=order.total_amount,
            status=order.status,
            created_at=order.created_at,
            metadata=payload.metadata
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.post("/webhooks/payment")
async def payment_webhook(payload: PaymentWebhookPayload, db: AsyncSession = Depends(get_db)):
    await order_service.handle_payment_webhook(db, payload.order_id, payload.status)
    return {"status": "acknowledged"}