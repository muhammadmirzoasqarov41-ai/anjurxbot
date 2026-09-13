"""
Telegram Bot factory and Dispatcher setup for AnjurX | Rss Bot.
Wires middlewares, handlers, and the background gardener scheduler.
"""
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import config
from app.middlewares.dedup import DedupMiddleware
from app.middlewares.rate_limit import RateLimitMiddleware

from app.handlers.start import router as start_router
from app.handlers.rss import router as rss_router
from app.handlers.errors import router as errors_router

from app.services.rss_storage import rss_storage
from app.services.gardener import gardener

logger = logging.getLogger("anjurxbot.bot")


def create_bot() -> Bot:
    """Creates an Aiogram Bot instance configured with HTML parse mode."""
    if not config.bot_token or config.bot_token.strip() in ("", "YOUR_TELEGRAM_BOT_TOKEN_HERE"):
        logger.warning("BOT_TOKEN is not set or using placeholder! Operating in dry/standby mode.")

    bot = Bot(
        token=config.bot_token or "123456789:DryRunPlaceholderTokenForLocalBuildTest",
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    gardener.set_bot(bot)
    return bot


async def on_startup(bot: Bot):
    """Startup hook: initializes storage and starts background gardener."""
    logger.info("Starting AnjurX | Rss Bot...")
    await rss_storage.init()
    gardener.start(bot)
    logger.info("AnjurX | Rss Bot startup complete.")


async def on_shutdown(bot: Bot):
    """Shutdown hook: stops background gardener cleanly."""
    logger.info("Shutting down AnjurX | Rss Bot...")
    gardener.stop()


def create_dispatcher() -> Dispatcher:
    """Creates an Aiogram Dispatcher and registers middlewares and routers in order."""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # 1. Update-level deduplication middleware
    dp.update.outer_middleware(DedupMiddleware())

    # 2. Rate limiting middleware
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())

    # 3. Handlers routers for RSS Bot
    dp.include_router(start_router)
    dp.include_router(rss_router)
    dp.include_router(errors_router)

    # 4. Lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    return dp
