from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class OrderItem(BaseModel):
    sku: str
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., ge=0.0)

class CreateOrderRequest(BaseModel):
    customer_id: str
    items: List[OrderItem]
    currency: str = "USD"
    # Defect #1: Schema mismatch - metadata is typed as dict, but parser expects JSON string in tests
    metadata: Optional[dict] = None

class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    total_amount: float
    status: OrderStatus
    created_at: datetime
    metadata: Optional[dict] = None

class PaymentWebhookPayload(BaseModel):
    transaction_id: str
    order_id: str
    amount: float
    status: str