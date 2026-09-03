"""
Guard middleware.

Runs AFTER ForceSubscribeMiddleware (registered second as outer middleware).
Applies all enabled guard filters to every group message.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

from app.services import guard_service, punishment_service, spam_service, stats_service, log_service
from app.services.flood_service import check_flood, reset_flood
from app.services.subscription_service import get_member_status
from app.utils.logger import logger

_GROUP_TYPES = {"group", "supergroup"}
_EXEMPT_STATUSES = {"administrator", "creator"}
_NOTICE_TTL = 15


async def _handle_violation(
    bot: Any,
    chat_id: int,
    user_id: int,
    message_id: int,
    event_type: str,
    reason: str,
    mute_duration: int,
    immediate_mute: bool = False,
) -> None:
    """Helper to process a guard violation."""
    # 1. Log the event & increment stats
    asyncio.create_task(stats_service.inc_guard_event(chat_id, event_type))
    asyncio.create_task(log_service.log_guard_event(chat_id, user_id, event_type, message_id))

    # 2. Delete the offending message
    await punishment_service.delete_message(bot, chat_id, message_id)

    # 3. Apply punishment
    if immediate_mute:
        await punishment_service.mute_user(bot, chat_id, user_id, seconds=mute_duration, reason=reason)
        notice = (
            f"🌊 <b>Juda ko'p xabar yuboryapsiz.</b>\n"
            "Iltimos, biroz kuting. Siz vaqtincha cheklindingiz."
        )
    else:
        warnings = await punishment_service.warn_user(bot, chat_id, user_id, mute_duration, reason=reason)
        if warnings < 3:
            notice = (
                f"⚠️ <b>OGOHLANTIRISH</b>\n\n"
                f"Siz guruh qoidalarini buzdingiz ({reason}).\n\n"
                f"👤 Ogohlantirish: {warnings}/3\n\n"
                "Keyingi qoidabuzarlikda vaqtincha cheklov qo'yilishi mumkin."
            )
        else:
            notice = (
                f"🔇 <b>Siz 3 marta ogohlantirildingiz.</b>\n\n"
                "Guruh qoidalarini buzganingiz sababli\n"
                "vaqtincha yozish huquqingiz cheklangan."
            )

    await punishment_service.send_notice(bot, chat_id, notice, auto_delete_after=_NOTICE_TTL)


class GuardMiddleware(BaseMiddleware):
    """
    Outer middleware that enforces guard rules on group messages.
    """

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if event.chat.type not in _GROUP_TYPES:
            return await handler(event, data)

        if event.from_user is None or event.from_user.is_bot:
            return await handler(event, data)

        if event.text and event.text.startswith("/"):
            return await handler(event, data)

        user_id: int = event.from_user.id
        chat_id: int = event.chat.id
        bot = data["bot"]

        state = data.get("state")
        if state is not None and await state.get_state():
            member_status = await get_member_status(bot, chat_id, user_id)
            if member_status in _EXEMPT_STATUSES:
                return await handler(event, data)

        try:
            group = await group_service.get_group(chat_id)
            if group and (group.get("is_active") is False or group.get("permissions_valid") is False):
                return await handler(event, data)
            guard = await guard_service.get_guard_settings(chat_id)
        except Exception as exc:
            logger.error("Failed to load guard settings for %s: %s", chat_id, exc)
            return await handler(event, data)

        if not guard.get("enabled", False):
            return await handler(event, data)

        try:
            status = await get_member_status(bot, chat_id, user_id)
        except Exception:
            status = None

        if status in _EXEMPT_STATUSES:
            return await handler(event, data)

        # Track total checked messages
        asyncio.create_task(stats_service.inc_checked(chat_id))

        mute_duration: int = int(guard.get("mute_duration", 300))
        anti_spam_on: bool = guard.get("anti_spam", True)

        # ---- 7a. Anti-Flood ------------------------------------------------
        if anti_spam_on and guard.get("anti_flood", True):
            flood_limit = int(guard.get("flood_limit", 5))
            flood_window = float(guard.get("flood_window", 5))
            if check_flood(chat_id, user_id, flood_limit, flood_window):
                logger.info("FLOOD_DETECTED group=%s user=%s", chat_id, user_id)
                await _handle_violation(bot, chat_id, user_id, event.message_id, "flood", "Flood", mute_duration, immediate_mute=True)
                reset_flood(chat_id, user_id)
                return None

        # ---- 7b. Anti-Repeat -----------------------------------------------
        if anti_spam_on and guard.get("anti_repeat", True):
            if spam_service.is_repeated_message(chat_id, user_id, event):
                logger.info("REPEAT_MESSAGE_DETECTED group=%s user=%s", chat_id, user_id)
                await _handle_violation(bot, chat_id, user_id, event.message_id, "repeat", "Takroriy xabar", mute_duration)
                return None

        # ---- 7c. Anti-Link -------------------------------------------------
        if anti_spam_on and guard.get("anti_link", False):
            if spam_service.has_link(event):
                logger.info("LINK_DETECTED group=%s user=%s", chat_id, user_id)
                await _handle_violation(bot, chat_id, user_id, event.message_id, "link", "Havola yuborish", mute_duration)
                return None

        # ---- 7d. Anti-Advertisement ----------------------------------------
        if anti_spam_on and guard.get("anti_ads", True):
            if spam_service.is_advertisement(event):
                logger.info("ADVERTISEMENT_DETECTED group=%s user=%s", chat_id, user_id)
                await _handle_violation(bot, chat_id, user_id, event.message_id, "advertisement", "Reklama", mute_duration)
                return None

        # ------------------------------------------------------------------ #
        # 8. Bad-Word Filter
        # ------------------------------------------------------------------ #
        if guard.get("bad_words", False):
            try:
                bad_words = await guard_service.get_bad_words(chat_id)
            except Exception as exc:
                logger.error("Failed to load bad words for %s: %s", chat_id, exc)
                bad_words = []

            if bad_words and spam_service.contains_bad_word(event, bad_words):
                logger.info("BAD_WORD_DETECTED group=%s user=%s", chat_id, user_id)
                await _handle_violation(bot, chat_id, user_id, event.message_id, "bad_word", "Taqiqlangan so'z", mute_duration)
                return None

        # ------------------------------------------------------------------ #
        # 9. New Member Protection
        # ------------------------------------------------------------------ #
        if guard.get("new_member_protection", True):
            from app.services.new_member_service import is_new_member
            if is_new_member(chat_id, user_id):
                logger.info("NEW_MEMBER_ACTIVITY group=%s user=%s", chat_id, user_id)

        return await handler(event, data)
