"""Tests run against a real Postgres: SKIP LOCKED, leases and ON CONFLICT are database
behaviour, so a fake would prove nothing.

Needs `docker compose up -d postgres`. Uses a separate `gitgoblin_test` database
(created on first run); override with TEST_DATABASE_URL.
"""

import asyncio
import os
from collections.abc import AsyncIterator

import asyncpg
import pytest
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from gitgoblin.db.models import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://gitgoblin:gitgoblin@localhost:5433/gitgoblin_test"
)


async def _create_schema() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin = await asyncpg.connect(
        user=url.username, password=url.password, host=url.host, port=url.port, database="postgres"
    )
    try:
        if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", url.database):
            await admin.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await admin.close()

    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    asyncio.run(_create_schema())


@pytest.fixture
async def sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A session factory on an emptied database. NullPool: no connections shared
    between tests, so each test's open transactions are truly independent."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE jobs, webhook_deliveries RESTART IDENTITY"))
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
