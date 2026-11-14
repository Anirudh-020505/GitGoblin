"""One connection pool per process, and short-lived sessions borrowed from it.

engine        = the pool of open Postgres connections (expensive, create once)
sessionmaker  = a factory that hands out sessions bound to that pool
session       = one unit of work: queries + one commit/rollback, then returned
"""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from gitgoblin.settings import database_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    # pre_ping drops connections Postgres closed while idle (restarts, timeouts).
    return create_async_engine(database_settings().database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: objects stay readable after commit without a new query.
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    async with get_sessionmaker()() as session:
        yield session
