import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import InventoryRecord

class InventoryService:
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
        """
        Defect #2 (Race Condition / TOCTOU): Reads stock, awaits context switch,
        then writes without atomic row locking or database constraint checks.
        """
        result = await session.execute(select(InventoryRecord).where(InventoryRecord.sku == sku))
        item = result.scalar_one_or_none()

        if not item or item.stock < quantity:
            return False

        # Simulated async I/O switch - exposes the concurrency race
        await asyncio.sleep(0.01)

        item.stock -= quantity
        await session.commit()
        return True

    @staticmethod
    async def get_stock(session: AsyncSession, sku: str) -> int:
        item = await session.get(InventoryRecord, sku)
        # Defect #3: Unhandled AttributeError if item does not exist
        return item.stock