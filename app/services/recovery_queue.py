"""
Local Durable Recovery Queue (SQLite) for AnjurX | Rss Bot.
Handles offline/quota-exceeded recovery buffering for Firestore.

IMPORTANT RENDER ARCHITECTURE NOTE:
The local filesystem on Render can be ephemeral across fresh container builds.
This SQLite database is a temporary durable recovery buffer during process lifecycle
and container restarts, NOT a replacement for primary cloud Firestore persistence.
"""
import os
import json
import sqlite3
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("anjurxbot.recovery_queue")

QUEUE_DB_PATH = os.getenv("RECOVERY_QUEUE_PATH", "./data/recovery_queue.db")

TABLES = [
    "pending_users",
    "pending_channels",
    "pending_posts",
    "pending_deliveries",
    "pending_stats",
    "pending_sources",
    "pending_categories",
]


class RecoveryQueueService:
    """Manages SQLite-based local recovery queue for Firestore data resilience."""

    def __init__(self, db_path: str = QUEUE_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrency without blocking reads/writes
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        """Initializes tables and indices for all pending recovery entities."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for tbl in TABLES:
                cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {tbl} (
                    event_id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    next_retry_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    last_error TEXT
                );
                """)
                cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{tbl}_status_retry
                ON {tbl}(status, next_retry_at);
                """)
                cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{tbl}_entity
                ON {tbl}(entity_id);
                """)

            # Telegram local delivery intent table to guarantee zero duplicate Telegram sends during outage
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS delivery_intents (
                intent_id TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                channel_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                telegram_message_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_delivery_intents_post_channel
            ON delivery_intents(post_id, channel_id);
            """)
            conn.commit()
            logger.info(f"Initialized SQLite Recovery Queue at {self.db_path}")

    # =========================================================================
    # DETERMINISTIC EVENT ID GENERATORS (IDEMPOTENCY)
    # =========================================================================

    @staticmethod
    def hash_id(prefix: str, *parts: Any) -> str:
        """Generates a deterministic unique idempotency key."""
        raw = ":".join(str(p).strip() for p in parts)
        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        return f"{prefix}_{sha}"

    # =========================================================================
    # ENQUEUE OPERATIONS (CRASH-SAFE ATOMIC COMMITS)
    # =========================================================================

    def enqueue_event(
        self,
        table: str,
        event_id: str,
        entity_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> bool:
        """
        Atomically appends an event to the recovery queue table.
        If event_id already exists with status 'pending' or 'processing',
        updates payload while preserving initial creation timestamp.
        """
        if table not in TABLES:
            raise ValueError(f"Unknown recovery queue table: {table}")

        now_iso = datetime.utcnow().isoformat()
        payload_json = json.dumps(payload, ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
            INSERT INTO {table} (
                event_id, entity_id, event_type, payload, created_at,
                retry_count, next_retry_at, status, last_error
            ) VALUES (?, ?, ?, ?, ?, 0, ?, 'pending', NULL)
            ON CONFLICT(event_id) DO UPDATE SET
                payload = excluded.payload,
                next_retry_at = excluded.next_retry_at,
                status = CASE WHEN status = 'completed' THEN 'completed' ELSE 'pending' END
            """, (event_id, entity_id, event_type, payload_json, now_iso, now_iso))
            conn.commit()
            return True

    def enqueue_post(self, post_dict: Dict[str, Any]) -> str:
        """Enqueues post into pending_posts with deterministic key."""
        source_id = str(post_dict.get("source_id", ""))
        ext_id = str(post_dict.get("external_post_id", ""))
        post_id = str(post_dict.get("post_id", ""))
        event_id = self.hash_id("ev_post", source_id, ext_id)
        self.enqueue_event("pending_posts", event_id, post_id or event_id, "save_post", post_dict)
        return event_id

    def enqueue_delivery(self, delivery_dict: Dict[str, Any]) -> str:
        """Enqueues delivery record into pending_deliveries with deterministic key."""
        post_id = str(delivery_dict.get("post_id", ""))
        channel_id = str(delivery_dict.get("channel_id", ""))
        event_id = self.hash_id("ev_del", post_id, channel_id)
        sig = str(delivery_dict.get("signature") or f"{post_id}:{channel_id}")
        self.enqueue_event("pending_deliveries", event_id, sig, "record_delivery", delivery_dict)
        return event_id

    def enqueue_user(self, user_dict: Dict[str, Any]) -> str:
        """Enqueues user profile into pending_users."""
        uid = str(user_dict.get("user_id", ""))
        event_id = self.hash_id("ev_user", uid)
        self.enqueue_event("pending_users", event_id, uid, "save_user", user_dict)
        return event_id

    def enqueue_channel(self, channel_dict: Dict[str, Any]) -> str:
        """Enqueues channel configuration into pending_channels."""
        cid = str(channel_dict.get("chat_id", ""))
        event_id = self.hash_id("ev_channel", cid)
        self.enqueue_event("pending_channels", event_id, cid, "save_channel", channel_dict)
        return event_id

    def enqueue_stat(self, stat_date: str, metric: str, amount: int = 1) -> str:
        """Enqueues atomic stat increment into pending_stats."""
        event_id = self.hash_id("ev_stat", stat_date, metric)
        payload = {"date": stat_date, "metric": metric, "amount": amount}
        self.enqueue_event("pending_stats", event_id, f"{stat_date}:{metric}", "increment_stat", payload)
        return event_id

    def enqueue_write(self, collection: str, doc_id: str, data: Dict[str, Any]) -> str:
        """Generic resilient fallback enqueue for any collection."""
        tbl_map = {
            "users": "pending_users",
            "channels": "pending_channels",
            "posts": "pending_posts",
            "sources": "pending_sources",
            "source_categories": "pending_categories",
            "central_channels": "pending_channels",
            "premium_posts": "pending_posts",
        }
        tbl = tbl_map.get(collection, "pending_posts")
        event_id = self.hash_id(f"ev_{collection}", doc_id)
        self.enqueue_event(tbl, event_id, doc_id, f"save_{collection}", data)
        return event_id

    # =========================================================================
    # TELEGRAM DELIVERY INTENT DEDUPLICATION
    # =========================================================================

    def register_delivery_intent(self, post_id: str, channel_id: int) -> Tuple[str, bool]:
        """
        Creates or retrieves delivery intent for (post_id, channel_id).
        Returns (intent_id, is_new).
        If already exists and was delivered (status='sent' or 'sent_pending_sync'), returns is_new=False!
        """
        intent_id = self.hash_id("intent", post_id, str(channel_id))
        now_iso = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM delivery_intents WHERE intent_id = ?", (intent_id,))
            row = cursor.fetchone()
            if row:
                if row["status"] in ("sent", "sent_pending_sync"):
                    return intent_id, False  # Already delivered!
                # If still pending, re-use
                return intent_id, True

            cursor.execute("""
            INSERT INTO delivery_intents (intent_id, post_id, channel_id, status, created_at, updated_at)
            VALUES (?, ?, ?, 'pending', ?, ?)
            """, (intent_id, post_id, channel_id, now_iso, now_iso))
            conn.commit()
            return intent_id, True

    def mark_delivery_intent_sent(self, intent_id: str, telegram_message_id: Optional[int]) -> bool:
        """Marks local delivery intent as sent and awaiting Firestore sync."""
        now_iso = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE delivery_intents
            SET status = 'sent_pending_sync', telegram_message_id = ?, updated_at = ?
            WHERE intent_id = ?
            """, (telegram_message_id, now_iso, intent_id))
            conn.commit()
            return True

    def is_delivery_already_sent(self, post_id: str, channel_id: int) -> bool:
        """Checks if Telegram delivery intent was already successfully sent."""
        intent_id = self.hash_id("intent", post_id, str(channel_id))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM delivery_intents WHERE intent_id = ?", (intent_id,))
            row = cursor.fetchone()
            if row and row["status"] in ("sent", "sent_pending_sync"):
                return True
            return False

    # =========================================================================
    # RECOVERY FLUSH BATCH CONSUMPTION
    # =========================================================================

    def get_pending_batch(self, table: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Fetches up to `limit` pending events ready for retry.
        Small batching (10-25) avoids hammering Firestore.
        """
        if table not in TABLES:
            return []

        now_iso = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
            SELECT * FROM {table}
            WHERE status = 'pending' AND next_retry_at <= ?
            ORDER BY created_at ASC
            LIMIT ?
            """, (now_iso, limit))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                try:
                    item["payload"] = json.loads(item["payload"])
                except Exception:
                    pass
                results.append(item)
            return results

    def mark_event_processing(self, table: str, event_ids: List[str]):
        """Marks events as in-flight processing."""
        if not event_ids or table not in TABLES:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in event_ids)
            cursor.execute(f"""
            UPDATE {table} SET status = 'processing' WHERE event_id IN ({placeholders})
            """, event_ids)
            conn.commit()

    def mark_event_completed(self, table: str, event_id: str):
        """Marks event completed after successful Firestore write and purges safely."""
        if table not in TABLES:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Mark completed, then safely delete
            cursor.execute(f"""
            DELETE FROM {table} WHERE event_id = ?
            """, (event_id,))
            conn.commit()

    def mark_event_failed(
        self,
        table: str,
        event_id: str,
        error: str,
        is_permanent: bool = False,
        backoff_seconds: int = 30,
    ):
        """Records error and sets next exponential backoff retry."""
        if table not in TABLES:
            return
        next_dt = datetime.utcnow() + timedelta(seconds=backoff_seconds)
        new_status = "failed_permanent" if is_permanent else "pending"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
            UPDATE {table}
            SET retry_count = retry_count + 1,
                next_retry_at = ?,
                status = ?,
                last_error = ?
            WHERE event_id = ?
            """, (next_dt.isoformat(), new_status, str(error)[:500], event_id))
            conn.commit()

    # =========================================================================
    # DIAGNOSTICS & METRICS
    # =========================================================================

    def get_queue_stats(self) -> Dict[str, Any]:
        """Returns deep diagnostics on all recovery queue tables for Super Admin (8157452043)."""
        counts_by_table: Dict[str, Dict[str, int]] = {}
        total_pending = 0
        total_processing = 0
        total_failed_permanent = 0
        oldest_pending_iso: Optional[str] = None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for tbl in TABLES:
                cursor.execute(f"""
                SELECT status, count(*) as cnt, min(created_at) as oldest
                FROM {tbl}
                GROUP BY status
                """)
                rows = cursor.fetchall()
                tbl_stats = {"pending": 0, "processing": 0, "failed_permanent": 0, "total": 0}
                for r in rows:
                    st = r["status"]
                    cnt = r["cnt"]
                    if st in tbl_stats:
                        tbl_stats[st] += cnt
                    tbl_stats["total"] += cnt
                    if st == "pending":
                        total_pending += cnt
                        if r["oldest"] and (oldest_pending_iso is None or r["oldest"] < oldest_pending_iso):
                            oldest_pending_iso = r["oldest"]
                    elif st == "processing":
                        total_processing += cnt
                    elif st == "failed_permanent":
                        total_failed_permanent += cnt

                counts_by_table[tbl] = tbl_stats

        oldest_age_sec = 0
        if oldest_pending_iso:
            try:
                oldest_dt = datetime.fromisoformat(oldest_pending_iso.replace("Z", "+00:00"))
                oldest_age_sec = int((datetime.utcnow() - oldest_dt.replace(tzinfo=None)).total_seconds())
            except Exception:
                oldest_age_sec = 0

        return {
            "total_pending": total_pending,
            "total_processing": total_processing,
            "total_failed_permanent": total_failed_permanent,
            "total_queue_size": total_pending + total_processing,
            "oldest_item_age_seconds": oldest_age_sec,
            "oldest_item_created_at": oldest_pending_iso,
            "tables": counts_by_table,
        }

    def purge_completed_and_stale(self, max_age_days: int = 7) -> int:
        """Safely cleans up stale completed delivery intents."""
        cutoff = (datetime.utcnow() - timedelta(days=max_age_days)).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM delivery_intents WHERE updated_at < ?", (cutoff,))
            del_count = cursor.rowcount
            conn.commit()
            return del_count


# Global singleton instance
recovery_queue = RecoveryQueueService()
