import logging
import aiohttp
from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


async def get_ai_response(message: str, context: list[dict] | None = None) -> str:
    """Get AI response from Ollama Cloud API."""
    messages = []
    messages.append({
        "role": "system",
        "content": (
            "You are AdFlux Media's AI support assistant. You help clients with "
            "ad account questions, billing, top-ups, campaign optimization, and general support. "
            "Be concise, friendly, and professional. If you cannot answer, suggest escalating to a human agent."
        ),
    })
    if context:
        messages.extend(context)
    messages.append({"role": "user", "content": message})

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.OLLAMA_CLOUD_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OLLAMA_CLOUD_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": messages,
                    "max_tokens": 512,
                    "temperature": 0.7,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    log.error("Ollama Cloud returned %d", resp.status)
                    return "I'm having trouble connecting right now. Let me escalate you to a human agent."
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception as e:
        log.exception("AI response error: %s", e)
        return "I'm temporarily unavailable. A human agent will be with you shortly."
