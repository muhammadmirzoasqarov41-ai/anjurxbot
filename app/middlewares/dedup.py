"""
Deduplication Middleware.
Prevents duplicate update processing in Telegram polling.
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from app.services.dedup_service import dedup_service


class DedupMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Update):
            update_key = f"up_{event.update_id}"
            if dedup_service.is_duplicate(update_key):
                return None
        return await handler(event, data)
