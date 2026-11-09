"""Route verified GitHub webhook events to workflows.

Work is awaited before responding: on serverless hosts the function is frozen once the
response is sent, so fire-and-forget work would be killed.
"""

from typing import Any

from gitgoblin.mentions import is_mentioned, reply_to_mention
from gitgoblin.models import WebhookContext
from gitgoblin.review import review_pull_request

REVIEW_ACTIONS = {"opened", "synchronize"}


def _context(payload: dict[str, Any], number: int) -> WebhookContext:
    return WebhookContext(
        installation_id=(payload.get("installation") or {}).get("id", 0),
        owner=payload["repository"]["owner"]["login"],
        repo=payload["repository"]["name"],
        number=number,
    )


async def handle_event(event: str, payload: dict[str, Any]) -> str:
    """Process one event; returns a short status message for the webhook response."""
    action = payload.get("action")

    if event == "pull_request" and action in REVIEW_ACTIONS:
        await review_pull_request(_context(payload, payload["pull_request"]["number"]))
        return "Pull request reviewed"

    if event == "issue_comment" and action == "created":
        comment = payload["comment"]
        if (comment.get("user") or {}).get("type") == "Bot":
            return "Ignored bot comment"
        body = comment.get("body") or ""
        if not is_mentioned(body):
            return "No mention detected"
        await reply_to_mention(_context(payload, payload["issue"]["number"]), comment["id"], body)
        return "Mention answered"

    return "Event ignored"
