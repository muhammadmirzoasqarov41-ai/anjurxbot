"""
Guard settings service.

Reads and writes the 'guard' sub-document inside groups/{group_id}.
Uses the same in-memory cache as group_service so a single Firestore
read per minute covers both fsub and guard settings.

Firestore layout (guard section):
    groups/{group_id}
    {
        "guard": {
            "enabled": true,
            "anti_spam": true,
            "anti_flood": true,
            "anti_link": false,
            "anti_ads": true,
            "anti_repeat": true,
            "bad_words": false,
            "new_member_protection": true,

            "flood_limit": 5,      # messages per window
            "flood_window": 5,     # window in seconds
            "mute_duration": 300,  # seconds

            "bad_words_list": []   # list[str]
        }
    }
"""

from __future__ import annotations

from typing import Any

from app.services.firebase import firebase_service
from app.services import group_service
from app.utils.logger import logger

# ------------------------------------------------------------------ #
# Defaults
# ------------------------------------------------------------------ #

DEFAULT_GUARD: dict[str, Any] = {
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
}


# ------------------------------------------------------------------ #
# Public API
# ------------------------------------------------------------------ #

async def get_guard_settings(group_id: int) -> dict[str, Any]:
    """
    Return the guard sub-document merged with defaults.

    Uses group_service cache — no extra Firestore call needed.
    """
    data = await group_service.get_group(group_id)
    if data is None:
        return dict(DEFAULT_GUARD)
    guard = data.get("guard", {})
    # Merge with defaults so new keys added later always have a value
    return {**DEFAULT_GUARD, **guard}


async def set_guard_enabled(group_id: int, enabled: bool) -> None:
    """Enable or disable the guard system for *group_id*."""
    await firebase_service.update_group(group_id, {"guard": {"enabled": enabled}})
    group_service._cache_invalidate(group_id)
    logger.info("Guard.enabled=%s for group %s.", enabled, group_id)


async def toggle_guard_feature(group_id: int, feature: str, enabled: bool) -> None:
    """
    Toggle a specific guard feature (e.g. 'anti_flood', 'anti_link').

    Valid feature names are the keys in DEFAULT_GUARD that hold booleans.
    """
    await firebase_service.update_group(group_id, {"guard": {feature: enabled}})
    group_service._cache_invalidate(group_id)
    logger.info("Guard.%s=%s for group %s.", feature, enabled, group_id)


async def update_guard_param(group_id: int, key: str, value: Any) -> None:
    """Update a single numeric/other guard parameter (flood_limit, mute_duration, etc.)."""
    await firebase_service.update_group(group_id, {"guard": {key: value}})
    group_service._cache_invalidate(group_id)
    logger.info("Guard.%s=%s for group %s.", key, value, group_id)


# ------------------------------------------------------------------ #
# Bad words management
# ------------------------------------------------------------------ #

async def get_bad_words(group_id: int) -> list[str]:
    """Return the bad_words_list for *group_id* (lowercase)."""
    guard = await get_guard_settings(group_id)
    return [w.lower() for w in guard.get("bad_words_list", [])]


async def add_bad_word(group_id: int, word: str) -> bool:
    """
    Add *word* to the bad_words_list.

    Returns False if it already exists.
    """
    guard = await get_guard_settings(group_id)
    words: list[str] = guard.get("bad_words_list", [])
    word_lower = word.strip().lower()
    if word_lower in [w.lower() for w in words]:
        return False
    words.append(word_lower)
    await firebase_service.update_group(group_id, {"guard": {"bad_words_list": words}})
    group_service._cache_invalidate(group_id)
    logger.info("Bad word '%s' added to group %s.", word_lower, group_id)
    return True


async def remove_bad_word(group_id: int, word: str) -> bool:
    """
    Remove *word* from the bad_words_list.

    Returns False if not found.
    """
    guard = await get_guard_settings(group_id)
    words: list[str] = guard.get("bad_words_list", [])
    word_lower = word.strip().lower()
    new_words = [w for w in words if w.lower() != word_lower]
    if len(new_words) == len(words):
        return False
    await firebase_service.update_group(group_id, {"guard": {"bad_words_list": new_words}})
    group_service._cache_invalidate(group_id)
    logger.info("Bad word '%s' removed from group %s.", word_lower, group_id)
    return True
