"""The @gitgoblin-dev conversational persona. Errors propagate so the worker can retry."""

from gitgoblin import llm
from gitgoblin.models import ChatTurn

SYSTEM_PROMPT = """You are GitGoblin, an expert Senior Software Engineer and AI Code Reviewer.
You are helping a team review pull requests. Be concise, technically rigorous,
and encouraging. Format your responses in Markdown with clear code blocks.
Do not hallucinate code that isn't there."""


async def generate_reply(prompt: str, history: list[ChatTurn]) -> str:
    return await llm.generate(SYSTEM_PROMPT, prompt, history=history, temperature=0.3)
