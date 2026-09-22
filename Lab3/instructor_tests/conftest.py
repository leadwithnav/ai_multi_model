import sys
from pathlib import Path
import pytest_asyncio

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOT = WORKSPACE_ROOT / "order_flow_service"

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from src.database import init_db, AsyncSessionLocal

@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    await init_db()
    yield

@pytest_asyncio.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session
