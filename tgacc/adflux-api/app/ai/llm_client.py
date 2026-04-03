"""Shared LLM client for all AI modules. Reusable interface to Ollama Cloud API."""

import aiohttp
import logging
from typing import Optional
from app.config import get_settings

logger = logging.getLogger(__name__)


async def call_llm(
    prompt: str,
    system_prompt: str = "You are a helpful AI assistant.",
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: int = 30,
) -> Optional[str]:
    """Call Ollama Cloud LLM. Returns response text or None on failure.

    Graceful degradation: returns None if LLM is unavailable, letting callers
    fall back to their existing logic (regex, templates, etc.)
    """
    settings = get_settings()

    if not settings.OLLAMA_CLOUD_URL or not settings.OLLAMA_CLOUD_KEY:
        logger.warning("LLM not configured — OLLAMA_CLOUD_URL or OLLAMA_CLOUD_KEY missing")
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.OLLAMA_CLOUD_URL}/chat/completions",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                headers={
                    "Authorization": f"Bearer {settings.OLLAMA_CLOUD_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status != 200:
                    logger.error(f"LLM API returned {resp.status}: {await resp.text()}")
                    return None
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None
