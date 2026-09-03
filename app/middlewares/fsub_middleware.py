"""
Force Subscribe middleware.

Intercepts every incoming Message in groups/supergroups.
If force_subscribe is enabled for that group and the sender is not subscribed,
the middleware:
  1. Deletes the user's message.
  2. Restricts the user (no send_messages).
  3. Sends the subscribe prompt (or re-uses an existing one).

The middleware pattern keeps the handler layer completely free of
subscription-gate logic.
"""

from __future__ import annotations

from html import escape
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

from app.services import group_service, subscription_service
from app.keyboards.fsub import fsub_keyboard
from app.utils.logger import logger

# Chat types where force-subscribe is active
_GROUP_TYPES = {"group", "supergroup"}

# Statuses that are always allowed through (group privileged members)
_EXEMPT_STATUSES = {"administrator", "creator"}

# Message text shown to non-subscribed users
_FSUB_TEXT_SINGLE = (
    "⚠️ Xabar yuborishdan oldin kanalimizga obuna bo'lishingiz kerak!\n\n"
    "📢 Quyidagi kanalga obuna bo'ling va keyin\n"
    "<b>«✅ Obunani tekshirish»</b> tugmasini bosing."
)

_FSUB_TEXT_MULTI = (
    "⚠️ Guruhda yozish uchun quyidagi <b>barcha</b> kanallarga obuna bo'ling:\n\n"
    "Obuna bo'lgach <b>«✅ Obunani tekshirish»</b> tugmasini bosing."
)


class ForceSubscribeMiddleware(BaseMiddleware):
    """
    Outer middleware attached to the message update pipeline.

    Runs before any handler so that blocked users never trigger
    business-logic handlers at all.
    """

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        # ---- 1. Only act on group / supergroup messages ----
        if event.chat.type not in _GROUP_TYPES:
            return await handler(event, data)

        # ---- 2. Skip service messages (no from_user) ----
        if event.from_user is None:
            return await handler(event, data)

        user_id: int = event.from_user.id
        chat_id: int = event.chat.id
        bot = data["bot"]

        # ---- 3. Skip if sender is a bot ----
        if event.from_user.is_bot:
            return await handler(event, data)

        state = data.get("state")
        if state is not None and await state.get_state():
            member_status = await subscription_service.get_member_status(bot, chat_id, user_id)
            if member_status in _EXEMPT_STATUSES:
                return await handler(event, data)

        # ---- 4. Always let commands through (admin commands must not be blocked) ----
        if event.text and event.text.startswith("/"):
            return await handler(event, data)

        # ---- 5. Ensure group doc exists ----
        try:
            group = await group_service.ensure_group_exists(
                group_id=chat_id,
                title=event.chat.title or str(chat_id),
            )
        except Exception as exc:
            logger.error("Failed to ensure group %s exists: %s", chat_id, exc)
            return await handler(event, data)

        if group.get("is_active") is False or group.get("permissions_valid") is False:
            return await handler(event, data)

        # ---- 6. Check if fsub is enabled ----
        try:
            fsub = await group_service.get_fsub_settings(chat_id)
        except Exception as exc:
            logger.error("Failed to get fsub settings for %s: %s", chat_id, exc)
            return await handler(event, data)

        if not fsub.get("enabled", False):
            return await handler(event, data)

        channels: list[dict] = fsub.get("channels", [])
        if not channels:
            # Fsub enabled but no channels configured — pass through
            return await handler(event, data)

        # ---- 7. Skip admins / creators inside the group ----
        member_status = await subscription_service.get_member_status(bot, chat_id, user_id)
        if member_status in _EXEMPT_STATUSES:
            return await handler(event, data)

        # ---- 8. Check subscriptions ----
        try:
            all_ok, missing = await subscription_service.check_all_subscriptions(
                bot=bot,
                user_id=user_id,
                channels=channels,
                fresh=False,
            )
        except Exception as exc:
            logger.error("Subscription check failed for user %s: %s", user_id, exc)
            return await handler(event, data)

        if all_ok:
            # User is subscribed — make sure they are not accidentally restricted
            await subscription_service.unrestrict_user(bot, chat_id, user_id)
            return await handler(event, data)

        # ---- 8. User is NOT subscribed — enforce ----
        logger.info(
            "User %s not subscribed in group %s. Missing %d channel(s).",
            user_id, chat_id, len(missing),
        )

        # Track fsub check stat (fire-and-forget)
        import asyncio
        from app.services import stats_service
        asyncio.create_task(stats_service.inc_fsub_checks(chat_id))

        # Delete the offending message
        await subscription_service.delete_message_safe(bot, chat_id, event.message_id)

        # Restrict the user
        await subscription_service.restrict_user(bot, chat_id, user_id)

        # Build and send the subscribe prompt
        channel_lines = "\n".join(
            f"• {escape(ch.get('username') or ch.get('title') or str(ch.get('channel_id', 'Kanal')))}"
            for ch in channels
        )
        text = (
            "⚠️ Xabar yuborishdan oldin kanalimizga obuna bo'lishingiz kerak.\n\n"
            "📢 Quyidagi kanallarga obuna bo'ling:\n"
            f"{channel_lines}\n\n"
            "Obuna bo'lgach, tekshirish tugmasini bosing."
        )
        keyboard = fsub_keyboard(channels=channels, user_id=user_id, chat_id=chat_id)

        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning("Could not send fsub prompt to chat %s: %s", chat_id, exc)

        # Stop propagation — no handler should process this update further
        return None
