import pytest
import asyncio
from src.services.inventory_service import InventoryService
from src.database import AsyncSessionLocal

@pytest.mark.asyncio
async def test_eval_atomic_concurrency():
    """Verifies that 10 concurrent requests for a single unit strictly allow only 1 reservation."""
    sku = "HIGH_CONTENTION_ITEM"
    
    async with AsyncSessionLocal() as session:
        await InventoryService.set_stock(session, sku, 1)

    async def worker():
        async with AsyncSessionLocal() as session:
            return await InventoryService.reserve_stock(session, sku, 1)

    # 10 workers concurrently contending for 1 unit
    results = await asyncio.gather(*(worker() for _ in range(10)))
    successes = sum(1 for r in results if r is True)
    
    assert successes == 1, f"Over-allocation detected! {successes} orders reserved stock of 1."