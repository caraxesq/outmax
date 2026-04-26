from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    settings = settings or get_settings()
    return create_async_engine(settings.database_url, echo=False, future=True)


def create_sessionmaker(engine: AsyncEngine | None = None, settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    engine = engine or create_engine(settings)
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
