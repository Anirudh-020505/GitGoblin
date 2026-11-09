"""Multi-agent review of a pull request: fetch diff → filter → specialists in parallel → one comment."""

import asyncio
import logging

from gitgoblin.agents.specialists import PERFORMANCE, SECURITY
from gitgoblin.diff import reviewable_diff
from gitgoblin.github import installation_client
from gitgoblin.models import WebhookContext

log = logging.getLogger(__name__)


async def review_pull_request(ctx: WebhookContext) -> None:
    log.info("Starting multi-agent review for %s/%s#%d", ctx.owner, ctx.repo, ctx.number)

    async with installation_client(ctx.installation_id) as github:
        diff = reviewable_diff(await github.get_pr_diff(ctx.owner, ctx.repo, ctx.number))
        if not diff.strip():
            log.info("No reviewable files in #%d; skipping AI", ctx.number)
            return

        # Specialists run concurrently: total latency is the slowest agent, not the sum.
        security_review, performance_review = await asyncio.gather(
            SECURITY.review(diff),
            PERFORMANCE.review(diff),
        )

        comment = f"""## 👾 GitGoblin Multi-Agent Review

Thank you for the PR! Our specialist agents have analyzed the changes:

### 🛡️ Security Specialist
{security_review}

### ⚡ Performance Specialist
{performance_review}"""

        await github.post_issue_comment(ctx.owner, ctx.repo, ctx.number, comment)

    log.info("Posted consolidated review on #%d", ctx.number)
