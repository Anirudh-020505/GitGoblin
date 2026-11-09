"""Reply to @gitgoblin-dev mentions using recent thread comments as conversation history."""

import logging
import re

from gitgoblin.agents.chat import generate_reply
from gitgoblin.github import installation_client
from gitgoblin.models import ChatTurn, WebhookContext

log = logging.getLogger(__name__)

MENTION = "@gitgoblin-dev"
MENTION_PATTERN = re.compile(r"@gitgoblin(-dev)?(\[bot\])?", re.IGNORECASE)
HISTORY_LIMIT = 10


def is_mentioned(body: str) -> bool:
    return MENTION in body.lower()


async def reply_to_mention(ctx: WebhookContext, comment_id: int, body: str) -> None:
    log.info("Replying to mention on %s/%s#%d", ctx.owner, ctx.repo, ctx.number)

    async with installation_client(ctx.installation_id) as github:
        comments = await github.list_issue_comments(ctx.owner, ctx.repo, ctx.number)
        earlier = [c for c in comments if c["id"] != comment_id][-HISTORY_LIMIT:]
        history = [
            ChatTurn(
                role="assistant" if "gitgoblin" in (c.get("user") or {}).get("login", "") else "user",
                text=c.get("body") or "",
            )
            for c in earlier
        ]

        prompt = MENTION_PATTERN.sub("", body).strip()
        reply = await generate_reply(prompt, history)
        await github.post_issue_comment(ctx.owner, ctx.repo, ctx.number, reply)

    log.info("Replied on #%d", ctx.number)
