"""
Group Service for managing group registration, real owner/admin synchronization, and Firestore persistence.
Focused purely on Qorovul Group Guard and Protection architecture.
"""
import time
import logging
from typing import Dict, Any, Optional, List
from aiogram import Bot
from aiogram.types import Chat
from app.config import config
from app.services.firebase import firebase_service
from app.services.permission_service import permission_service
from app.services.bad_words_data import ALL_DEFAULT_BAD_WORDS

logger = logging.getLogger("anjurxbot.group_service")

DEFAULT_GUARD_SETTINGS = {
    "anti_link": True,
    "anti_spam": True,
    "anti_flood": True,
    "anti_ads": True,
    "anti_repeat": True,
    "bad_words_filter": True,
    "bad_words_action": "delete",  # 'delete', 'warn', 'mute'
    "raid_protection": True,
    "raid_threshold": 10,
    "new_member_protection": True,
    "new_member_duration": 300,
    "allowed_domains": ["youtube.com", "youtu.be", "instagram.com", "github.com", "google.com"],
    "whitelist_words": [],
    "flood_limit": 5,
    "flood_window": 5,
    "warn_limit": 3,
    "punishment": "mute",  # 'mute', 'kick', 'ban'
    "mute_duration": 900,  # 15 minutes
    "delete_service_messages": True,
    "bad_words": list(ALL_DEFAULT_BAD_WORDS),
}

DEFAULT_MODERATION_STATS = {
    "spam": 0,
    "flood": 0,
    "link": 0,
    "ads": 0,
    "warn": 0,
    "mute": 0,
    "ban": 0,
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

        chat_title = title or (chat.title if chat and hasattr(chat, "title") else "")
        chat_username = chat.username if chat and hasattr(chat, "username") else None
        chat_type = chat.type if chat and hasattr(chat, "type") else "supergroup"

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
                "moderation_stats": dict(DEFAULT_MODERATION_STATS),
            }

            if bot:
                await self._populate_telegram_metadata(bot, group_id, group_doc, chat=chat)

            save_ok = await firebase_service.save_group(group_id, group_doc)
            logger.info(
                f"GROUP_REGISTERED chat_id={group_id} chat_type={group_doc.get('type')} "
                f"title='{group_doc.get('title')}' owner_id={group_doc.get('owner_id')} "
                f"admins_count={len(group_doc.get('admins', []))} firebase_group_saved={save_ok}"
            )
        else:
            # Ensure schema completeness
            updated = False
            if "guard_settings" not in group_doc:
                group_doc["guard_settings"] = dict(DEFAULT_GUARD_SETTINGS)
                updated = True
            else:
                current_words = group_doc["guard_settings"].get("bad_words", [])
                if not current_words or len(current_words) < 10:
                    # Upgrade to comprehensive list preserving existing custom words
                    merged_words = list(dict.fromkeys(list(current_words) + list(ALL_DEFAULT_BAD_WORDS)))
                    group_doc["guard_settings"]["bad_words"] = merged_words
                    updated = True

            if "moderation_stats" not in group_doc:
                group_doc["moderation_stats"] = dict(DEFAULT_MODERATION_STATS)
                updated = True

            if chat_title and group_doc.get("title") != chat_title:
                group_doc["title"] = chat_title
                updated = True
            if chat_username and group_doc.get("username") != chat_username:
                group_doc["username"] = chat_username
                updated = True

            # If missing owner_id or admin list or force_refresh is requested, sync with Telegram
            needs_metadata_sync = (
                force_refresh or
                not group_doc.get("owner_id") or
                not group_doc.get("admins")
            )
            if bot and needs_metadata_sync:
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
        """Helper to fetch real owner, administrators, and member counts from Telegram API."""
        try:
            tg_chat = chat or await bot.get_chat(group_id)
            if tg_chat:
                if hasattr(tg_chat, "title") and tg_chat.title:
                    group_doc["title"] = tg_chat.title
                if hasattr(tg_chat, "username") and tg_chat.username:
                    group_doc["username"] = tg_chat.username
                if hasattr(tg_chat, "type") and tg_chat.type:
                    group_doc["type"] = str(tg_chat.type)
        except Exception as e:
            logger.debug(f"Could not get chat info for group {group_id}: {e}")

        try:
            admins_list = await bot.get_chat_administrators(group_id)
            admin_dicts = []
            admin_ids = []
            owner_info = None

            for admin in admins_list:
                user = admin.user
                is_creator = admin.status == "creator"
                admin_entry = {
                    "user_id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "is_bot": user.is_bot,
                    "custom_title": getattr(admin, "custom_title", None),
                    "status": admin.status,
                    "is_creator": is_creator,
                }
                admin_dicts.append(admin_entry)
                admin_ids.append(user.id)

                if is_creator:
                    owner_info = {
                        "user_id": user.id,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "username": user.username,
                    }
                    group_doc["owner_id"] = user.id
                    group_doc["owner"] = owner_info

            group_doc["admins"] = admin_dicts
            group_doc["admin_ids"] = admin_ids

            # Seed permission cache with verified admin IDs
            permission_service.set_cached_admins(group_id, admin_ids)
        except Exception as e:
            logger.warning(f"Could not fetch chat administrators for group {group_id}: {e}")

        try:
            count = await bot.get_chat_member_count(group_id)
            group_doc["members_count"] = count
        except Exception as e:
            logger.debug(f"Could not get member count for group {group_id}: {e}")

        try:
            bot_member = await bot.get_chat_member(group_id, bot.id)
            group_doc["bot_status"] = bot_member.status
            group_doc["is_active"] = bot_member.status in ("administrator", "member")
        except Exception as e:
            logger.debug(f"Could not get bot member status in group {group_id}: {e}")

        return True

    async def sync_group_admins(
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
        logger.info(f"GROUP_SETTINGS_UPDATED group_id={group_id} key=guard_settings.{key} value={value} success={success}")
        return success

    async def increment_group_stat(self, group_id: int, metric: str, count: int = 1) -> bool:
        """Increments specific group moderation metric in Firestore."""
        group = await self.get_or_register_group(group_id)
        stats = group.setdefault("moderation_stats", dict(DEFAULT_MODERATION_STATS))
        current = stats.get(metric, 0)
        stats[metric] = current + count
        success = await firebase_service.update_group_settings(group_id, f"moderation_stats.{metric}", stats[metric])
        self._cache[group_id] = (group, time.time())
        return success

    def invalidate_cache(self, group_id: int) -> None:
        self._cache.pop(group_id, None)


group_service = GroupService()
