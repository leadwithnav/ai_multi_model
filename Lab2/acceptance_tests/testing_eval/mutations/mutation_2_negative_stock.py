import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import InventoryRecord

class InventoryService:
    """MUTANT 2: Negative Stock Bug (allows reserving more stock than available)."""
    @staticmethod
    async def set_stock(session: AsyncSession, sku: str, stock: int):
        record = await session.get(InventoryRecord, sku)
        if not record:
            record = InventoryRecord(sku=sku, stock=stock)
            session.add(record)
        else:
            record.stock = stock
        await session.commit()

    @staticmethod
    async def reserve_stock(session: AsyncSession, sku: str, quantity: int) -> bool:
        result = await session.execute(select(InventoryRecord).where(InventoryRecord.sku == sku))
        item = result.scalar_one_or_none()
        if not item:
            return False
        # DEFECT MUTATION: Fails to check if item.stock >= quantity, allowing negative stock!
        item.stock -= quantity
        await session.commit()
        return True

    @staticmethod
    async def get_stock(session: AsyncSession, sku: str) -> int:
        item = await session.get(InventoryRecord, sku)
        return item.stock if item else 0
