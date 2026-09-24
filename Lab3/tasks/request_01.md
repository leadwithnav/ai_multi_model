# Engineering Task — Incident INC-8821

## Symptom Report
Production incident INC-8821:
When payment processing fails or payment webhook receives status "FAILED", customer inventory stock remains reserved in `InventoryRecord` instead of being restored.
Additionally, if multi-item stock reservation fails halfway through in `create_order`, previously reserved items in the same request are not restored.

## Requirements
1. Investigate `src/services/order_service.py` (and `handle_payment_webhook`).
2. Identify the root cause of the stock leakage when payment fails or when partial order reservation fails.
3. Fix the defect so that inventory stock is properly released back when payment status is FAILED or when order reservation fails.
4. Preserve existing interfaces and avoid breaking unrelated functionality.
