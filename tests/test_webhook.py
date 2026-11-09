"""Webhook: signature, delivery dedupe, and which events become jobs."""

import hashlib
import hmac
import json

import httpx
import pytest
from sqlalchemy import func, select

from gitgoblin.db.models import Job
from gitgoblin.db.session import get_session
from gitgoblin.jobs import JobKind
from gitgoblin.main import app
from gitgoblin.settings import github_settings
from gitgoblin.webhook import Ignored, plan_job

SECRET = "test-secret"
REPO = {"owner": {"login": "o"}, "name": "r"}
PR_OPENED = {"action": "opened", "installation": {"id": 1}, "repository": REPO, "pull_request": {"number": 7}}


@pytest.fixture
async def client(sessionmaker, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY", "unused")
    github_settings.cache_clear()

    async def test_session():
        async with sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    github_settings.cache_clear()


async def _post(client, event, payload, delivery, secret=SECRET):
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {"x-github-event": event, "x-github-delivery": delivery, "x-hub-signature-256": signature}
    return await client.post("/api/webhook", content=body, headers=headers)


async def test_redelivery_is_acknowledged_but_queues_nothing(client, sessionmaker):
    first = await _post(client, "pull_request", PR_OPENED, "delivery-1")
    again = await _post(client, "pull_request", PR_OPENED, "delivery-1")

    assert (first.status_code, again.status_code) == (202, 200)
    async with sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(Job)) == 1


async def test_bad_signature_is_rejected_before_anything_is_stored(client, sessionmaker):
    response = await _post(client, "pull_request", PR_OPENED, "delivery-2", secret="wrong")

    assert response.status_code == 401
    async with sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(Job)) == 0


def _comment(body: str, user_type: str = "User") -> dict:
    return {
        "action": "created",
        "repository": REPO,
        "issue": {"number": 7},
        "comment": {"id": 9, "body": body, "user": {"type": user_type, "login": "x"}},
    }


@pytest.mark.parametrize(
    ("event", "payload", "expected"),
    [
        ("pull_request", PR_OPENED, JobKind.REVIEW_PULL_REQUEST),
        ("pull_request", {**PR_OPENED, "action": "reopened"}, JobKind.REVIEW_PULL_REQUEST),
        ("pull_request", {**PR_OPENED, "action": "closed"}, None),
        ("issue_comment", _comment("@GitGoblin-Dev explain this"), JobKind.REPLY_TO_MENTION),
        ("issue_comment", _comment("looks good"), None),
        # Our own replies contain the mention; answering them would loop forever.
        ("issue_comment", _comment("@gitgoblin-dev said hi", user_type="Bot"), None),
        ("push", {"ref": "refs/heads/main"}, None),
    ],
)
def test_plan_job_routes_events(event, payload, expected):
    plan = plan_job(event, payload)
    assert (None if isinstance(plan, Ignored) else plan.kind) == expected
