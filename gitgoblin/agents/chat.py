"""The @gitgoblin-dev conversational persona."""

import logging

from gitgoblin import llm
from gitgoblin.models import ChatTurn

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are GitGoblin, an expert Senior Software Engineer and AI Code Reviewer.
You are helping a team review pull requests. Be concise, technically rigorous,
and encouraging. Format your responses in Markdown with clear code blocks.
Do not hallucinate code that isn't there."""

FAILURE_MESSAGE = (
    "⚠️ *GitGoblin hit an internal error while generating a reply. Please try again later.*"
)


async def generate_reply(prompt: str, history: list[ChatTurn]) -> str:
    try:
        return await llm.generate(SYSTEM_PROMPT, prompt, history=history, temperature=0.3)
    except Exception:
        log.exception("Chat reply failed")
        return FAILURE_MESSAGE
