import os
from pydantic import BaseModel

class Settings(BaseModel):
    app_name: str = "OrderFlowEngine"
    db_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    payment_api_url: str = os.getenv("PAYMENT_API_URL", "https://api.mockpayment.internal/v1")
    payment_api_key: str = os.getenv("PAYMENT_API_KEY", "test-secret-key-123")
    max_retries: int = 3

settings = Settings()