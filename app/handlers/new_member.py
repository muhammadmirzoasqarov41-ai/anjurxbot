"""
New member event handler.

Listens for new_chat_members events (users joining a group).
When new_member_protection is enabled, records the join time so the
GuardMiddleware can apply awareness during the new-member window.

This handler does NOT send a welcome message — the sole purpose is
tracking join time for the new_member_protection guard feature.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import ChatMemberUpdated, Message

from app.services import guard_service
from app.services.new_member_service import mark_new_member
from app.utils.logger import logger

router = Router(name="new_member")

_GROUP_TYPES = {"group", "supergroup"}


@router.message(F.new_chat_members)
async def handle_new_chat_members(message: Message) -> None:
    """
    Triggered when one or more users join the group.

    Records each new member's join timestamp in the in-memory cache
    so the guard middleware can enforce extra scrutiny during their
    first _NEW_MEMBER_WINDOW seconds.
    """
    if message.chat.type not in _GROUP_TYPES:
        return

    chat_id = message.chat.id

    # Check if new_member_protection is enabled for this group
    try:
        guard = await guard_service.get_guard_settings(chat_id)
    except Exception as exc:
        logger.error(
            "Failed to load guard settings for new member check in %s: %s",
            chat_id, exc,
        )
        return

    if not guard.get("enabled", False):
        return

    if not guard.get("new_member_protection", True):
        return

    # Record each new member
    new_members = message.new_chat_members or []
    for member in new_members:
        if member.is_bot:
            continue  # Don't track bots
        mark_new_member(chat_id, member.id)
        logger.info(
            "NEW_MEMBER_JOINED group=%s user=%s username=%s",
            chat_id, member.id, member.username or "no_username",
        )
