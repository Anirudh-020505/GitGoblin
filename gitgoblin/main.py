"""HTTP entrypoint: health check and HMAC-verified GitHub webhook.

Local: `uv run uvicorn gitgoblin.main:app --reload --port 8080`
"""

import hashlib
import hmac
import json
import logging

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from gitgoblin.settings import github_settings
from gitgoblin.webhook import handle_event

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
async def github_webhook(request: Request) -> PlainTextResponse:
    # Verify against the raw bytes: re-serialized JSON would not match GitHub's signature.
    body = await request.body()
    secret = github_settings().github_webhook_secret.get_secret_value()
    if not signature_is_valid(secret, body, request.headers.get("x-hub-signature-256")):
        log.warning("Rejected webhook: missing or invalid signature")
        return PlainTextResponse("Unauthorized: invalid signature", status_code=401)

    event = request.headers.get("x-github-event", "")
    try:
        status = await handle_event(event, json.loads(body))
    except Exception:
        log.exception("Failed to process %s event", event)
        return PlainTextResponse("Internal processing error", status_code=500)
    return PlainTextResponse(status)
