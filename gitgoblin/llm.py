"""The only module that talks to the model provider (any OpenAI-compatible API)."""

from functools import lru_cache

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from gitgoblin.models import ChatTurn
from gitgoblin.settings import get_settings


@lru_cache(maxsize=1)
def _client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=settings.llm_base_url,
    )


async def generate(
    system_prompt: str,
    prompt: str,
    *,
    history: list[ChatTurn] | None = None,
    temperature: float | None = None,
) -> str:
    """Run one completion: system prompt, optional prior turns, then `prompt` as the user."""
    messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": system_prompt}]
    messages += [{"role": turn.role, "content": turn.text} for turn in history or []]
    messages.append({"role": "user", "content": prompt})

    response = await _client().chat.completions.create(
        model=get_settings().llm_model,
        messages=messages,
        **({"temperature": temperature} if temperature is not None else {}),
    )
    text = response.choices[0].message.content if response.choices else None
    if not text:
        raise ValueError("Model returned an empty response")
    return text
