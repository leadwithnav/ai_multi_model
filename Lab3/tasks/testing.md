# Engineering Task — Automated Test Generation

## Context
`InventoryService` in `src/services/inventory_service.py` lacks comprehensive automated unit test coverage for edge cases.

## Requirements
1. Generate a unit test suite for `InventoryService` in `order_flow_service/tests/test_inventory_generated.py`.
2. Tests must cover:
   - Setting initial stock for new and existing SKUs (`set_stock`)
   - Stock reservation success and failure due to insufficient quantity (`reserve_stock`)
   - Fetching stock for existing and missing SKUs (`get_stock`)
3. Tests must be executable with `pytest tests/test_inventory_generated.py` from `order_flow_service`.
4. Do not alter production code behavior to make tests pass.
