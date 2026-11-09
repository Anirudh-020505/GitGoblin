"""Data shared across the webhook, services, and agents."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class WebhookContext:
    """Where a webhook event happened: which installation, repo, and PR/issue."""

    installation_id: int
    owner: str
    repo: str
    number: int


@dataclass(frozen=True)
class ChatTurn:
    """One message in a conversation; `assistant` is GitGoblin, `user` is anyone else."""

    role: Literal["user", "assistant"]
    text: str
