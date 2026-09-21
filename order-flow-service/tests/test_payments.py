import pytest
from src.services.payment_gateway import PaymentGatewayClient

def test_timing_safe_webhook_verification():
    """Exposes Defect #5: insecure direct string check."""
    client = PaymentGatewayClient()
    payload = b'{"order_id": "123", "status": "SUCCESS"}'
    valid_sig = "sig_" + str(len(payload))
    assert client.verify_webhook_signature(valid_sig, payload) is True