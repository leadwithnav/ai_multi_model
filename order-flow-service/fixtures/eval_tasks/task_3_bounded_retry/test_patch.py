import pytest
import httpx
from src.services.payment_gateway import PaymentGatewayClient
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_eval_payment_retries_exhausted():
    """Verifies that failing payment calls do not loop indefinitely and fail after max_retries."""
    client = PaymentGatewayClient()
    
    # Mock httpx.AsyncClient.post to continuously return a 500 error
    mock_resp = httpx.Response(status_code=500, request=httpx.Request("POST", "http://test"))
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        
        with pytest.raises(RuntimeError, match="Payment gateway retries exhausted"):
            await client.charge(order_id="ord_fail", amount=100.0, idempotency_key="key_1")
        
        # Max retries is set to 3 in settings
        assert mock_post.call_count == 3