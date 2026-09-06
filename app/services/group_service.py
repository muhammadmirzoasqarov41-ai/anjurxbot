"""
Group Service for managing group registration and cached configurations.
"""
import time
import logging
from typing import Dict, Any, Optional
from app.config import config
from app.services.firebase import firebase_service

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

    async def get_or_register_group(self, group_id: int, title: str = "") -> Dict[str, Any]:
        """Fetch group settings from cache or database; register with defaults if not present."""
        now = time.time()
        if group_id in self._cache:
            data, ts = self._cache[group_id]
            if now - ts < config.cache_ttl_group_config:
                return data

        group_doc = await firebase_service.get_group(group_id)
        if not group_doc:
            group_doc = {
                "group_id": group_id,
                "title": title,
                "is_active": True,
                "guard_settings": dict(DEFAULT_GUARD_SETTINGS),
                "force_sub": dict(DEFAULT_FSUB_SETTINGS),
            }
            await firebase_service.save_group(group_id, group_doc)
        else:
            # Ensure missing default fields exist
            updated = False
            if "guard_settings" not in group_doc:
                group_doc["guard_settings"] = dict(DEFAULT_GUARD_SETTINGS)
                updated = True
            if "force_sub" not in group_doc:
                group_doc["force_sub"] = dict(DEFAULT_FSUB_SETTINGS)
                updated = True
            if title and group_doc.get("title") != title:
                group_doc["title"] = title
                updated = True
            if updated:
                await firebase_service.save_group(group_id, group_doc)

        self._cache[group_id] = (group_doc, now)
        return group_doc

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
