"""
Guard Middleware.
Executes spam, flood, link, ads, and profanity checks on incoming group messages.
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message

from app.services.group_service import group_service
from app.services.guard_service import guard_service


class GuardMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message) or not event.chat or not event.from_user:
            return await handler(event, data)

        # Only apply in groups
        if event.chat.type not in ("group", "supergroup"):
            return await handler(event, data)

        # Ignore bots
        if event.from_user.is_bot:
            return await handler(event, data)

        bot: Bot = data.get("bot")
        if not bot:
            return await handler(event, data)

        chat_id = event.chat.id
        group_config = await group_service.get_or_register_group(
            chat_id,
            title=event.chat.title or "",
            chat=event.chat,
            bot=bot
        )

        # Execute guard checks
        is_violation = await guard_service.process_message(bot, event, group_config)
        if is_violation:
            # Violation handled; stop downstream message handlers
            return None

        return await handler(event, data)
