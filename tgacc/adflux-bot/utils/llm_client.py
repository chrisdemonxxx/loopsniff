"""LLM client for bot AI chat. Calls Ollama Cloud API."""

import aiohttp
import logging
import os

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_CLOUD_URL", "https://api.ollamacloud.com/v1")
OLLAMA_KEY = os.getenv("OLLAMA_CLOUD_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


async def call_llm(
    prompt: str,
    system_prompt: str = (
        "You are a helpful AI assistant for AdFlux, an ad account management platform."
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

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_URL}/chat/completions",
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
                    logger.error("LLM API returned %d", resp.status)
                    return None
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return None
