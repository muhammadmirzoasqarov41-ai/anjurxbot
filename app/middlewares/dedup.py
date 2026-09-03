"""Drop duplicate Telegram updates before feature middleware runs."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Update

from app.services.dedup_service import update_dedup_service


class UpdateDedupMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        if not update_dedup_service.first_seen(event.update_id):
            return None
        return await handler(event, data)