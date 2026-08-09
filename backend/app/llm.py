from __future__ import annotations
"""
Single LLM abstraction. Swap between Ollama (free, local) and Anthropic (cloud)
by setting USE_OLLAMA=true in .env.

Both backends expose the same call() interface so agents don't care which is running.
"""

import logging
from app.config import settings

logger = logging.getLogger(__name__)


async def call(prompt: str, *, fast: bool = False, max_tokens: int = 1024) -> str:
    """
    Call the configured LLM. Returns the response text.

    fast=True uses a smaller/cheaper model for bulk tasks (scoring).
    fast=False uses the better model for quality tasks (research, generation).
    """
    if settings.USE_OLLAMA:
        return await _ollama(prompt, fast=fast, max_tokens=max_tokens)
    return await _anthropic(prompt, fast=fast, max_tokens=max_tokens)


async def _ollama(prompt: str, *, fast: bool, max_tokens: int) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    model = settings.OLLAMA_FAST_MODEL if fast else settings.OLLAMA_MODEL
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()


async def _anthropic(prompt: str, *, fast: bool, max_tokens: int) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    model = "claude-haiku-4-5-20251001" if fast else "claude-sonnet-4-6"
    msg = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()
