import pytest
import asyncio
from src.database import init_db, AsyncSessionLocal

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()
    yield

@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session