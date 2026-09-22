import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import InventoryRecord

class InventoryService:
    """MUTANT 1: Double Reservation Bug (deducts 2x quantity)."""
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
        if not item or item.stock < quantity:
            return False
        # DEFECT MUTATION: Deducts double the requested quantity
        item.stock -= (quantity * 2)
        await session.commit()
        return True

    @staticmethod
    async def get_stock(session: AsyncSession, sku: str) -> int:
        item = await session.get(InventoryRecord, sku)
        return item.stock if item else 0
