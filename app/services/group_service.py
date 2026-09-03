"""
Group domain service — business logic layer between handlers and Firestore.

All Force Subscribe related database operations live here.
Handlers should call these functions, not touch firebase_service directly.

Firestore document layout:
    groups/{chat_id}
    {
        "chat_id": -1001234567890,
        "title": "My Group",
        "added_at": <timestamp>,
        "force_subscribe": {
            "enabled": true,
            "channels": [
                {
                    "channel_id": -1001111111111,   # int (canonical key)
                    "username": "@mychannel",        # str or ""
                    "invite_link": "https://t.me/…", # str or ""
                    "title": "My Channel"            # str
                },
                ...
            ]
        }
    }
"""

from __future__ import annotations

import time
from typing import Any, Optional

from app.services.firebase import firebase_service
from app.utils.logger import logger

# ------------------------------------------------------------------ #
# Simple in-memory cache for group settings
# TTL: 60 seconds — short enough to reflect admin changes quickly,
# long enough to reduce Firestore reads on busy groups.
# ------------------------------------------------------------------ #
_CACHE_TTL = 60  # seconds

_cache: dict[int, tuple[Optional[dict[str, Any]], float]] = {}


def _cache_set(group_id: int, data: Optional[dict[str, Any]]) -> None:
    _cache[group_id] = (data, time.monotonic())


def _cache_get(group_id: int) -> tuple[bool, Optional[dict[str, Any]]]:
    """Return (hit, data). hit=False means cache miss or expired."""
    entry = _cache.get(group_id)
    if entry is None:
        return False, None
    data, ts = entry
    if time.monotonic() - ts > _CACHE_TTL:
        return False, None
    return True, data


def _cache_invalidate(group_id: int) -> None:
    _cache.pop(group_id, None)


# ------------------------------------------------------------------ #
# Public API
# ------------------------------------------------------------------ #

async def get_group(group_id: int) -> Optional[dict[str, Any]]:
    """
    Return the group document from Firestore (with cache).

    Returns None if the group has never been registered.
    """
    hit, cached = _cache_get(group_id)
    if hit:
        return cached

    data = await firebase_service.get_group(group_id)
    _cache_set(group_id, data)
    return data


async def ensure_group_exists(
    group_id: int,
    title: str,
    username: str = "",
    chat_type: str = "supergroup",
) -> dict[str, Any]:
    """
    Return existing group document or create a minimal one.

    Called when the bot first sees activity in a group.
    """
    data = await get_group(group_id)
    now = _now_iso()
    defaults: dict[str, Any] = {
        "chat_id": group_id,
        "title": title,
        "username": username,
        "type": chat_type,
        "is_active": True,
        "bot_status": "administrator",
        "permissions_valid": False,
        "permissions": {
            "can_delete_messages": False,
            "can_restrict_members": False,
        },
        "last_verified_at": None,
        "created_at": now,
        "updated_at": now,
        "added_at": now,
        "force_subscribe": {
            "enabled": False,
            "channels": [],
        },
        "guard": {
            "enabled": False,
            "anti_spam": True,
            "anti_flood": True,
            "anti_link": False,
            "anti_ads": True,
            "anti_repeat": True,
            "bad_words": False,
            "new_member_protection": True,
            "flood_limit": 5,
            "flood_window": 5,
            "mute_duration": 300,
            "bad_words_list": [],
        },
    }
    if data is None:
        await firebase_service.create_group(group_id, defaults)
        data = defaults
    else:
        # Backfill only missing top-level defaults without resetting settings.
        missing = {key: value for key, value in defaults.items() if key not in data}
        if missing:
            await firebase_service.update_group(group_id, missing)
            data = {**defaults, **data}
    _cache_set(group_id, data)
    logger.info("Group %s '%s' registered in Firestore.", group_id, title)
    return data


# ------------------------------------------------------------------ #
# Force Subscribe helpers
# ------------------------------------------------------------------ #

async def get_fsub_settings(group_id: int) -> dict[str, Any]:
    """
    Return the force_subscribe sub-document for *group_id*.

    Default: {"enabled": False, "channels": []}
    """
    data = await get_group(group_id)
    if data is None:
        return {"enabled": False, "channels": []}
    return data.get("force_subscribe", {"enabled": False, "channels": []})


async def set_fsub_enabled(group_id: int, enabled: bool) -> None:
    """Enable or disable force subscribe for *group_id*."""
    await firebase_service.update_group(
        group_id,
        {"force_subscribe": {"enabled": enabled}},
    )
    _cache_invalidate(group_id)
    logger.info("Group %s force_subscribe.enabled set to %s.", group_id, enabled)


async def add_channel(group_id: int, channel_data: dict[str, Any]) -> bool:
    """
    Add a channel to the group's force_subscribe.channels list.

    Returns False if a channel with the same channel_id already exists.
    """
    fsub = await get_fsub_settings(group_id)
    channels: list[dict[str, Any]] = fsub.get("channels", [])

    # Deduplication by channel_id
    channel_id = channel_data["channel_id"]
    if any(ch["channel_id"] == channel_id for ch in channels):
        return False

    channels.append(channel_data)
    await firebase_service.update_group(
        group_id,
        {"force_subscribe": {"channels": channels}},
    )
    _cache_invalidate(group_id)
    logger.info("Channel %s added to group %s.", channel_id, group_id)
    return True


async def remove_channel(group_id: int, channel_id: int) -> bool:
    """
    Remove a channel from the force_subscribe.channels list.

    Returns False if the channel was not found.
    """
    fsub = await get_fsub_settings(group_id)
    channels: list[dict[str, Any]] = fsub.get("channels", [])
    new_channels = [ch for ch in channels if ch["channel_id"] != channel_id]

    if len(new_channels) == len(channels):
        return False  # not found

    await firebase_service.update_group(
        group_id,
        {"force_subscribe": {"channels": new_channels}},
    )
    _cache_invalidate(group_id)
    logger.info("Channel %s removed from group %s.", channel_id, group_id)
    return True


async def get_channels(group_id: int) -> list[dict[str, Any]]:
    """Return the list of required channels for *group_id*."""
    fsub = await get_fsub_settings(group_id)
    return fsub.get("channels", [])


# ------------------------------------------------------------------ #
# Private helpers
# ------------------------------------------------------------------ #

def _now_iso() -> str:
    """Return current timezone-aware UTC time as ISO-8601 string."""
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
