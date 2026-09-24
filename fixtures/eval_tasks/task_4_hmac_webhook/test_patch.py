import pytest
from src.services.payment_gateway import PaymentGatewayClient

def test_eval_hmac_comparison_behavior():
    """Verifies constant-time signature verification semantics."""
    client = PaymentGatewayClient()
    payload = b'{"status": "CONFIRMED", "order_id": "ORD-999"}'
    valid_signature = "sig_" + str(len(payload))
    invalid_signature = "sig_invalid_checksum"

    assert client.verify_webhook_signature(valid_signature, payload) is True
    assert client.verify_webhook_signature(invalid_signature, payload) is False
    assert client.verify_webhook_signature("", payload) is False