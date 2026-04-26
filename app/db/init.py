from __future__ import annotations

import asyncio

from app.config import get_settings
from app.db.models import Base
from app.db.session import create_engine


async def init_db() -> None:
    settings = get_settings()
    settings.ensure_runtime_dirs()
    engine = create_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
