"""
Force Subscribe Middleware.
Enforces channel subscription before allowing users to chat in groups.
"""
from typing import Callable, Dict, Any, Awaitable
import logging
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message

from app.services.permission_service import permission_service
from app.services.group_service import group_service
from app.services.subscription_service import subscription_service
from app.services.moderation import moderation_service
from app.keyboards.fsub import get_force_sub_user_keyboard

logger = logging.getLogger("anjurxbot.fsub_middleware")


class ForceSubscribeMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message) or not event.chat or not event.from_user:
            return await handler(event, data)

        # Only apply in group / supergroup chats
        if event.chat.type not in ("group", "supergroup"):
            return await handler(event, data)

        # Ignore bot messages
        if event.from_user.is_bot:
            return await handler(event, data)

        bot: Bot = data.get("bot")
        if not bot:
            return await handler(event, data)

        chat_id = event.chat.id
        user_id = event.from_user.id
        sender_chat_id = event.sender_chat.id if event.sender_chat else None

        # 1. Admin bypass
        if await permission_service.is_user_admin(bot, chat_id, user_id, sender_chat_id=sender_chat_id):
            return await handler(event, data)

        # 2. Check group force_sub settings
        group_config = await group_service.get_or_register_group(
            chat_id,
            title=event.chat.title or "",
            chat=event.chat,
            bot=bot
        )
        fsub_conf = group_config.get("force_sub", {})
        if not fsub_conf.get("is_enabled", False):
            return await handler(event, data)

        channels = fsub_conf.get("channels", [])
        if not channels:
            return await handler(event, data)

        # 3. Verify user subscription
        is_sub, missing = await subscription_service.verify_user_subscriptions(
            bot=bot,
            channels=channels,
            user_id=user_id,
            force_fresh=False
        )

        if not is_sub:
            # Delete the user's message
            await moderation_service.delete_message(bot, chat_id, event.message_id)

            # Send subscription notification
            keyboard = get_force_sub_user_keyboard(channels, chat_id)
            user_name = event.from_user.first_name or "Foydalanuvchi"
            text = (
                f"👋 Hurmatli <b>{user_name}</b>!\n\n"
                f"Guruhda xabar yozish uchun quyidagi homiy kanallarga a'zo bo'lishingiz shart.\n"
                f"A'zo bo'lgach, <b>Obunani tekshirish</b> tugmasini bosing:"
            )
            try:
                sent = await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.debug(f"Could not send force sub notice in {chat_id}: {e}")

            # Stop propagation of this message
            return None

        return await handler(event, data)
