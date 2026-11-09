"""GitHub REST client authenticated as a GitHub App installation.

Why App auth instead of a personal access token: PATs are tied to one user account,
while App installation tokens are scoped to the repo, carry granular permissions,
and expire after one hour.
"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import jwt

from gitgoblin.settings import get_settings

API_URL = "https://api.github.com"
BASE_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "gitgoblin",
}


def _app_jwt() -> str:
    settings = get_settings()
    now = int(time.time())
    private_key = settings.github_private_key.get_secret_value().replace("\\n", "\n")
    claims = {"iat": now - 60, "exp": now + 540, "iss": settings.github_app_id}
    return jwt.encode(claims, private_key, algorithm="RS256")


class GitHubClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def get_pr_diff(self, owner: str, repo: str, number: int) -> str:
        response = await self._http.get(
            f"/repos/{owner}/{repo}/pulls/{number}",
            headers={"Accept": "application/vnd.github.diff"},
        )
        response.raise_for_status()
        return response.text

    async def list_issue_comments(self, owner: str, repo: str, number: int) -> list[dict]:
        """First 100 comments, oldest first."""
        response = await self._http.get(
            f"/repos/{owner}/{repo}/issues/{number}/comments",
            params={"per_page": 100},
        )
        response.raise_for_status()
        return response.json()

    async def post_issue_comment(self, owner: str, repo: str, number: int, body: str) -> None:
        response = await self._http.post(
            f"/repos/{owner}/{repo}/issues/{number}/comments",
            json={"body": body},
        )
        response.raise_for_status()


@asynccontextmanager
async def installation_client(installation_id: int) -> AsyncIterator[GitHubClient]:
    """Yield a client authenticated as the given App installation."""
    async with httpx.AsyncClient(base_url=API_URL, headers=BASE_HEADERS, timeout=30) as http:
        response = await http.post(
            f"/app/installations/{installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {_app_jwt()}"},
        )
        response.raise_for_status()
        http.headers["Authorization"] = f"Bearer {response.json()['token']}"
        yield GitHubClient(http)
