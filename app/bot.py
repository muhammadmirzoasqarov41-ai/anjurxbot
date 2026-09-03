"""
Bot and Dispatcher factory + lifecycle hooks.

This module is the single place that:
  - Creates the :class:`aiogram.Bot` and :class:`aiogram.Dispatcher` instances.
  - Registers all routers (handlers).
  - Defines startup and shutdown hooks for Firestore, logging, etc.
  - Exposes ``run_polling()`` as the sole public entry point called by
    ``main.py``.

Adding a new handler in a future phase is a two-step change:
  1. Create ``app/handlers/<feature>.py`` with a ``router`` object.
  2. Add one ``dp.include_router(...)`` line in ``_register_routers()``.
"""

from __future__ import annotations

import asyncio
import fcntl
import os
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeAllChatAdministrators, BotCommandScopeAllPrivateChats, ErrorEvent

from app.config import settings
from app.handlers import (
    admin, admin_fsm, admin_panel, force_subscribe,
    fsub_admin, guard_admin, new_member, setup, start,
)
from app.middlewares.fsub_middleware import ForceSubscribeMiddleware
from app.middlewares.guard_middleware import GuardMiddleware
from app.middlewares.dedup import UpdateDedupMiddleware
from app.middlewares.rate_limit import CallbackRateLimitMiddleware
from app.services.firebase import firebase_service
from app.utils.logger import logger

_POLLING_LOCK_PATH = "/tmp/anjurxbot-polling.lock"


def _acquire_polling_lock():
    lock_file = open(_POLLING_LOCK_PATH, "w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_file.close()
        raise RuntimeError("Another AnjurXBot polling instance is already running") from exc
    return lock_file


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _create_bot() -> Bot:
    """Instantiate the :class:`aiogram.Bot` with sensible defaults."""
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def _create_dispatcher() -> Dispatcher:
    """Instantiate the :class:`aiogram.Dispatcher` with FSM storage."""
    return Dispatcher(storage=MemoryStorage())


def _register_routers(dp: Dispatcher) -> None:
    """
    Attach all feature routers to the dispatcher.

    Order matters for filter priority: more specific routers should come first.
    Admin/fsub_admin routers before the middleware so commands bypass the gate.
    """
    # Phase 1 — core
    dp.include_router(start.router)
    dp.include_router(admin.router)
    # Phase 2 — Force Subscribe
    dp.include_router(fsub_admin.router)       # admin commands
    dp.include_router(force_subscribe.router)  # verify callback
    # Phase 3 — Guard
    dp.include_router(guard_admin.router)      # guard panel + bad words (group commands)
    dp.include_router(new_member.router)       # new member join tracking
    dp.include_router(setup.router)             # onboarding + permission checks
    # Phase 4 — Admin Panel
    dp.include_router(admin_panel.router)      # inline admin panel navigation
    dp.include_router(admin_fsm.router)        # FSM flows (flood, bad words, fsub add)
    # Future phases — just add lines here:
    # dp.include_router(stats.router)


def _register_middlewares(dp: Dispatcher) -> None:
    """
    Attach middlewares to the dispatcher.

    Registration order for outer middlewares:
      1. ForceSubscribeMiddleware  — gate: must be subscribed first
      2. GuardMiddleware           — content filtering

    aiogram calls outer middlewares in LIFO order for the same event,
    so we register ForceSubscribe first and Guard second — Guard runs
    after ForceSubscribe has already allowed the message through.
    """
    # Aiogram wraps later registrations outside earlier ones. Keep the
    # subscription gate outside Guard so unsubscribed messages stop first.
    dp.message.outer_middleware(GuardMiddleware())
    dp.message.outer_middleware(ForceSubscribeMiddleware())
    dp.callback_query.outer_middleware(CallbackRateLimitMiddleware())
    dp.update.outer_middleware(UpdateDedupMiddleware())


# --------------------------------------------------------------------------- #
# Lifecycle hooks
# --------------------------------------------------------------------------- #

async def _on_startup(bot: Bot) -> None:
    """Run once when the dispatcher starts polling."""
    logger.info("Bot is starting up…")

    # Initialise Firebase (exits the process on failure so we fail fast)
    try:
        firebase_service.initialize()
    except RuntimeError:
        # Error already logged inside FirebaseService.initialize()
        raise

    bot_info = await bot.get_me()
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Telegram webhook cleared; polling mode enabled")
    await bot.set_my_commands(
        [BotCommand(command="start", description="Botni ishga tushirish"), BotCommand(command="help", description="Yordam")],
        scope=BotCommandScopeAllPrivateChats(),
    )
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Botni ishga tushirish"),
            BotCommand(command="panel", description="Admin panel"),
            BotCommand(command="setup", description="Guruhni sozlash"),
            BotCommand(command="guard", description="Qorovul"),
            BotCommand(command="fsub", description="Majburiy obuna"),
            BotCommand(command="stats", description="Statistika"),
        ],
        scope=BotCommandScopeAllChatAdministrators(),
    )
    logger.info(
        "Bot started successfully. Username: @%s  ID: %s",
        bot_info.username,
        bot_info.id,
    )


async def _on_shutdown(bot: Bot) -> None:
    """Run once when the dispatcher is stopping."""
    logger.info("Bot is shutting down…")
    await firebase_service.close()
    await bot.session.close()
    logger.info("Bot shut down cleanly.")


# --------------------------------------------------------------------------- #
# Global error handler
# --------------------------------------------------------------------------- #

def _register_error_handler(dp: Dispatcher) -> None:
    """
    Catch all unhandled exceptions so a single bad update never kills the bot.
    """

    @dp.errors()
    async def global_error_handler(event: ErrorEvent, **kwargs: Any) -> bool:
        exc = event.exception

        if isinstance(exc, TelegramAPIError):
            logger.warning("Telegram API error: %s", exc)
        else:
            logger.error("Unhandled exception: %s", exc, exc_info=exc)

        # Try to notify the user if there is an associated message
        update = event.update
        message = getattr(update, "message", None) or getattr(
            update.callback_query, "message", None
        ) if update.callback_query else None

        if message is not None:
            try:
                await message.answer(
                    "❌ Kutilmagan xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring."
                )
            except Exception:
                pass  # Never let the error handler itself crash

        return True  # Mark the error as handled


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

async def run_polling() -> None:
    """
    Build the bot, register everything, and start long-polling.

    This is the only function that ``main.py`` needs to call.
    """
    lock_file = _acquire_polling_lock()
    bot = _create_bot()
    dp = _create_dispatcher()

    _register_routers(dp)
    _register_middlewares(dp)
    _register_error_handler(dp)

    dp.startup.register(_on_startup)
    dp.shutdown.register(_on_shutdown)

    logger.info("Starting polling…")
    try:
        logger.info("Telegram polling started")
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "my_chat_member", "chat_member"],
        )
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


async def run_web_service() -> None:
    """Run polling and the read-only admin panel in one Render Web Service."""
    from aiohttp import web
    from app.web_admin import create_app

    lock_file = _acquire_polling_lock()
    bot = _create_bot()
    dp = _create_dispatcher()
    _register_routers(dp)
    _register_middlewares(dp)
    _register_error_handler(dp)
    dp.startup.register(_on_startup)
    dp.shutdown.register(_on_shutdown)

    web_app = await create_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000")))
    await site.start()
    logger.info("Web service health endpoint started on PORT=%s", os.getenv("PORT", "10000"))
    try:
        logger.info("Telegram polling started")
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "my_chat_member", "chat_member"],
        )
    finally:
        await runner.cleanup()
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
