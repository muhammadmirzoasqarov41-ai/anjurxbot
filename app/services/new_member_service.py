"""
New Member Protection service (in-memory cache).

Tracks recent joiners so the guard middleware can apply stricter
filtering during their first few minutes in the group.

Cache layout:
    (chat_id, user_id) -> join_timestamp (monotonic)

Cache is cleared on bot restart — acceptable for new-member detection
because a brief gap does not cause security issues.
"""

from __future__ import annotations

import time
from typing import Dict, Tuple

# How long (seconds) a user is considered a "new member"
_NEW_MEMBER_WINDOW: float = 300.0  # 5 minutes

# (chat_id, user_id) -> monotonic join timestamp
_new_members: Dict[Tuple[int, int], float] = {}


def mark_new_member(chat_id: int, user_id: int) -> None:
    """Record that *user_id* just joined *chat_id*."""
    _new_members[(chat_id, user_id)] = time.monotonic()


def is_new_member(chat_id: int, user_id: int) -> bool:
    """
    Return True if *user_id* joined *chat_id* within _NEW_MEMBER_WINDOW seconds.

    Expired entries are lazily cleaned up here.
    """
    key = (chat_id, user_id)
    join_ts = _new_members.get(key)
    if join_ts is None:
        return False

    if time.monotonic() - join_ts > _NEW_MEMBER_WINDOW:
        # Expired — remove and return False
        _new_members.pop(key, None)
        return False

    return True


def remove_new_member(chat_id: int, user_id: int) -> None:
    """Manually remove a user from the new-member cache (e.g., after restriction)."""
    _new_members.pop((chat_id, user_id), None)


def cleanup_expired() -> int:
    """
    Remove all expired entries from the cache.

    Returns the number of removed entries.
    Can be called periodically by a background task if needed.
    """
    now = time.monotonic()
    expired = [
        key for key, ts in _new_members.items()
        if now - ts > _NEW_MEMBER_WINDOW
    ]
    for key in expired:
        _new_members.pop(key, None)
    return len(expired)
