import pytest
import asyncio
from src.services.inventory_service import InventoryService

@pytest.mark.asyncio
async def test_get_nonexistent_stock_raises_proper_error(db_session):
    """Exposes Defect #3: unhandled NoneType access."""
    with pytest.raises(ValueError):
        # Should raise a domain ValueError or return 0, but currently crashes with AttributeError
        stock = await InventoryService.get_stock(db_session, "NON_EXISTENT_SKU")
        assert stock == 0

@pytest.mark.asyncio
async def test_concurrency_race_condition(db_session):
    """Exposes Defect #2: overselling stock due to lack of concurrency locks."""
    sku = "FLASH_SALE_ITEM"
    initial_stock = 1
    await InventoryService.set_stock(db_session, sku, initial_stock)

    # 5 concurrent workers attempting to reserve the exact same 1 unit
    tasks = [InventoryService.reserve_stock(db_session, sku, 1) for _ in range(5)]
    results = await asyncio.gather(*tasks)

    successful_reservations = sum(1 for r in results if r is True)
    assert successful_reservations == 1, (
        f"Race condition violated! Allocated {successful_reservations} units from a stock of 1."
    )