"""
Statistics service.

Tracks per-group guard and force-subscribe statistics using
Firestore atomic increments.

Structure:
  groups/{group_id}.stats  (aggregate counters)
    groups/{group_id}/daily_stats/{YYYY-MM-DD}  (daily counters)
"""
from __future__ import annotations

import datetime
import zoneinfo
from typing import Any

from app.services.firebase import firebase_service
from app.utils.logger import logger

# Timezone for Uzbekistan
TZ_UZ = zoneinfo.ZoneInfo("Asia/Tashkent")


def get_today_str() -> str:
    """Return YYYY-MM-DD string for current day in Uzbekistan."""
    return datetime.datetime.now(TZ_UZ).strftime("%Y-%m-%d")


DEFAULT_STATS: dict[str, int] = {
    "messages_checked": 0,
    "deleted_messages": 0,
    "muted_users": 0,
    "banned_users": 0,
    "warnings": 0,
    "force_subscribe_checks": 0,

    "spam": 0,
    "flood": 0,
    "link": 0,
    "advertisement": 0,
    "repeat": 0,
    "bad_word": 0,
}


async def get_stats(group_id: int) -> dict[str, Any]:
    """Return overall aggregate stats for *group_id*, merged with defaults."""
    try:
        data = await firebase_service.get_group(group_id)
        if data is None:
            return dict(DEFAULT_STATS)
        return {**DEFAULT_STATS, **data.get("stats", {})}
    except Exception as exc:
        logger.error("Failed to get stats for group %s: %s", group_id, exc)
        return dict(DEFAULT_STATS)


async def get_daily_stats(group_id: int, date_str: str | None = None) -> dict[str, Any]:
    """Return daily stats for *group_id* and given date (default today)."""
    if date_str is None:
        date_str = get_today_str()

    try:
        doc = await firebase_service.db.collection("groups").document(str(group_id)) \
            .collection("daily_stats").document(date_str).get()
        if doc.exists:
            return {**DEFAULT_STATS, **(doc.to_dict() or {})}
        return dict(DEFAULT_STATS)
    except Exception as exc:
        logger.error("Failed to get daily stats for group %s: %s", group_id, exc)
        return dict(DEFAULT_STATS)


async def _increment_both(group_id: int, field: str, amount: int = 1) -> None:
    """Atomically increment a stats field in both total and daily documents."""
    try:
        from google.cloud.firestore_v1 import transforms
        db = firebase_service.db
        group_ref = db.collection("groups").document(str(group_id))
        daily_ref = group_ref.collection("daily_stats").document(get_today_str())

        inc = transforms.Increment(amount)

        batch = db.batch()
        # ``set(..., merge=True)`` also works when a group document is absent.
        batch.set(group_ref, {"stats": {field: inc}}, merge=True)
        batch.set(daily_ref, {field: inc}, merge=True)
        await batch.commit()
    except Exception as exc:
        logger.warning(
            "Stats increment failed group=%s field=%s: %s", group_id, field, exc
        )


async def inc_checked(group_id: int, amount: int = 1) -> None:
    await _increment_both(group_id, "messages_checked", amount)


async def inc_deleted(group_id: int, amount: int = 1) -> None:
    await _increment_both(group_id, "deleted_messages", amount)


async def inc_muted(group_id: int, amount: int = 1) -> None:
    await _increment_both(group_id, "muted_users", amount)


async def inc_warnings(group_id: int, amount: int = 1) -> None:
    await _increment_both(group_id, "warnings", amount)


async def inc_fsub_checks(group_id: int, amount: int = 1) -> None:
    await _increment_both(group_id, "force_subscribe_checks", amount)


async def inc_guard_event(group_id: int, event_type: str, amount: int = 1) -> None:
    """Increment specific guard event (spam, flood, link, advertisement, repeat, bad_word)."""
    if event_type in DEFAULT_STATS:
        await _increment_both(group_id, event_type, amount)
