"""Queue guarantees: one owner per job, crashed owners recovered, stale owners fenced
out, failures backed off and eventually given up on."""

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gitgoblin.db.models import Job
from gitgoblin.jobs import JobKind, JobSpec
from gitgoblin.queue import RETRY_CAP_SECONDS, claim_job, complete_job, enqueue, fail_job, retry_delay

SPEC = JobSpec(JobKind.REVIEW_PULL_REQUEST, {"installation_id": 1, "owner": "o", "repo": "r", "number": 7})


async def _enqueue(sm: async_sessionmaker[AsyncSession], count: int = 1) -> list[int]:
    async with sm() as session, session.begin():
        return [await enqueue(session, SPEC) for _ in range(count)]


async def _job(sm: async_sessionmaker[AsyncSession], job_id: int) -> Job:
    async with sm() as session:
        return (await session.scalars(select(Job).where(Job.id == job_id))).one()


async def test_concurrent_claims_never_share_a_job(sessionmaker):
    """Three workers claim at once while two jobs exist: each job goes to exactly one
    worker, and the third gets nothing instead of blocking."""
    first_id, second_id = await _enqueue(sessionmaker, 2)
    sessions = [sessionmaker() for _ in range(3)]
    try:
        for session in sessions:
            await session.begin()  # all three transactions are open at the same time
            # Without SKIP LOCKED a claim would wait on another's row lock; fail fast instead.
            await session.execute(text("SET LOCAL lock_timeout = '2s'"))
        claims = [await claim_job(session, lease_seconds=60) for session in sessions]
    finally:
        for session in sessions:
            await session.close()  # rolls back; the claims were only needed in memory

    assert [c.id if c else None for c in claims] == [first_id, second_id, None]


async def test_expired_lease_is_reclaimed_and_old_owner_is_fenced_out(sessionmaker):
    [job_id] = await _enqueue(sessionmaker)
    async with sessionmaker() as session, session.begin():
        crashed_owner = await claim_job(session, lease_seconds=0)  # lease already over

    async with sessionmaker() as session, session.begin():
        new_owner = await claim_job(session, lease_seconds=60)
    assert new_owner is not None
    assert (new_owner.id, new_owner.attempts) == (job_id, 2)

    async with sessionmaker() as session, session.begin():
        assert not await complete_job(session, crashed_owner)  # stale write rejected
        assert await complete_job(session, new_owner)
    assert (await _job(sessionmaker, job_id)).status == "done"


async def test_failures_back_off_then_give_up(sessionmaker):
    [job_id] = await _enqueue(sessionmaker)
    async with sessionmaker() as session, session.begin():
        await session.execute(update(Job).where(Job.id == job_id).values(max_attempts=2))

    async with sessionmaker() as session, session.begin():
        attempt_1 = await claim_job(session, lease_seconds=60)
        assert await fail_job(session, attempt_1, "boom 1") == "queued"
    async with sessionmaker() as session, session.begin():
        assert await claim_job(session, lease_seconds=60) is None  # still backing off

    async with sessionmaker() as session, session.begin():
        await session.execute(update(Job).where(Job.id == job_id).values(run_after=Job.created_at))
    async with sessionmaker() as session, session.begin():
        attempt_2 = await claim_job(session, lease_seconds=60)
        assert await fail_job(session, attempt_2, "boom 2") == "failed"

    job = await _job(sessionmaker, job_id)
    assert (job.status, job.attempts, job.last_error) == ("failed", 2, "boom 2")


def test_retry_delay_grows_exponentially_and_is_capped():
    assert 30 <= retry_delay(1) <= 33
    assert 120 <= retry_delay(3) <= 132
    assert RETRY_CAP_SECONDS <= retry_delay(20) <= RETRY_CAP_SECONDS * 1.1
