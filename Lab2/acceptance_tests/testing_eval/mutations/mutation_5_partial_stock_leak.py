import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import InventoryRecord

class InventoryService:
    """MUTANT 5: Stock Leak Bug (always deducts stock even if reservation checks fail)."""
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
        # DEFECT MUTATION: Always deducts quantity regardless of whether stock < quantity
        item.stock -= quantity
        await session.commit()
        return item.stock >= 0

    @staticmethod
    async def get_stock(session: AsyncSession, sku: str) -> int:
        item = await session.get(InventoryRecord, sku)
        return item.stock if item else 0
