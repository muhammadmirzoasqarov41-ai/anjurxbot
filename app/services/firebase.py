"""
High-level Firebase Firestore services for AnjurX | Rss Bot.
Handles users, sources (RSS feeds & Telegram channels), destinations (channels & groups),
and delivered post tracking with robust error handling.
"""
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.config import config
from app.database.firestore import db

try:
    import pytz
    def _get_tz():
        try:
            return pytz.timezone(config.timezone)
        except Exception:
            return pytz.UTC
except ImportError:
    try:
        from zoneinfo import ZoneInfo
        def _get_tz():
            try:
                return ZoneInfo(config.timezone)
            except Exception:
                return None
    except Exception:
        def _get_tz():
            return None

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
    @property
    def db(self):
        """Returns the active FirestoreManager instance."""
        return db

    async def initialize(self) -> bool:
        """Connects to Firestore if credentials are configured."""
        return await db.connect()

    def is_initialized(self) -> bool:
        """Checks if Firestore connection is active and ready."""
        return db.is_connected and not db._fallback_mode and db.client is not None

    # --- Sources (RSS feeds & Telegram channels) ---
    async def get_all_sources(self, limit: int = 1000) -> List[Dict[str, Any]]:
        if not self.is_initialized():
            return []
        return await db.list_documents("aggregator_sources", limit=limit)

    async def save_source(self, source_data: Dict[str, Any]) -> bool:
        if not self.is_initialized():
            return False
        source_id = str(source_data.get("id", ""))
        if not source_id:
            return False
        return await db.set_document("aggregator_sources", source_id, source_data, merge=True)

    async def delete_source(self, source_id: str) -> bool:
        if not self.is_initialized():
            return False
        return await db.delete_document("aggregator_sources", source_id)

    # --- Destinations (Channels & Groups) ---
    async def get_all_destinations(self, limit: int = 1000) -> List[Dict[str, Any]]:
        if not self.is_initialized():
            return []
        return await db.list_documents("aggregator_destinations", limit=limit)

    async def save_destination(self, dest_data: Dict[str, Any]) -> bool:
        if not self.is_initialized():
            return False
        chat_id = str(dest_data.get("chat_id", ""))
        if not chat_id:
            return False
        return await db.set_document("aggregator_destinations", chat_id, dest_data, merge=True)

    async def delete_destination(self, chat_id: int) -> bool:
        if not self.is_initialized():
            return False
        return await db.delete_document("aggregator_destinations", str(chat_id))

    # --- Delivered Posts Log ---
    async def save_delivered_post(self, post_data: Dict[str, Any]) -> bool:
        if not self.is_initialized():
            return False
        post_id = str(post_data.get("id") or f"post_{int(time.time()*1000)}")
        return await db.set_document("delivered_posts", post_id, post_data, merge=True)

    async def get_recent_delivered_posts(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.is_initialized():
            return []
        return await db.list_documents("delivered_posts", limit=limit)

    # --- RSS Feed Firestore Operations (Backward Compatibility) ---
    async def get_rss_feeds(self, limit: int = 1000) -> List[Dict[str, Any]]:
        if not self.is_initialized():
            return []
        return await db.list_documents("rss_feeds", limit=limit)

    async def save_rss_feed(self, feed_data: Dict[str, Any]) -> bool:
        if not self.is_initialized():
            return False
        feed_id = str(feed_data.get("id", ""))
        if not feed_id:
            return False
        return await db.set_document("rss_feeds", feed_id, feed_data, merge=True)

    async def delete_rss_feed(self, feed_id: str) -> bool:
        if not self.is_initialized():
            return False
        return await db.delete_document("rss_feeds", feed_id)

    # --- User operations ---
    async def save_or_update_user(self, user_id: int, user_data: Dict[str, Any]) -> bool:
        if not self.is_initialized():
            return False
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
        if not self.is_initialized():
            return None
        return await db.get_document("users", str(user_id))

    async def get_all_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.is_initialized():
            return []
        return await db.list_documents("users", limit=limit)

    # --- Daily Stats ---
    async def increment_stat(self, metric: str, count: int = 1) -> bool:
        if not self.is_initialized():
            return False
        today = get_today_date_str()
        existing = await db.get_document("daily_stats", today) or {}
        current_val = existing.get(metric, 0)
        existing[metric] = current_val + count
        existing["date"] = today
        existing["updated_at"] = get_current_time_iso()
        return await db.set_document("daily_stats", today, existing, merge=True)

    async def get_today_stats(self) -> Dict[str, Any]:
        if not self.is_initialized():
            return {}
        today = get_today_date_str()
        return await db.get_document("daily_stats", today) or {}


firebase_service = FirebaseService()
