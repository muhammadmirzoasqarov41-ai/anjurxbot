"""
Flood detection service (in-memory, per-restart).

Tracks message timestamps per user per chat.
On each incoming message, slides the window and counts messages.

Configuration (from guard settings):
    flood_limit  — max messages allowed inside the window
    flood_window — window size in seconds

Cache is never written to Firestore — acceptable for flood detection
because a brief restart window is an acceptable gap.
"""

from __future__ import annotations

import collections
import time
from typing import DefaultDict, Deque


# chat_id -> user_id -> deque of timestamps
_flood_cache: DefaultDict[int, DefaultDict[int, Deque[float]]] = collections.defaultdict(
    lambda: collections.defaultdict(collections.deque)
)


def check_flood(
    chat_id: int,
    user_id: int,
    flood_limit: int,
    flood_window: float,
) -> bool:
    """
    Record a message timestamp and check if *user_id* is flooding.

    Returns True if the user has exceeded *flood_limit* messages
    within the last *flood_window* seconds.
    """
    now = time.monotonic()
    dq: Deque[float] = _flood_cache[chat_id][user_id]

    # Remove timestamps outside the window
    while dq and now - dq[0] > flood_window:
        dq.popleft()

    dq.append(now)
    return len(dq) > flood_limit


def reset_flood(chat_id: int, user_id: int) -> None:
    """Clear the flood counter for *user_id* in *chat_id* (e.g. after mute)."""
    try:
        _flood_cache[chat_id][user_id].clear()
    except KeyError:
        pass


def cleanup_flood_cache(max_idle_seconds: float = 300.0) -> None:
    """Evict idle users and chats from the in-memory flood cache."""
    now = time.monotonic()
    for chat_id in list(_flood_cache):
        users = _flood_cache[chat_id]
        for user_id in list(users):
            timestamps = users[user_id]
            if not timestamps or now - timestamps[-1] > max_idle_seconds:
                users.pop(user_id, None)
        if not users:
            _flood_cache.pop(chat_id, None)
