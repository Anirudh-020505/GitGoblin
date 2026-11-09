"""Typed configuration from environment variables (and `.env` in development).

Split by concern so each process validates only what it uses: migrations need just
the database, the web process never touches the LLM, and so on.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class _Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class GitHubSettings(_Settings):
    github_app_id: str
    github_private_key: SecretStr
    github_webhook_secret: SecretStr


class LLMSettings(_Settings):
    """Any OpenAI-compatible endpoint. Default: Z.ai GLM Coding Plan."""

    llm_api_key: SecretStr
    llm_base_url: str = "https://api.z.ai/api/coding/paas/v4"
    llm_model: str = "glm-5.3"


class DatabaseSettings(_Settings):
    # SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host:5432/db
    database_url: str


class WorkerSettings(_Settings):
    # Jobs one worker process runs at the same time.
    worker_concurrency: int = 4


# Fields come from the environment, hence the pyright ignores on the no-arg constructors.
@lru_cache(maxsize=1)
def github_settings() -> GitHubSettings:
    return GitHubSettings()  # pyright: ignore[reportCallIssue]


@lru_cache(maxsize=1)
def llm_settings() -> LLMSettings:
    return LLMSettings()  # pyright: ignore[reportCallIssue]


@lru_cache(maxsize=1)
def database_settings() -> DatabaseSettings:
    return DatabaseSettings()  # pyright: ignore[reportCallIssue]


@lru_cache(maxsize=1)
def worker_settings() -> WorkerSettings:
    return WorkerSettings()
