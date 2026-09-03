"""
Log service.

Handles logging of admin actions and guard events.
Data is stored in Firestore subcollections:
  groups/{group_id}/admin_logs
  groups/{group_id}/guard_logs
"""
from __future__ import annotations

import datetime
from typing import Any

from google.cloud.firestore_v1.query import Query

from app.services.firebase import firebase_service
from app.services.stats_service import TZ_UZ
from app.utils.logger import logger


# ------------------------------------------------------------------ #
# Admin Logs
# ------------------------------------------------------------------ #

async def log_admin_action(group_id: int, admin_id: int, action: str, details: str = "") -> None:
    """Log an action performed by an admin."""
    try:
        now = datetime.datetime.now(TZ_UZ)
        doc_data = {
            "group_id": group_id,
            "admin_id": admin_id,
            "action": action,
            "details": details,
            "created_at": now.isoformat(),
            "timestamp": now.timestamp(),
        }
        await firebase_service.db.collection("groups").document(str(group_id)) \
            .collection("admin_logs").add(doc_data)
    except Exception as exc:
        logger.error("Failed to log admin action for group %s: %s", group_id, exc)


async def get_admin_logs(group_id: int, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    """Retrieve recent admin logs for a group."""
    try:
        query = firebase_service.db.collection("groups").document(str(group_id)) \
            .collection("admin_logs").order_by("timestamp", direction=Query.DESCENDING) \
            .limit(limit).offset(offset)

        results = []
        async for doc in query.stream():
            data = doc.to_dict()
            if data:
                data["_id"] = doc.id
                results.append(data)
        return results
    except Exception as exc:
        logger.error("Failed to get admin logs for group %s: %s", group_id, exc)
        return []


# ------------------------------------------------------------------ #
# Guard Logs
# ------------------------------------------------------------------ #

async def log_guard_event(group_id: int, user_id: int, event_type: str, message_id: int = 0) -> None:
    """Log a guard violation event (spam, flood, etc.)."""
    try:
        now = datetime.datetime.now(TZ_UZ)
        doc_data = {
            "group_id": group_id,
            "user_id": user_id,
            "type": event_type,
            "message_id": message_id,
            "created_at": now.isoformat(),
            "timestamp": now.timestamp(),
        }
        await firebase_service.db.collection("groups").document(str(group_id)) \
            .collection("guard_logs").add(doc_data)
    except Exception as exc:
        logger.error("Failed to log guard event for group %s: %s", group_id, exc)


async def log_moderation_action(
    group_id: int,
    user_id: int,
    action: str,
    reason: str = "",
    duration: int | None = None,
) -> None:
    """Store a moderation action in a retention-ready event stream."""
    try:
        now = datetime.datetime.now(TZ_UZ)
        data: dict[str, Any] = {
            "action": action,
            "user_id": user_id,
            "reason": reason,
            "created_at": now.isoformat(),
            "timestamp": now.timestamp(),
        }
        if duration is not None:
            data["duration"] = duration
        await firebase_service.db.collection("groups").document(str(group_id)) \
            .collection("moderation_logs").add(data)
    except Exception as exc:
        logger.error("Failed to log moderation action for group %s: %s", group_id, exc)


async def get_logs_before(group_id: int, collection: str, before: datetime.datetime) -> list[str]:
    """Return document IDs eligible for a future retention cleanup job."""
    query = firebase_service.db.collection("groups").document(str(group_id)) \
        .collection(collection).where("timestamp", "<", before.timestamp()).limit(500)
    try:
        return [doc.id async for doc in query.stream()]
    except Exception as exc:
        logger.error("Failed to find old %s for group %s: %s", collection, group_id, exc)
        return []


async def get_guard_logs(group_id: int, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    """Retrieve recent guard logs for a group."""
    try:
        query = firebase_service.db.collection("groups").document(str(group_id)) \
            .collection("guard_logs").order_by("timestamp", direction=Query.DESCENDING) \
            .limit(limit).offset(offset)

        results = []
        async for doc in query.stream():
            data = doc.to_dict()
            if data:
                data["_id"] = doc.id
                results.append(data)
        return results
    except Exception as exc:
        logger.error("Failed to get guard logs for group %s: %s", group_id, exc)
        return []
