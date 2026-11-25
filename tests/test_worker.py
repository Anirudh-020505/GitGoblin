"""Worker behaviour: success, retry on error, heartbeat keeps long jobs owned, and
graceful shutdown finishes the in-flight job."""

import asyncio

from sqlalchemy import select

from gitgoblin.db.models import Job
from gitgoblin.jobs import JobKind, JobSpec
from gitgoblin.queue import claim_job, enqueue
from gitgoblin.worker import Worker

PAYLOAD = {"installation_id": 1, "owner": "o", "repo": "r", "number": 7}


async def _enqueue(sm) -> int:
    async with sm() as session, session.begin():
        return await enqueue(session, JobSpec(JobKind.REVIEW_PULL_REQUEST, PAYLOAD))


async def _status(sm, job_id: int) -> tuple[str, int]:
    async with sm() as session:
        job = (await session.scalars(select(Job).where(Job.id == job_id))).one()
        return job.status, job.attempts


async def test_handler_success_marks_done_and_error_schedules_retry(sessionmaker):
    seen = []

    async def ok(payload):
        seen.append(payload)

    async def broken(payload):
        raise RuntimeError("model timed out")

    done_id = await _enqueue(sessionmaker)
    assert await Worker(sessionmaker, {JobKind.REVIEW_PULL_REQUEST: ok}).run_once()
    assert seen == [PAYLOAD]
    assert await _status(sessionmaker, done_id) == ("done", 1)

    retry_id = await _enqueue(sessionmaker)
    assert await Worker(sessionmaker, {JobKind.REVIEW_PULL_REQUEST: broken}).run_once()
    assert await _status(sessionmaker, retry_id) == ("queued", 1)
    assert not await Worker(sessionmaker, {}).run_once()  # backing off: nothing claimable


async def test_heartbeat_keeps_a_long_job_owned_past_its_lease(sessionmaker):
    """The job runs 1.5s with a 0.5s lease. Without heartbeats a second worker
    would steal it halfway; with them, nobody else can claim it."""
    job_id = await _enqueue(sessionmaker)
    started = asyncio.Event()

    async def slow(payload):
        started.set()
        await asyncio.sleep(1.5)

    worker = Worker(
        sessionmaker, {JobKind.REVIEW_PULL_REQUEST: slow}, lease_seconds=0.5, heartbeat_seconds=0.1
    )
    run = asyncio.create_task(worker.run_once())
    await started.wait()
    await asyncio.sleep(1.0)  # well past the original 0.5s lease
    async with sessionmaker() as session, session.begin():
        assert await claim_job(session, lease_seconds=60) is None

    await run
    assert await _status(sessionmaker, job_id) == ("done", 1)


async def test_shutdown_finishes_the_in_flight_job(sessionmaker):
    job_id = await _enqueue(sessionmaker)
    started, release = asyncio.Event(), asyncio.Event()

    async def gated(payload):
        started.set()
        await release.wait()

    stop = asyncio.Event()
    worker = Worker(sessionmaker, {JobKind.REVIEW_PULL_REQUEST: gated}, poll_seconds=0.05)
    running = asyncio.create_task(worker.run(1, stop))
    await started.wait()
    stop.set()  # SIGTERM arrives mid-job
    release.set()
    await asyncio.wait_for(running, timeout=5)

    assert await _status(sessionmaker, job_id) == ("done", 1)
