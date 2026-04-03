import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from middlewares.i18n import I18nMiddleware
from middlewares.logger import ConversationLoggerMiddleware, CallbackLoggerMiddleware
from db.conversations import init_db

from handlers.start import router as start_router
from handlers.services import router as services_router
from handlers.pricing import router as pricing_router
from handlers.case_studies import router as case_studies_router
from handlers.faq import router as faq_router
from handlers.order_flow import router as order_flow_router
from handlers.language import router as language_router
from handlers.admin import router as admin_router
from handlers.ai_chat import router as ai_chat_router


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

    # Register routers (order matters — ai_chat is the catch-all, must be last)
    dp.include_router(start_router)
    dp.include_router(services_router)
    dp.include_router(pricing_router)
    dp.include_router(case_studies_router)
    dp.include_router(faq_router)
    dp.include_router(order_flow_router)
    dp.include_router(language_router)
    dp.include_router(admin_router)
    dp.include_router(ai_chat_router)

    logging.info("Bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
