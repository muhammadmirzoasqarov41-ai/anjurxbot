"""
Global error handler router for Aiogram 3.13.1.
Intercepts unhandled exceptions, logs tracebacks securely, and prevents raw error exposure.
"""
import logging
from aiogram import Router
from aiogram.types import ErrorEvent
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

logger = logging.getLogger("anjurxbot.errors")
router = Router(name="error_router")


@router.errors()
async def global_error_handler(event: ErrorEvent):
    """Global catch-all error handler."""
    exception = event.exception

    # Benign or expected Telegram client race conditions
    if isinstance(exception, TelegramBadRequest):
        err_msg = str(exception).lower()
        if "message is not modified" in err_msg or "message to edit not found" in err_msg:
            return True
        if "chat not found" in err_msg or "user not found" in err_msg:
            logger.warning("TelegramBadRequest: %s", exception)
            return True
        logger.warning("TelegramBadRequest encountered: %s", exception)
        return True

    if isinstance(exception, TelegramForbiddenError):
        logger.warning("TelegramForbiddenError (bot was blocked/restricted): %s", exception)
        return True

    # Critical / unexpected exceptions: log securely with traceback
    logger.error(
        "Unhandled exception in update %s: %s",
        getattr(event.update, "update_id", "unknown"),
        exception,
        exc_info=exception,
    )

    # Inform user with friendly message instead of raw crash
    try:
        if event.update.callback_query:
            await event.update.callback_query.answer(
                "⚠️ Amaliyotni bajarishda xatolik yuz berdi. Iltimos qayta urinib ko'ring.",
                show_alert=True,
            )
        elif event.update.message:
            await event.update.message.reply(
                "⚠️ <i>Xatolik yuz berdi. Iltimos birozdan so'ng qayta urinib ko'ring.</i>",
                parse_mode="HTML",
            )
    except Exception as notify_err:
        logger.debug("Could not send error notification to user: %s", notify_err)

    return True
