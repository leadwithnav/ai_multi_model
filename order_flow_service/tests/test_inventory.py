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