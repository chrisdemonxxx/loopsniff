import asyncio
import logging
import sys
import os
from datetime import datetime, timezone

import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, API_BASE_URL, OLLAMA_MODEL, OLLAMA_CLOUD_URL
from middlewares.i18n import I18nMiddleware
from middlewares.logger import ConversationLoggerMiddleware, CallbackLoggerMiddleware
from db.conversations import init_db

from handlers.start import router as start_router
from handlers.admin import router as admin_router
from handlers.ai_chat import router as ai_chat_router


SYNC_KEY = os.getenv("STATS_SYNC_KEY", "")
LAST_LLM_OK_AT: str | None = None
_status: dict = {"status": "starting", "conversations": 0, "hot_leads": 0}

HEALTH_PORT = int(os.getenv("BOT_HEALTH_PORT", "8097"))


async def _health_handler(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "status": _status["status"],
            "conversations": _status["conversations"],
            "hot_leads": _status["hot_leads"],
        }
    )


async def _run_health_server() -> None:
    app = web.Application()
    app.router.add_get("/health", _health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HEALTH_PORT)
    await site.start()
    logging.info("Health server listening on port %s", HEALTH_PORT)


async def _send_heartbeat(status: str, last_error: str | None = None) -> None:
    if not API_BASE_URL:
        return
    url = API_BASE_URL.rstrip("/") + "/internal/worker-heartbeat"
    payload = {
        "worker": "bot",
        "authorized": bool(BOT_TOKEN),
        "telegram_connected": status == "online",
        "status": status,
        "last_error": last_error,
        "last_llm_ok_at": LAST_LLM_OK_AT,
        "model": OLLAMA_MODEL or None,
        "ollama_endpoint": OLLAMA_CLOUD_URL or None,
    }
    headers = {"Content-Type": "application/json", "X-Sync-Key": SYNC_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=8),
            ):
                pass
    except Exception as exc:
        logging.warning("Bot heartbeat failed: %s", exc)


async def _heartbeat_loop() -> None:
    while True:
        await _send_heartbeat("online")
        await asyncio.sleep(30)


async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=None)
    dp = Dispatcher(storage=MemoryStorage())

    # Init conversation database
    await init_db()

    # Start health server so the API can probe this worker
    await _run_health_server()
    _status["status"] = "online"

    # Register middlewares (logger first, then i18n)
    dp.message.middleware(ConversationLoggerMiddleware())
    dp.callback_query.middleware(CallbackLoggerMiddleware())
    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(I18nMiddleware())

    # Register routers (ai_chat is the catch-all, must be last)
    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(ai_chat_router)

    logging.info("Bot starting...")
    hb_task = asyncio.create_task(_heartbeat_loop())

    # Prewarm RAG in background — first AI reply isn't 30s slow waiting on ST model.
    async def _prewarm_rag() -> None:
        try:
            from rag.retrieval.retriever import Retriever  # type: ignore

            await asyncio.to_thread(lambda: Retriever().prewarm())
            logging.info("RAG prewarm finished")
        except Exception as exc:
            logging.warning("RAG prewarm failed (non-fatal): %s", exc)

    asyncio.create_task(_prewarm_rag())

    try:
        await dp.start_polling(bot)
    finally:
        hb_task.cancel()
        await _send_heartbeat("offline")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    async def _runner():
        # Retry loop avoids transient disconnects crashing the service.
        delay = 3
        while True:
            try:
                await main()
                return
            except Exception as exc:
                logging.exception("Bot crashed, restarting in %ss: %s", delay, exc)
                await _send_heartbeat("degraded", last_error=str(exc)[:400])
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    asyncio.run(_runner())
