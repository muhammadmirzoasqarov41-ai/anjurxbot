"""
High-level Firebase Firestore services for AnjurXBot.
Handles users, groups, settings, moderation logs, and statistics.
"""
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

try:
    import pytz
    def _get_tz():
        return pytz.timezone(config.timezone)
except ImportError:
    try:
        from zoneinfo import ZoneInfo
        def _get_tz():
            return ZoneInfo(config.timezone)
    except Exception:
        def _get_tz():
            return None

from app.config import config
from app.database.firestore import db

logger = logging.getLogger("anjurxbot.firebase_service")


def get_current_time_iso() -> str:
    tz = _get_tz()
    if tz:
        return datetime.now(tz).isoformat()
    return datetime.utcnow().isoformat()


def get_today_date_str() -> str:
    tz = _get_tz()
    if tz:
        return datetime.now(tz).strftime("%Y-%m-%d")
    return datetime.utcnow().strftime("%Y-%m-%d")


class FirebaseService:
    # --- User operations ---
    async def save_or_update_user(self, user_id: int, user_data: Dict[str, Any]) -> bool:
        doc_id = str(user_id)
        existing = await db.get_document("users", doc_id)
        now = get_current_time_iso()

        payload = {
            "user_id": user_id,
            "username": user_data.get("username"),
            "first_name": user_data.get("first_name", ""),
            "last_name": user_data.get("last_name", ""),
            "updated_at": now,
        }
        if not existing:
            payload["created_at"] = now
            payload["is_bot"] = user_data.get("is_bot", False)

        return await db.set_document("users", doc_id, payload, merge=True)

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await db.get_document("users", str(user_id))

    async def get_all_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        return await db.list_documents("users", limit=limit)

    # --- Group operations ---
    async def get_group(self, group_id: int) -> Optional[Dict[str, Any]]:
        return await db.get_document("groups", str(group_id))

    async def save_group(self, group_id: int, data: Dict[str, Any]) -> bool:
        doc_id = str(group_id)
        now = get_current_time_iso()
        payload = dict(data)
        payload["updated_at"] = now
        existing = await db.get_document("groups", doc_id)
        if not existing:
            payload["created_at"] = now
        return await db.set_document("groups", doc_id, payload, merge=True)

    async def update_group_settings(self, group_id: int, key_path: str, value: Any) -> bool:
        """Update a specific setting in the group document safely without overwriting other keys."""
        doc_id = str(group_id)
        group = await db.get_document("groups", doc_id)
        if not group:
            group = {"group_id": group_id, "guard_settings": {}, "force_sub": {}}

        # Parse nested paths e.g. "guard_settings.anti_link"
        parts = key_path.split(".")
        target = group
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value
        group["updated_at"] = get_current_time_iso()
        return await db.set_document("groups", doc_id, group, merge=True)

    async def get_all_groups(self, limit: int = 100) -> List[Dict[str, Any]]:
        return await db.list_documents("groups", limit=limit)

    # --- Moderation Logs ---
    async def log_moderation_event(
        self,
        group_id: int,
        user_id: int,
        action: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        now = get_current_time_iso()
        log_id = f"{group_id}_{user_id}_{int(time.time() * 1000)}"
        payload = {
            "group_id": group_id,
            "user_id": user_id,
            "action": action,
            "reason": reason,
            "details": details or {},
            "created_at": now,
        }
        return await db.set_document("moderation_logs", log_id, payload, merge=False)

    async def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return await db.list_documents("moderation_logs", limit=limit)

    # --- Daily Stats ---
    async def increment_stat(self, metric: str, count: int = 1) -> bool:
        today = get_today_date_str()
        existing = await db.get_document("daily_stats", today) or {}
        current_val = existing.get(metric, 0)
        existing[metric] = current_val + count
        existing["date"] = today
        existing["updated_at"] = get_current_time_iso()
        return await db.set_document("daily_stats", today, existing, merge=True)

    async def get_today_stats(self) -> Dict[str, Any]:
        today = get_today_date_str()
        return await db.get_document("daily_stats", today) or {}


firebase_service = FirebaseService()
