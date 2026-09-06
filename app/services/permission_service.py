"""
Permission Service.
Normalizes member status, caches permissions, and checks administrative privileges using Telegram user_id.
"""
import time
import logging
from typing import Dict, Tuple, Optional, List, Any
from aiogram import Bot
from app.config import config

logger = logging.getLogger("anjurxbot.permissions")


class PermissionService:
    def __init__(self):
        # Cache format: (group_id, user_id) -> (role, timestamp)
        # Roles: "OWNER", "ADMIN", "MEMBER"
        self._role_cache: Dict[Tuple[int, int], Tuple[str, float]] = {}
        # Bot admin cache: group_id -> (is_admin, can_delete, can_restrict, timestamp)
        self._bot_admin_cache: Dict[int, Tuple[bool, bool, bool, float]] = {}

    def normalize_member_status(self, status: str) -> str:
        """
        Normalize member status strings.
        Maps 'creator' -> 'administrator' for backward-compatible admin checks.
        """
        st = (status or "").lower().strip()
        if st in ("creator", "administrator", "admin", "owner"):
            return "administrator"
        if st in ("member", "restricted", "left", "kicked"):
            return st
        return "member"

    def normalize_role(self, status: str) -> str:
        """
        Normalize member status to specific roles:
        'creator' -> 'OWNER'
        'administrator' -> 'ADMIN'
        'member' / other -> 'MEMBER'
        """
        st = (status or "").lower().strip()
        if st in ("creator", "owner"):
            return "OWNER"
        if st in ("administrator", "admin"):
            return "ADMIN"
        return "MEMBER"

    async def get_user_role(
        self,
        bot: Bot,
        group_id: int,
        user_id: int,
        sender_chat_id: Optional[int] = None
    ) -> str:
        """
        Returns the exact role of the user: 'OWNER', 'ADMIN', or 'MEMBER'.
        Uses Telegram user_id as the primary identifier.
        """
        if config.is_admin(user_id):
            return "ADMIN"

        # Telegram supergroup anonymous admin check
        if sender_chat_id and sender_chat_id == group_id:
            return "ADMIN"

        now = time.time()
        key = (group_id, user_id)
        if key in self._role_cache:
            role, cached_time = self._role_cache[key]
            if now - cached_time < config.cache_ttl_member_status:
                return role

        try:
            member = await bot.get_chat_member(chat_id=group_id, user_id=user_id)
            role = self.normalize_role(member.status)
            self._role_cache[key] = (role, now)
            return role
        except Exception as e:
            logger.error(
                f"error_type={type(e).__name__} action=get_user_role group_id={group_id} user_id={user_id} error={e}"
            )
            return "MEMBER"

    async def is_user_admin(
        self,
        bot: Bot,
        group_id: int,
        user_id: int,
        sender_chat_id: Optional[int] = None
    ) -> bool:
        """Check if a user is an administrator or owner of the given group."""
        role = await self.get_user_role(bot, group_id, user_id, sender_chat_id=sender_chat_id)
        return role in ("OWNER", "ADMIN")

    async def is_user_owner(self, bot: Bot, group_id: int, user_id: int) -> bool:
        """Check if a user is the primary creator/owner of the given group."""
        if config.is_admin(user_id):
            return True
        role = await self.get_user_role(bot, group_id, user_id)
        return role == "OWNER"

    async def sync_group_administrators(
        self,
        bot: Bot,
        group_id: int
    ) -> Tuple[Optional[int], Optional[Dict[str, Any]], List[Dict[str, Any]], List[int]]:
        """
        Calls Telegram get_chat_administrators to obtain the real group owner and admin list.
        Returns (owner_id, owner_dict, admins_list, admin_ids_list).
        """
        now = time.time()
        owner_id: Optional[int] = None
        owner_data: Optional[Dict[str, Any]] = None
        admins_list: List[Dict[str, Any]] = []
        admin_ids: List[int] = []

        try:
            administrators = await bot.get_chat_administrators(chat_id=group_id)
            for m in administrators:
                u = m.user
                u_id = u.id
                status = getattr(m, "status", "administrator")
                is_creator = (status == "creator")
                role = "OWNER" if is_creator else "ADMIN"

                # Update role cache
                self._role_cache[(group_id, u_id)] = (role, now)

                admin_entry = {
                    "user_id": u_id,
                    "username": u.username,
                    "first_name": u.first_name or "",
                    "last_name": u.last_name or "",
                    "status": status,
                    "is_owner": is_creator,
                    "is_bot": u.is_bot,
                    "custom_title": getattr(m, "custom_title", None) or None,
                    "can_delete_messages": getattr(m, "can_delete_messages", False) or False,
                    "can_restrict_members": getattr(m, "can_restrict_members", False) or False,
                }
                admins_list.append(admin_entry)
                if not u.is_bot:
                    admin_ids.append(u_id)

                if is_creator:
                    owner_id = u_id
                    owner_data = {
                        "user_id": u_id,
                        "username": u.username,
                        "first_name": u.first_name or "",
                        "last_name": u.last_name or "",
                        "is_bot": u.is_bot,
                    }

            return (owner_id, owner_data, admins_list, admin_ids)
        except Exception as e:
            logger.error(
                f"error_type={type(e).__name__} action=sync_group_administrators group_id={group_id} error={e}"
            )
            return (None, None, [], [])

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
            logger.error(f"error_type={type(e).__name__} action=get_bot_permissions group_id={group_id} error={e}")
            return (False, False, False)

    def invalidate_user_cache(self, group_id: int, user_id: int) -> None:
        self._role_cache.pop((group_id, user_id), None)

    def invalidate_group_cache(self, group_id: int) -> None:
        self._bot_admin_cache.pop(group_id, None)
        keys_to_remove = [k for k in self._role_cache if k[0] == group_id]
        for k in keys_to_remove:
            self._role_cache.pop(k, None)


permission_service = PermissionService()
