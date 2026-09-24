# Incident Report: INC-8821 — Inventory Stock Leak Under Multi-Item Order Failures

## Production Symptom
When customers attempt to create an order containing multiple items and one of the items fails stock reservation (due to insufficient inventory), the order creation correctly raises a `ValueError`. However, warehouse audits reveal that stock for the *other* available items in the order was already deducted and never restored. This causes permanent phantom inventory stock leaks in the database.

## Objective
Investigate the issue in `order-flow-service`, identify the root cause, and implement a fix so that when an order creation fails, any inventory stock reserved during that order creation attempt is fully rolled back and restored.

## Constraints
- Preserve existing public function signatures and return types.
- Do not modify unrelated components or database models.
- Ensure all existing and new acceptance tests pass cleanly.
