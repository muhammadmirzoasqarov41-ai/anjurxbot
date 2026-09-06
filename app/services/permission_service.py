"""
Permission Service.
Normalizes member status, caches permissions, and checks administrative privileges.
"""
import time
import logging
from typing import Dict, Tuple, Optional
from aiogram import Bot
from app.config import config

logger = logging.getLogger("anjurxbot.permissions")


class PermissionService:
    def __init__(self):
        # Cache format: (group_id, user_id) -> (status, timestamp)
        self._status_cache: Dict[Tuple[int, int], Tuple[str, float]] = {}
        # Bot admin cache: group_id -> (is_admin, can_delete, can_restrict, timestamp)
        self._bot_admin_cache: Dict[int, Tuple[bool, bool, bool, float]] = {}

    def normalize_member_status(self, status: str) -> str:
        """
        Normalize member status strings.
        Maps 'creator' -> 'administrator' for uniform admin checks.
        """
        st = (status or "").lower().strip()
        if st in ("creator", "administrator", "admin", "owner"):
            return "administrator"
        if st in ("member", "restricted", "left", "kicked"):
            return st
        return "member"

    async def is_user_admin(self, bot: Bot, group_id: int, user_id: int) -> bool:
        """Check if a user is an administrator or owner of the given group."""
        # Global bot admins always pass
        if config.is_admin(user_id):
            return True

        now = time.time()
        key = (group_id, user_id)
        if key in self._status_cache:
            status, cached_time = self._status_cache[key]
            if now - cached_time < config.cache_ttl_member_status:
                return status == "administrator"

        try:
            member = await bot.get_chat_member(chat_id=group_id, user_id=user_id)
            normalized = self.normalize_member_status(member.status)
            self._status_cache[key] = (normalized, now)
            return normalized == "administrator"
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=is_user_admin group_id={group_id} user_id={user_id}")
            return False

    async def get_bot_permissions(self, bot: Bot, group_id: int) -> Tuple[bool, bool, bool]:
        """
        Returns (is_admin, can_delete_messages, can_restrict_members)
        """
        now = time.time()
        if group_id in self._bot_admin_cache:
            is_adm, can_del, can_rst, cached_time = self._bot_admin_cache[group_id]
            if now - cached_time < config.cache_ttl_member_status:
                return (is_adm, can_del, can_rst)

        try:
            bot_member = await bot.get_chat_member(chat_id=group_id, user_id=bot.id)
            is_adm = bot_member.status in ("administrator", "creator")
            can_del = getattr(bot_member, "can_delete_messages", False) or False
            can_rst = getattr(bot_member, "can_restrict_members", False) or False
            result = (is_adm, can_del, can_rst)
            self._bot_admin_cache[group_id] = (is_adm, can_del, can_rst, now)
            return result
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=get_bot_permissions group_id={group_id}")
            return (False, False, False)

    def invalidate_user_cache(self, group_id: int, user_id: int) -> None:
        self._status_cache.pop((group_id, user_id), None)

    def invalidate_group_cache(self, group_id: int) -> None:
        self._bot_admin_cache.pop(group_id, None)
        keys_to_remove = [k for k in self._status_cache if k[0] == group_id]
        for k in keys_to_remove:
            self._status_cache.pop(k, None)


permission_service = PermissionService()
