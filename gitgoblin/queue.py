"""The Postgres-backed queue. Every function takes the caller's session, so the caller
decides the transaction boundary (e.g. record delivery + enqueue commit together)."""

from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from gitgoblin.db.models import Job, WebhookDelivery
from gitgoblin.jobs import JobSpec


async def record_delivery(
    session: AsyncSession, delivery_id: str, event: str, payload: dict[str, Any]
) -> bool:
    """Store a webhook delivery. Returns False if this delivery id was already stored.

    INSERT ... ON CONFLICT DO NOTHING RETURNING delivery_id
      first time  → returns the id  → True
      redelivery  → returns nothing → False
    Two identical deliveries racing: the second waits on the first's row lock, then
    sees the conflict, so exactly one wins.
    """
    stmt = (
        insert(WebhookDelivery)
        .values(delivery_id=delivery_id, event=event, action=payload.get("action"), payload=payload)
        .on_conflict_do_nothing(index_elements=[WebhookDelivery.delivery_id])
        .returning(WebhookDelivery.delivery_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def enqueue(session: AsyncSession, spec: JobSpec, delivery_id: str | None = None) -> int:
    """Add a queued job and return its id (assigned by Postgres on flush)."""
    job = Job(kind=spec.kind, payload=spec.payload, delivery_id=delivery_id)
    session.add(job)
    await session.flush()
    return job.id
