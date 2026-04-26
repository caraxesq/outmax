from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings
from app.db.models import Base
from app.db.session import create_sessionmaker


@pytest.fixture
def settings(tmp_path):
    return Settings(
        BOT_TOKEN="token",
        ADMIN_IDS="1,2",
        API_ID=123,
        API_HASH="hash",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        SESSIONS_DIR=tmp_path / "sessions",
        LOG_DIR=tmp_path / "logs",
        MIN_SEND_DELAY=0,
        MAX_SEND_DELAY=0,
        COOLDOWN_AFTER_MESSAGES=2,
        COOLDOWN_SECONDS=10,
        DAILY_ACCOUNT_LIMIT=5,
        WORKER_IDLE_SECONDS=0,
    )


@pytest.fixture
async def sessionmaker(settings):
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = create_sessionmaker(engine=engine)
    yield maker
    await engine.dispose()
