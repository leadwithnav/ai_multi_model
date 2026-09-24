import pytest
import httpx

from order_flow_service.src.services.payment_gateway import PaymentGatewayClient


@pytest.mark.asyncio
async def test_payment_retry_is_bounded(monkeypatch):

    attempts = 0

    async def always_fail(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        raise httpx.RequestError("Payment provider unavailable")

    # Prevent a real HTTP call.
    monkeypatch.setattr(
        httpx.AsyncClient,
        "post",
        always_fail,
    )

    gateway = PaymentGatewayClient()

    # The gateway must eventually stop retrying
    # and report failure.
    with pytest.raises(Exception):
        await gateway.charge(
            order_id="ORDER-101",
            amount=100.00,
            idempotency_key="test-key",
        )

    # It must retry, but retries must be bounded.
    assert attempts >= 1
    assert attempts <= 5