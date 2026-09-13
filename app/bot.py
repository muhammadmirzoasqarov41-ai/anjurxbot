"""
Telegram Bot factory and Dispatcher setup.
Wires middlewares, handlers, and routers.
"""
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import config
from app.middlewares.dedup import DedupMiddleware
from app.middlewares.rate_limit import RateLimitMiddleware
from app.middlewares.guard_middleware import GuardMiddleware

from app.handlers.start import router as start_router
from app.handlers.setup import router as setup_router
from app.handlers.guard import router as guard_router
from app.handlers.admin import router as admin_router
from app.handlers.member import router as member_router
from app.handlers.errors import router as errors_router

logger = logging.getLogger("anjurxbot.bot")


def create_bot() -> Bot:
    """Creates an Aiogram Bot instance configured with HTML parse mode."""
    if not config.bot_token or config.bot_token.strip() in ("", "YOUR_TELEGRAM_BOT_TOKEN_HERE"):
        logger.warning("BOT_TOKEN is not set or using placeholder! Operating in dry/standby mode.")

    bot = Bot(
        token=config.bot_token or "123456789:DryRunPlaceholderTokenForLocalBuildTest",
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    return bot


def create_dispatcher() -> Dispatcher:
    """Creates an Aiogram Dispatcher and registers middlewares and routers in order."""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # 1. Update-level deduplication middleware
    dp.update.outer_middleware(DedupMiddleware())

    # 2. Rate limiting middleware
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())

    # 3. Guard & spam/flood/link filter middleware (Qorovul)
    dp.message.middleware(GuardMiddleware())

    # 4. Handlers routers
    dp.include_router(start_router)
    dp.include_router(setup_router)
    dp.include_router(guard_router)
    dp.include_router(admin_router)
    dp.include_router(member_router)
    dp.include_router(errors_router)

    return dp
