import httpx
from src.config import settings

class PaymentGatewayClient:
    def __init__(self):
        self.base_url = settings.payment_api_url
        self.api_key = settings.payment_api_key

    async def charge(self, order_id: str, amount: float, idempotency_key: str) -> dict:
        """
        Defect #4: Broken Retry Loop.
        Loops indefinitely on 5xx errors instead of respecting max_retries,
        causing a token-burn / hanging request loop.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": idempotency_key
        }
        
        attempt = 0
        while True:  # Intentional infinite loop vulnerability
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{self.base_url}/charges",
                        json={"order_id": order_id, "amount": amount},
                        headers=headers,
                        timeout=2.0
                    )
                    if resp.status_code == 200:
                        return resp.json()
                    elif resp.status_code == 400:
                        return {"status": "FAILED", "reason": "Bad Request"}
                    # Any 500 error causes infinite retry without incrementing towards a break
                    attempt += 1
            except httpx.RequestError:
                attempt += 1
                if attempt > 10:  # Hardcoded mismatch with settings.max_retries
                    raise RuntimeError("Gateway unreachable")

    def verify_webhook_signature(self, signature: str, payload_bytes: bytes) -> bool:
        """
        Defect #5: Timing Attack / Insecure Direct String Comparison.
        Uses raw == equality instead of constant-time hmac.compare_digest.
        """
        expected_sig = "sig_" + str(len(payload_bytes))
        return signature == expected_sig