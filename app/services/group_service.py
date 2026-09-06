"""
Group Service for managing group registration, real owner/admin synchronization, and Firestore persistence.
"""
import time
import logging
from typing import Dict, Any, Optional, List
from aiogram import Bot
from aiogram.types import Chat
from app.config import config
from app.services.firebase import firebase_service
from app.services.permission_service import permission_service

logger = logging.getLogger("anjurxbot.group_service")

DEFAULT_GUARD_SETTINGS = {
    "anti_link": True,
    "anti_spam": True,
    "anti_flood": True,
    "anti_ads": True,
    "anti_repeat": True,
    "bad_words_filter": True,
    "flood_limit": 5,
    "flood_window": 5,
    "warn_limit": 3,
    "punishment": "mute",  # 'mute', 'kick', 'ban'
    "bad_words": [
        "ahmoq", "tentak", "haromi", "iflos", "jalap", "it", "chochqa"
    ],
}

DEFAULT_FSUB_SETTINGS = {
    "is_enabled": False,
    "channels": [],  # list of {"channel_id": int/str, "title": str, "invite_link": str}
}


class GroupService:
    def __init__(self):
        # Cache format: group_id -> (config_dict, cached_timestamp)
        self._cache: Dict[int, tuple[Dict[str, Any], float]] = {}

    async def get_or_register_group(
        self,
        group_id: int,
        title: str = "",
        chat: Optional[Chat] = None,
        bot: Optional[Bot] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch group settings from cache or database; register with full Telegram metadata if not present.
        If bot is provided and group is missing owner or admins, automatically syncs with Telegram API.
        """
        now = time.time()
        if not force_refresh and group_id in self._cache:
            data, ts = self._cache[group_id]
            # If cached data is fresh and already has owner/admins synced, return it
            if now - ts < config.cache_ttl_group_config and data.get("owner_id"):
                return data

        group_doc = await firebase_service.get_group(group_id)
        chat_type = getattr(chat, "type", "supergroup") if chat else "supergroup"
        chat_username = getattr(chat, "username", None) if chat else None
        chat_title = title or (getattr(chat, "title", "") if chat else "") or f"Group {group_id}"

        if not group_doc:
            group_doc = {
                "group_id": int(group_id),
                "chat_id": int(group_id),
                "title": chat_title,
                "username": chat_username,
                "type": chat_type,
                "owner_id": None,
                "owner": None,
                "admins": [],
                "admin_ids": [],
                "members_count": 0,
                "is_active": True,
                "bot_status": "member",
                "guard_settings": dict(DEFAULT_GUARD_SETTINGS),
                "force_sub": dict(DEFAULT_FSUB_SETTINGS),
            }

            if bot:
                await self._populate_telegram_metadata(bot, group_id, group_doc, chat=chat)

            save_ok = await firebase_service.save_group(group_id, group_doc)
            logger.info(
                f"GROUP DETECTED chat_id={group_id} chat_type={group_doc.get('type')} "
                f"title='{group_doc.get('title')}' owner_id={group_doc.get('owner_id')} "
                f"admins_count={len(group_doc.get('admins', []))} firebase_group_saved={save_ok}"
            )
        else:
            # Ensure schema completeness
            updated = False
            if "guard_settings" not in group_doc:
                group_doc["guard_settings"] = dict(DEFAULT_GUARD_SETTINGS)
                updated = True
            if "force_sub" not in group_doc:
                group_doc["force_sub"] = dict(DEFAULT_FSUB_SETTINGS)
                updated = True
            if chat_title and group_doc.get("title") != chat_title:
                group_doc["title"] = chat_title
                updated = True
            if chat_username and group_doc.get("username") != chat_username:
                group_doc["username"] = chat_username
                updated = True

            # If missing owner_id or admin list or force_refresh is requested, sync with Telegram
            if bot and (force_refresh or not group_doc.get("owner_id") or not group_doc.get("admins")):
                synced = await self._populate_telegram_metadata(bot, group_id, group_doc, chat=chat)
                if synced:
                    updated = True

            if updated:
                await firebase_service.save_group(group_id, group_doc)

        self._cache[group_id] = (group_doc, now)
        return group_doc

    async def _populate_telegram_metadata(
        self,
        bot: Bot,
        group_id: int,
        group_doc: Dict[str, Any],
        chat: Optional[Chat] = None
    ) -> bool:
        """Helper to sync real owner, admin list, member count and bot status from Telegram."""
        try:
            owner_id, owner_data, admins_list, admin_ids = await permission_service.sync_group_administrators(
                bot, group_id
            )
            if owner_id:
                group_doc["owner_id"] = owner_id
                group_doc["owner"] = owner_data
            if admins_list:
                group_doc["admins"] = admins_list
                group_doc["admin_ids"] = admin_ids

            # Check bot's own status
            try:
                bot_member = await bot.get_chat_member(chat_id=group_id, user_id=bot.id)
                bot_status = bot_member.status
                group_doc["bot_status"] = bot_status
                group_doc["is_active"] = bot_status not in ("left", "kicked")
            except Exception:
                pass

            # Fetch members count
            try:
                count = await bot.get_chat_member_count(chat_id=group_id)
                group_doc["members_count"] = count
            except Exception:
                pass

            if chat:
                if chat.title:
                    group_doc["title"] = chat.title
                if chat.username:
                    group_doc["username"] = chat.username
                if chat.type:
                    group_doc["type"] = chat.type

            return True
        except Exception as e:
            logger.error(
                f"error_type={type(e).__name__} action=_populate_telegram_metadata group_id={group_id} error={e}"
            )
            return False

    async def sync_and_save_administrators(
        self,
        bot: Bot,
        group_id: int,
        chat: Optional[Chat] = None
    ) -> Dict[str, Any]:
        """Directly syncs administrators and updates Firestore and internal cache."""
        group_doc = await self.get_or_register_group(group_id, chat=chat, bot=bot, force_refresh=True)
        return group_doc

    async def mark_group_status(self, group_id: int, is_active: bool, bot_status: str) -> bool:
        """Update group active and bot membership status."""
        self.invalidate_cache(group_id)
        permission_service.invalidate_group_cache(group_id)
        group = await firebase_service.get_group(group_id)
        if group:
            group["is_active"] = is_active
            group["bot_status"] = bot_status
            return await firebase_service.save_group(group_id, group)
        return False

    async def update_guard_setting(self, group_id: int, key: str, value: Any) -> bool:
        group = await self.get_or_register_group(group_id)
        guard = group.setdefault("guard_settings", dict(DEFAULT_GUARD_SETTINGS))
        guard[key] = value
        success = await firebase_service.update_group_settings(group_id, f"guard_settings.{key}", value)
        self._cache[group_id] = (group, time.time())
        return success

    async def update_fsub_setting(self, group_id: int, key: str, value: Any) -> bool:
        group = await self.get_or_register_group(group_id)
        fsub = group.setdefault("force_sub", dict(DEFAULT_FSUB_SETTINGS))
        fsub[key] = value
        success = await firebase_service.update_group_settings(group_id, f"force_sub.{key}", value)
        self._cache[group_id] = (group, time.time())
        return success

    def invalidate_cache(self, group_id: int) -> None:
        self._cache.pop(group_id, None)


group_service = GroupService()
