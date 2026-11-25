"""Background worker: claims jobs from Postgres and runs them.

Run: `uv run python -m gitgoblin.worker`

    ┌─ slot ─────────────────────────────────────────────┐
    │ claim (SKIP LOCKED) ─► run handler ─► complete      │
    │        │ nothing        │ every 30s: extend lease   │
    │        ▼                │ error ─► fail (retry/give up)
    │    wait 1s              ▼                            │
    └──────── repeat until SIGTERM, finishing the current job
    WORKER_CONCURRENCY slots run side by side in one process.
"""

import asyncio
import logging
import signal
import traceback
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from gitgoblin.db.session import get_engine, get_sessionmaker
from gitgoblin.jobs import JobKind
from gitgoblin.mentions import reply_to_mention
from gitgoblin.models import WebhookContext
from gitgoblin.queue import ClaimedJob, claim_job, complete_job, extend_lease, fail_job
from gitgoblin.review import review_pull_request
from gitgoblin.settings import worker_settings

log = logging.getLogger("gitgoblin.worker")

Handler = Callable[[dict[str, Any]], Awaitable[None]]

# If a worker dies, its job becomes claimable again once the lease runs out.
LEASE_SECONDS = 120
HEARTBEAT_SECONDS = 30
POLL_SECONDS = 1.0


def _context(payload: dict[str, Any]) -> WebhookContext:
    return WebhookContext(
        installation_id=payload["installation_id"],
        owner=payload["owner"],
        repo=payload["repo"],
        number=payload["number"],
    )


async def _review(payload: dict[str, Any]) -> None:
    await review_pull_request(_context(payload))


async def _reply(payload: dict[str, Any]) -> None:
    await reply_to_mention(_context(payload), payload["comment_id"], payload["body"])


# Registry: job kind → function. Adding a job type = one entry here + one in JobKind.
HANDLERS: dict[str, Handler] = {
    JobKind.REVIEW_PULL_REQUEST: _review,
    JobKind.REPLY_TO_MENTION: _reply,
}


class LeaseLost(Exception):
    """Our lease expired and another worker took the job; stop and write nothing."""


class Worker:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        handlers: dict[str, Handler],
        *,
        lease_seconds: float = LEASE_SECONDS,
        heartbeat_seconds: float = HEARTBEAT_SECONDS,
        poll_seconds: float = POLL_SECONDS,
    ) -> None:
        self.sessionmaker = sessionmaker
        self.handlers = handlers
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.poll_seconds = poll_seconds

    async def run(self, concurrency: int, stop: asyncio.Event) -> None:
        async with asyncio.TaskGroup() as group:
            for slot in range(concurrency):
                group.create_task(self._slot(slot, stop))

    async def _slot(self, slot: int, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                if not await self.run_once():
                    # Idle: sleep, but wake immediately on shutdown.
                    with suppress(TimeoutError):
                        await asyncio.wait_for(stop.wait(), self.poll_seconds)
            except Exception:
                # A database blip must not kill the worker; back off and try again.
                log.exception("Slot %d crashed; retrying in %.0fs", slot, self.poll_seconds)
                await asyncio.sleep(self.poll_seconds)

    async def run_once(self) -> bool:
        """Claim and process one job. Returns False if the queue had nothing ready."""
        async with self.sessionmaker() as session, session.begin():
            job = await claim_job(session, self.lease_seconds)
        if job is None:
            return False
        await self._process(job)
        return True

    async def _process(self, job: ClaimedJob) -> None:
        log.info("Job %d [%s] attempt %d/%d started", job.id, job.kind, job.attempts, job.max_attempts)

        handler = self.handlers.get(job.kind)
        if handler is None:
            reason = f"No handler for job kind '{job.kind}'"
            await self._fail(job, reason, reason, permanent=True)
            return
        if job.attempts > job.max_attempts:
            # Re-claimed after the previous owner's lease expired on its final attempt.
            reason = "Lease expired during the final attempt"
            await self._fail(job, reason, reason, permanent=True)
            return

        try:
            await self._run_with_heartbeat(job, handler)
        except LeaseLost:
            log.warning("Job %d: lease lost to another worker; result discarded", job.id)
            return
        except Exception as exc:
            # Stored: full traceback (tail). Logged: "ValidationError: 1 validation error for ...".
            summary = traceback.format_exception_only(exc)[0].strip().splitlines()[0]
            await self._fail(job, "".join(traceback.format_exception(exc))[-4000:], summary)
            return

        async with self.sessionmaker() as session, session.begin():
            completed = await complete_job(session, job)
        if completed:
            log.info("Job %d done", job.id)
        else:
            log.warning("Job %d finished after losing its lease; another worker owns it", job.id)

    async def _run_with_heartbeat(self, job: ClaimedJob, handler: Handler) -> None:
        """Run the handler, extending the lease every heartbeat while it works."""
        work = asyncio.create_task(handler(job.payload))
        try:
            while True:
                done, _ = await asyncio.wait({work}, timeout=self.heartbeat_seconds)
                if done:
                    return work.result()  # re-raises the handler's exception, if any
                async with self.sessionmaker() as session, session.begin():
                    if not await extend_lease(session, job, self.lease_seconds):
                        raise LeaseLost(job.id)
        finally:
            if not work.done():
                work.cancel()
                with suppress(asyncio.CancelledError):
                    await work

    async def _fail(self, job: ClaimedJob, error: str, summary: str, *, permanent: bool = False) -> None:
        async with self.sessionmaker() as session, session.begin():
            status = await fail_job(session, job, error, permanent=permanent)
        log.warning("Job %d attempt %d failed → %s: %s", job.id, job.attempts, status, summary)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    # Graceful shutdown: stop claiming, let in-flight jobs finish. A hard kill is
    # still safe; the lease expires and another worker retries the job.
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    concurrency = worker_settings().worker_concurrency
    log.info("Worker started with %d slots", concurrency)
    try:
        await Worker(get_sessionmaker(), HANDLERS).run(concurrency, stop)
    finally:
        await get_engine().dispose()
    log.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
