"""HTTP entrypoint: health check and HMAC-verified GitHub webhook.

The webhook never does the slow work itself. It verifies, records the delivery, queues
a job, and answers in milliseconds; `python -m gitgoblin.worker` runs the job.

Local: `uv run uvicorn gitgoblin.main:app --reload --port 8080`
"""

import hashlib
import hmac
import json
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from gitgoblin.db.session import get_session
from gitgoblin.queue import enqueue, record_delivery
from gitgoblin.settings import github_settings
from gitgoblin.webhook import Ignored, plan_job

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
log = logging.getLogger("gitgoblin")

app = FastAPI(title="GitGoblin")


def signature_is_valid(secret: str, body: bytes, signature: str | None) -> bool:
    """GitHub signs the exact raw body with HMAC-SHA256; compare in constant time."""
    if not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    return "GitGoblin is healthy and watching 😈"


@app.post("/api/webhook", response_class=PlainTextResponse)
async def github_webhook(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> PlainTextResponse:
    # Verify against the raw bytes: re-serialized JSON would not match GitHub's signature.
    body = await request.body()
    secret = github_settings().github_webhook_secret.get_secret_value()
    if not signature_is_valid(secret, body, request.headers.get("x-hub-signature-256")):
        log.warning("Rejected webhook: missing or invalid signature")
        return PlainTextResponse("Unauthorized: invalid signature", status_code=401)

    # GitHub's unique id for this delivery; identical on redelivery.
    delivery_id = request.headers.get("x-github-delivery")
    if not delivery_id:
        return PlainTextResponse("Missing X-GitHub-Delivery header", status_code=400)
    event = request.headers.get("x-github-event", "")
    payload = json.loads(body)
    plan = plan_job(event, payload)

    # One transaction: the delivery row and its job are saved together or not at all.
    async with session.begin():
        if not await record_delivery(session, delivery_id, event, payload):
            log.info("Duplicate delivery %s ignored", delivery_id)
            return PlainTextResponse("Duplicate delivery ignored")
        if isinstance(plan, Ignored):
            return PlainTextResponse(plan.reason)
        job_id = await enqueue(session, plan, delivery_id)

    log.info("Delivery %s (%s) queued as job %d [%s]", delivery_id, event, job_id, plan.kind)
    return PlainTextResponse(f"Queued job {job_id}", status_code=202)
