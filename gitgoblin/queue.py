"""The Postgres-backed queue. Every function takes the caller's session, so the caller
decides the transaction boundary (e.g. record delivery + enqueue commit together).

Producer side: record_delivery, enqueue (webhook).
Consumer side: claim_job, extend_lease, complete_job, fail_job (worker).
"""

import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from gitgoblin.db.models import Job, WebhookDelivery
from gitgoblin.jobs import JobSpec

RETRY_BASE_SECONDS = 30
RETRY_CAP_SECONDS = 15 * 60


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



@dataclass(frozen=True)
class ClaimedJob:
    """A job a worker currently holds. `attempts` doubles as a fencing token: every
    write back to the row requires it to still match, so a worker whose lease expired
    (and whose job was re-claimed, bumping attempts) cannot overwrite the new owner."""

    id: int
    kind: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int


def retry_delay(attempts: int) -> float:
    """Seconds to wait after the given failed attempt: 30s, 60s, 120s, ... capped at
    15 min, plus up to 10% random jitter so many failing jobs don't retry in lockstep."""
    delay = min(RETRY_BASE_SECONDS * 2 ** (attempts - 1), RETRY_CAP_SECONDS)
    return delay * (1 + random.uniform(0, 0.1))


async def claim_job(session: AsyncSession, lease_seconds: float) -> ClaimedJob | None:
    """Atomically take the next runnable job, or None if there is nothing to do.

    UPDATE jobs SET status='running', attempts=attempts+1, locked_until=now()+lease
    WHERE id = (SELECT id FROM jobs
                WHERE (status='queued'  AND run_after <= now())      -- ready
                   OR (status='running' AND locked_until < now())    -- owner died
                ORDER BY run_after LIMIT 1
                FOR UPDATE SKIP LOCKED)                              -- skip rows another
    RETURNING ...                                                    -- worker is claiming
    """
    now = func.now()
    next_id = (
        select(Job.id)
        .where(
            or_(
                and_(Job.status == "queued", Job.run_after <= now),
                and_(Job.status == "running", Job.locked_until < now),
            )
        )
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    stmt = (
        update(Job)
        .where(Job.id == next_id)
        .values(status="running", attempts=Job.attempts + 1, locked_until=now + timedelta(seconds=lease_seconds))
        .returning(Job.id, Job.kind, Job.payload, Job.attempts, Job.max_attempts)
        .execution_options(synchronize_session=False)
    )
    row = (await session.execute(stmt)).one_or_none()
    return ClaimedJob(*row) if row else None


def _owned(job: ClaimedJob):
    """WHERE clause: the row is still running under this exact claim."""
    return and_(Job.id == job.id, Job.status == "running", Job.attempts == job.attempts)


async def _update_owned(session: AsyncSession, job: ClaimedJob, **values: Any) -> bool:
    stmt = update(Job).where(_owned(job)).values(**values).execution_options(synchronize_session=False)
    result = await session.execute(stmt)
    return result.rowcount == 1  # pyright: ignore[reportAttributeAccessIssue]


async def extend_lease(session: AsyncSession, job: ClaimedJob, lease_seconds: float) -> bool:
    """Heartbeat: push the lease forward. False means we no longer own the job."""
    return await _update_owned(session, job, locked_until=func.now() + timedelta(seconds=lease_seconds))


async def complete_job(session: AsyncSession, job: ClaimedJob) -> bool:
    return await _update_owned(session, job, status="done", locked_until=None, last_error=None)


async def fail_job(session: AsyncSession, job: ClaimedJob, error: str, *, permanent: bool = False) -> str:
    """Record a failure. Returns the new status: 'queued' (will retry), 'failed'
    (gave up), or 'lost' (another worker owns the job now; nothing written)."""
    if permanent or job.attempts >= job.max_attempts:
        status, values = "failed", {}
    else:
        status, values = "queued", {"run_after": func.now() + timedelta(seconds=retry_delay(job.attempts))}
    written = await _update_owned(session, job, status=status, locked_until=None, last_error=error, **values)
    return status if written else "lost"