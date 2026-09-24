import pytest
import asyncio
from src.services.inventory_service import InventoryService

@pytest.mark.asyncio
async def test_get_nonexistent_stock_raises_proper_error(db_session):
    with pytest.raises(ValueError):
        stock = await InventoryService.get_stock(db_session, "NON_EXISTENT_SKU")
        assert stock == 0