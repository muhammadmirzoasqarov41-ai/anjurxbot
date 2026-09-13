"""
Permission and Authorization Service for AnjurX | Rss Bot.
Handles:
- Strict numeric Telegram user_id Super Admin validation (independent of username)
- Channel/Group destination administrative permission checks
- Bot channel posting capabilities detection (can_post_messages)
"""
import time
import logging
from typing import Dict, Tuple, Optional, Any
from aiogram import Bot
from app.config import config

logger = logging.getLogger("anjurxbot.permissions")


def is_super_admin(user_id: Optional[int]) -> bool:
    """
    Canonical Super Admin check for the entire application.
    Security rules:
    - Granted solely by Telegram numeric User ID, NEVER by username.
    - Telegram username changing preserves super-admin rights.
    """
    return config.is_super_admin(user_id)


class PermissionService:
    def __init__(self):
        # Cache for user permissions in chats: (chat_id, user_id) -> (is_admin, timestamp)
        self._user_perm_cache: Dict[Tuple[int, int], Tuple[bool, float]] = {}
        # Cache for bot permissions in channels/chats: chat_id -> (can_post, is_admin, timestamp)
        self._bot_perm_cache: Dict[int, Tuple[bool, bool, float]] = {}
        self._cache_ttl = 120.0  # 2 minutes

    def is_super_admin(self, user_id: Optional[int]) -> bool:
        """Helper delegation to canonical is_super_admin."""
        return is_super_admin(user_id)

    async def can_user_manage_chat(self, bot: Bot, chat_id: int, user_id: int) -> bool:
        """
        Determines if a user has authority to connect or manage destinations.
        - Super Admins have global authority over all chats/channels.
        - In private chat (chat_id > 0), user manages their own chat.
        - In channels/groups (chat_id < 0), user must be creator or administrator.
        """
        if is_super_admin(user_id):
            return True

        if chat_id > 0:
            return chat_id == user_id

        # Channel or group
        now = time.time()
        cache_key = (chat_id, user_id)
        if cache_key in self._user_perm_cache:
            is_adm, cached_at = self._user_perm_cache[cache_key]
            if now - cached_at < self._cache_ttl:
                return is_adm

        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            is_adm = member.status in ("creator", "administrator")
            self._user_perm_cache[cache_key] = (is_adm, now)
            return is_adm
        except Exception as e:
            logger.warning(f"Could not verify chat member privileges for user {user_id} in {chat_id}: {e}")
            return False

    async def check_bot_channel_permissions(self, bot: Bot, chat_id: int) -> Dict[str, Any]:
        """
        Verifies bot's presence and posting permissions in a target channel.
        Returns:
            {
                "chat_id": int,
                "title": str,
                "username": Optional[str],
                "type": str,
                "is_admin": bool,
                "can_post": bool,
                "error": Optional[str]
            }
        """
        try:
            chat = await bot.get_chat(chat_id=chat_id)
            title = chat.title or f"Chat {chat_id}"
            username = chat.username
            chat_type = chat.type

            # For private chats, bot can always send messages unless blocked
            if chat_type == "private":
                return {
                    "chat_id": chat_id,
                    "title": title,
                    "username": username,
                    "type": chat_type,
                    "is_admin": True,
                    "can_post": True,
                    "error": None
                }

            # For channels and groups, inspect bot's member object
            bot_member = await bot.get_chat_member(chat_id=chat_id, user_id=bot.id)
            status = bot_member.status
            is_admin = status in ("administrator", "creator")

            # In channels, check can_post_messages
            can_post = False
            if is_admin:
                if chat_type == "channel":
                    can_post = getattr(bot_member, "can_post_messages", False) is True
                else:
                    # In groups/supergroups, admins can typically post unless restricted
                    can_post = True
            
            return {
                "chat_id": chat_id,
                "title": title,
                "username": username,
                "type": chat_type,
                "is_admin": is_admin,
                "can_post": can_post,
                "error": None if can_post else (
                    "Bot kanalda post yubora olmaydi. Botni administrator qilib, 'Post Messages' huquqini bering."
                    if not is_admin or not can_post else None
                )
            }
        except Exception as e:
            err_msg = str(e)
            logger.warning(f"Permission check failed for bot in chat {chat_id}: {err_msg}")
            return {
                "chat_id": chat_id,
                "title": f"Chat {chat_id}",
                "username": None,
                "type": "channel",
                "is_admin": False,
                "can_post": False,
                "error": err_msg
            }

    def invalidate_cache(self, chat_id: Optional[int] = None, user_id: Optional[int] = None):
        """Clears permission cache for target chat or user."""
        if chat_id and user_id:
            self._user_perm_cache.pop((chat_id, user_id), None)
        elif chat_id:
            self._bot_perm_cache.pop(chat_id, None)
            keys = [k for k in self._user_perm_cache if k[0] == chat_id]
            for k in keys:
                self._user_perm_cache.pop(k, None)
        else:
            self._user_perm_cache.clear()
            self._bot_perm_cache.clear()


permission_service = PermissionService()
