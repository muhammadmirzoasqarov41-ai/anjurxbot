"""
Rate Limiting Middleware.
Throttles user commands and callback queries.
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from app.services.rate_limit_service import rate_limit_service


class RateLimitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        action_name = "general"

        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            action_name = "message"
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
            action_name = f"cb_{event.data.split(':')[0] if event.data else 'cb'}"

        if user_id:
            is_limited, wait_sec = rate_limit_service.is_rate_limited(action_name, user_id)
            if is_limited:
                if isinstance(event, CallbackQuery):
                    await event.answer(f"Iltimos, {wait_sec} soniya kuting!", show_alert=True)
                return None

        return await handler(event, data)
