import asyncio
import logging
import sys
import os
from datetime import datetime, timezone

import aiohttp

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


SYNC_KEY = os.getenv("STATS_SYNC_KEY", "kliq-stats-2026-xK9m")
LAST_LLM_OK_AT: str | None = None


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
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)):
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
