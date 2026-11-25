"""Job kinds: the vocabulary shared by the webhook (producer) and the worker (consumer)."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class JobKind(StrEnum):
    REVIEW_PULL_REQUEST = "review_pull_request"
    REPLY_TO_MENTION = "reply_to_mention"


@dataclass(frozen=True)
class JobSpec:
    """A job before it is stored: what to run and the JSON it needs.

    Example:
        JobSpec(kind=JobKind.REVIEW_PULL_REQUEST,
                payload={"installation_id": 122888592, "owner": "Anirudh-020505",
                         "repo": "Stocks-Tracker", "number": 1})
    """

    kind: JobKind
    payload: dict[str, Any]
