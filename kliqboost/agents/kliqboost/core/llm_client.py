"""Baseten Kimi K2.6 client (OpenAI-compatible)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import AsyncIterator

import aiohttp

log = logging.getLogger(__name__)

BASETEN_URL = os.getenv("BASETEN_URL", "https://inference.baseten.co/v1/chat/completions")
BASETEN_KEY = os.getenv("BASETEN_API_KEY", "")
BASETEN_MODEL = os.getenv("BASETEN_MODEL", "moonshotai/Kimi-K2.6")
LLM_TIMEOUT_SECS = int(os.getenv("LLM_TIMEOUT_SECS", "90"))


async def chat(
    system_prompt: str,
    messages: list[dict],
    *,
    temperature: float = 0.7,
    max_tokens: int = 600,
) -> str:
    if not BASETEN_KEY:
        log.error("BASETEN_API_KEY not set")
        return ""

    payload = {
        "model": BASETEN_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {BASETEN_KEY}", "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=LLM_TIMEOUT_SECS)

    for attempt in range(1, 4):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(BASETEN_URL, json=payload, headers=headers) as resp:
                    if resp.status >= 500:
                        log.warning("Baseten %s on attempt %s", resp.status, attempt)
                        await asyncio.sleep(1.5 * attempt)
                        continue
                    if resp.status != 200:
                        body = await resp.text()
                        log.error("Baseten %s: %s", resp.status, body[:300])
                        return ""
                    data = await resp.json()
                    return (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )
        except Exception as exc:
            log.warning("Baseten attempt %s failed: %s", attempt, exc)
            await asyncio.sleep(1.0 * attempt)
    return ""


async def stream(
    system_prompt: str,
    messages: list[dict],
    *,
    temperature: float = 0.7,
    max_tokens: int = 600,
) -> AsyncIterator[str]:
    if not BASETEN_KEY:
        log.error("BASETEN_API_KEY not set")
        return

    payload = {
        "model": BASETEN_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {BASETEN_KEY}", "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=LLM_TIMEOUT_SECS)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(BASETEN_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    log.error("Baseten stream %s", resp.status)
                    return
                async for raw in resp.content:
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data)
                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            yield delta
                    except Exception:
                        continue
    except Exception as exc:
        log.warning("Baseten stream failed: %s", exc)
