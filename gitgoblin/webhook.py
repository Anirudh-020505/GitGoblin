"""Decide what work a verified GitHub webhook asks for. Pure: no network, no database.

    pull_request  opened/synchronize/reopened  → review_pull_request job
    issue_comment created, mentions us, human  → reply_to_mention job
    anything else                              → Ignored("why")
"""

from dataclasses import dataclass
from typing import Any

from gitgoblin.jobs import JobKind, JobSpec
from gitgoblin.mentions import is_mentioned

REVIEW_ACTIONS = {"opened", "synchronize", "reopened"}


@dataclass(frozen=True)
class Ignored:
    reason: str


def _target(payload: dict[str, Any], number: int) -> dict[str, Any]:
    """The fields every job needs to talk to GitHub about one PR/issue."""
    return {
        "installation_id": (payload.get("installation") or {}).get("id", 0),
        "owner": payload["repository"]["owner"]["login"],
        "repo": payload["repository"]["name"],
        "number": number,
    }


def plan_job(event: str, payload: dict[str, Any]) -> JobSpec | Ignored:
    action = payload.get("action")

    if event == "pull_request":
        if action not in REVIEW_ACTIONS:
            return Ignored(f"pull_request action '{action}' does not trigger a review")
        return JobSpec(JobKind.REVIEW_PULL_REQUEST, _target(payload, payload["pull_request"]["number"]))

    if event == "issue_comment" and action == "created":
        comment = payload["comment"]
        if (comment.get("user") or {}).get("type") == "Bot":
            return Ignored("Comment is from a bot")
        body = comment.get("body") or ""
        if not is_mentioned(body):
            return Ignored("No mention detected")
        target = _target(payload, payload["issue"]["number"])
        return JobSpec(JobKind.REPLY_TO_MENTION, {**target, "comment_id": comment["id"], "body": body})

    return Ignored(f"Event '{event}' is not handled")
