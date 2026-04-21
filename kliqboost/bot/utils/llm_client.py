"""LLM client for bot AI chat. Calls Ollama Cloud API."""

import aiohttp
import logging
import os

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_CLOUD_URL", "https://ollama.com/v1/chat/completions")
OLLAMA_KEY = os.getenv("OLLAMA_CLOUD_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2:1t")


async def call_llm(
    prompt: str,
    system_prompt: str = (
        "You are a helpful AI assistant for Kliqboost, an ad account management platform."
    ),
    history: list = None,
) -> str | None:
    """Call Ollama Cloud LLM. Returns response text or None."""
    if not OLLAMA_URL or not OLLAMA_KEY:
        logger.warning(
            "LLM not configured — OLLAMA_CLOUD_URL or OLLAMA_CLOUD_API_KEY missing"
        )
        return None

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history[-10:])  # Last 10 messages for context
    messages.append({"role": "user", "content": prompt})

    # OLLAMA_CLOUD_URL already includes /chat/completions
    url = OLLAMA_URL
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"

    import asyncio

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 1024,
                    },
                    headers={
                        "Authorization": f"Bearer {OLLAMA_KEY}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(
                            "LLM API returned %d (attempt %d/3): %s",
                            resp.status, attempt + 1, body[:200],
                        )
                        if attempt < 2:
                            await asyncio.sleep(1.5 * (attempt + 1))
                            continue
                        return None
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("LLM call failed (attempt %d/3): %s", attempt + 1, e)
            if attempt < 2:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            return None
