import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from order_flow_service.src.database import AsyncSessionLocal
from order_flow_service.src.services.inventory_service import InventoryService


@pytest.mark.asyncio
async def test_sequential_reserve_stock(db_session: AsyncSession):
    """
    Verifies basic sequential reservation and out-of-stock handling.
    """
    sku = "SKU_SEQ_L8"
    await InventoryService.set_stock(db_session, sku, 3)

    res1 = await InventoryService.reserve_stock(db_session, sku, 2)
    assert res1 is True, "Expected reservation of 2 items from stock of 3 to succeed"

    stock_mid = await InventoryService.get_stock(db_session, sku)
    assert stock_mid == 1, f"Expected remaining stock 1, got {stock_mid}"

    res2 = await InventoryService.reserve_stock(db_session, sku, 2)
    assert res2 is False, "Expected reservation of 2 items from remaining stock of 1 to fail"

    stock_end = await InventoryService.get_stock(db_session, sku)
    assert stock_end == 1, f"Expected remaining stock 1 after failed reservation, got {stock_end}"


@pytest.mark.asyncio
async def test_concurrent_reserve_stock():
    """
    Verifies fix for INC-9204:
    Under 15 concurrent reservation attempts for stock=5,
    EXACTLY 5 attempts must succeed, EXACTLY 10 attempts must fail,
    and final stock MUST be exactly 0 (no stock overcommitment or negative stock).
    """
    sku = "SKU_CONCUR_L8"

    # Setup initial stock of 5
    async with AsyncSessionLocal() as setup_session:
        await InventoryService.set_stock(setup_session, sku, 5)

    async def single_reservation_worker():
        async with AsyncSessionLocal() as session:
            try:
                res = await InventoryService.reserve_stock(session, sku, 1)
                return res
            except Exception as exc:
                return False

    # Execute 15 concurrent reservation attempts
    tasks = [single_reservation_worker() for _ in range(15)]
    results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r is True)
    fail_count = sum(1 for r in results if r is False)

    # Check final stock in DB
    async with AsyncSessionLocal() as verify_session:
        final_stock = await InventoryService.get_stock(verify_session, sku)

    assert success_count == 5, f"Race condition detected! Expected 5 successful reservations, got {success_count}"
    assert fail_count == 10, f"Expected 10 failed reservations, got {fail_count}"
    assert final_stock == 0, f"Inventory overcommitted! Expected final stock 0, got {final_stock}"
