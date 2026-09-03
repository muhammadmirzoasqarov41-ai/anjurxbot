"""Dispatcher-level rate limiting for callback queries."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

from app.services.rate_limit_service import rate_limit_service


class CallbackRateLimitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        if event.from_user and not rate_limit_service.allow_callback(event.from_user.id):
            await event.answer("⏳ Juda ko'p so'rov yuborildi. Biroz kuting.", show_alert=True)
            return None
        return await handler(event, data)