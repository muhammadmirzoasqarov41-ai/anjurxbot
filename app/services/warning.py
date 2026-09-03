"""Public warning service API for handlers and future user management UI."""

from app.services.punishment_service import (
    clear_warnings,
    get_warning_history,
    get_warnings,
    warn_user,
)

__all__ = ["get_warnings", "add_warning", "clear_warnings", "get_user_moderation_history"]


async def add_warning(*args, **kwargs):
    return await warn_user(*args, **kwargs)


async def get_user_moderation_history(chat_id: int, user_id: int, limit: int = 10):
    return await get_warning_history(chat_id, user_id, limit)