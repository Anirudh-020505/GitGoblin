"""Typed configuration from environment variables (and `.env` in development)."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    github_app_id: str
    github_private_key: SecretStr
    github_webhook_secret: SecretStr

    # Any OpenAI-compatible endpoint. Default: Z.ai GLM Coding Plan.
    llm_api_key: SecretStr
    llm_base_url: str = "https://api.z.ai/api/coding/paas/v4"
    llm_model: str = "glm-5.3"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]  # fields come from the environment
