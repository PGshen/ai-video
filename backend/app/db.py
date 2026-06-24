from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine
from typing import AsyncGenerator
from app.config import settings


class Base(DeclarativeBase):
    pass


# Async engine for FastAPI
async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# Sync engine for Workers
sync_engine = create_engine(settings.DATABASE_SYNC_URL, echo=False)
SyncSessionLocal = sessionmaker(sync_engine)


def get_sync_session():
    return SyncSessionLocal()
