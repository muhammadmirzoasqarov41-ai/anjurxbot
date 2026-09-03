"""Telegram bot membership and permission verification service."""

from __future__ import annotations

import datetime
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.services import group_service
from app.services.firebase import firebase_service
from app.utils.logger import logger

_ADMIN_STATUSES = {"administrator", "creator"}


def normalize_member_status(member: Any) -> str:
    """Return the canonical Telegram status for enum or string responses."""
    raw_status = getattr(member, "status", "")
    value = getattr(raw_status, "value", raw_status)
    normalized = str(value).rsplit(".", 1)[-1].lower()
    if normalized in _ADMIN_STATUSES:
        return normalized
    class_name = type(member).__name__.lower()
    if "creator" in class_name or "owner" in class_name:
        return "creator"
    if "administrator" in class_name or "admin" in class_name:
        return "administrator"
    return normalized


class PermissionService:
    """Centralises getChatMember checks and persists the bot health state."""

    async def verify_bot(self, bot: Bot, group_id: int) -> dict[str, Any]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result: dict[str, Any] = {
            "bot_status": "unknown",
            "is_active": False,
            "permissions_valid": False,
            "permissions": {
                "can_delete_messages": False,
                "can_restrict_members": False,
            },
            "last_verified_at": now,
        }
        try:
            me = await bot.get_me()
            member = await bot.get_chat_member(chat_id=group_id, user_id=me.id)
            status = normalize_member_status(member)
            result["bot_status"] = status
            if status in _ADMIN_STATUSES:
                is_creator = status == "creator"
                permissions = {
                    "can_delete_messages": is_creator or bool(getattr(member, "can_delete_messages", False)),
                    "can_restrict_members": is_creator or bool(getattr(member, "can_restrict_members", False)),
                }
                result["permissions"] = permissions
                result["permissions_valid"] = all(permissions.values())
                result["is_active"] = True
            elif status in {"member", "restricted"}:
                result["is_active"] = True
        except TelegramAPIError as exc:
            logger.warning("Permission check failed for group %s: %s", group_id, exc)
            result["bot_status"] = "error"
        except Exception as exc:
            logger.error("Unexpected permission check error for group %s: %s", group_id, exc)

        await firebase_service.update_group(group_id, result)
        group_service._cache_invalidate(group_id)
        return result

    async def is_group_admin(self, bot: Bot, group_id: int, user_id: int) -> bool:
        """Return whether a Telegram user is a creator or administrator."""
        try:
            member = await bot.get_chat_member(chat_id=group_id, user_id=user_id)
            return normalize_member_status(member) in _ADMIN_STATUSES
        except TelegramAPIError as exc:
            logger.warning(
                "Group admin check failed group=%s user=%s: %s",
                group_id,
                user_id,
                exc.__class__.__name__,
            )
            return False
        except Exception as exc:
            logger.error(
                "Unexpected group admin check error group=%s user=%s: %s",
                group_id,
                user_id,
                exc.__class__.__name__,
            )
            return False


permission_service = PermissionService()


async def verify_bot_permissions(bot: Bot, group_id: int) -> dict[str, Any]:
    return await permission_service.verify_bot(bot, group_id)


async def is_group_admin(bot: Bot, group_id: int, user_id: int) -> bool:
    return await permission_service.is_group_admin(bot, group_id, user_id)