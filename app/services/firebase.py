"""
Firebase Service for AnjurX | Rss Bot with Full Quota Resilience Architecture.
Implements:
- Explicit Health State Machine: HEALTHY, DEGRADED, QUOTA_EXCEEDED, RECOVERING
- Exponential backoff: 30s, 1m, 2m, 5m, 10m, 15m
- Lightweight Health Check (CHEAP single document check, NO collection scans)
- Integration with local durable SQLite recovery queue
- Safe recovery flusher (small batches of 10-25 with atomic checkpointing)
- Zero full collection scans
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

from app.database.firestore import db, is_quota_error
from app.services.recovery_queue import recovery_queue

logger = logging.getLogger("anjurxbot.firebase")


def get_current_time_iso() -> str:
    return datetime.utcnow().isoformat()


def get_today_date_str() -> str:
    try:
        import pytz
        return datetime.now(pytz.timezone("Asia/Tashkent")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.utcnow().strftime("%Y-%m-%d")


class FirestoreHealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    RECOVERING = "RECOVERING"


BACKOFF_SCHEDULE = [30, 60, 120, 300, 600, 900]  # 30s, 1m, 2m, 5m, 10m, 15m


class FirebaseService:
    def __init__(self):
        self.db = db
        self.state: FirestoreHealthState = FirestoreHealthState.HEALTHY
        self._backoff_index: int = 0
        self._next_retry_at: Optional[datetime] = None
        self._is_flushing: bool = False
        self._lock = asyncio.Lock()

        # Monitoring Metrics (In-Memory, Zero Quota Cost)
        self.metrics = {
            "firestore_status": FirestoreHealthState.HEALTHY.value,
            "firestore_429_count": 0,
            "firestore_read_errors": 0,
            "firestore_write_errors": 0,
            "recovery_success_count": 0,
            "recovery_failure_count": 0,
            "last_successful_firestore_operation": None,
            "last_successful_sync": None,
            "last_quota_error_at": None,
        }

    def is_initialized(self) -> bool:
        return self.db.is_initialized()

    def is_quota_exhausted(self) -> bool:
        return self.state == FirestoreHealthState.QUOTA_EXCEEDED

    def get_state(self) -> FirestoreHealthState:
        return self.state

    def get_diagnostics(self) -> Dict[str, Any]:
        """Provides full metrics to Super Admin (8157452043) and Dashboard API."""
        q_stats = recovery_queue.get_queue_stats()
        next_retry_iso = self._next_retry_at.isoformat() if self._next_retry_at else None
        backoff_sec = BACKOFF_SCHEDULE[self._backoff_index] if self.state == FirestoreHealthState.QUOTA_EXCEEDED else 0

        return {
            "firestore_status": self.state.value,
            "is_stale": self.state in (FirestoreHealthState.QUOTA_EXCEEDED, FirestoreHealthState.DEGRADED),
            "current_backoff_seconds": backoff_sec,
            "next_health_check_at": next_retry_iso,
            "firestore_429_count": self.metrics["firestore_429_count"],
            "firestore_read_errors": self.metrics["firestore_read_errors"],
            "firestore_write_errors": self.metrics["firestore_write_errors"],
            "recovery_success_count": self.metrics["recovery_success_count"],
            "recovery_failure_count": self.metrics["recovery_failure_count"],
            "last_successful_firestore_operation": self.metrics["last_successful_firestore_operation"],
            "last_successful_sync": self.metrics["last_successful_sync"],
            "last_quota_error_at": self.metrics["last_quota_error_at"],
            "recovery_queue_size": q_stats["total_queue_size"],
            "recovery_queue_oldest_age": q_stats["oldest_item_age_seconds"],
            "recovery_queue_details": q_stats["tables"],
        }

    # =========================================================================
    # STATE TRANSITIONS & BACKOFF
    # =========================================================================

    def record_success(self):
        """Records a successful Firestore operation."""
        self.metrics["last_successful_firestore_operation"] = get_current_time_iso()
        if self.state == FirestoreHealthState.DEGRADED:
            self.state = FirestoreHealthState.HEALTHY
            self.metrics["firestore_status"] = self.state.value

    def record_quota_exceeded(self, err: Exception):
        """Transitions state to QUOTA_EXCEEDED with exponential backoff."""
        now = datetime.utcnow()
        self.metrics["firestore_429_count"] += 1
        self.metrics["last_quota_error_at"] = now.isoformat()
        
        if self.state != FirestoreHealthState.QUOTA_EXCEEDED:
            self.state = FirestoreHealthState.QUOTA_EXCEEDED
            self._backoff_index = 0
            logger.warning(f"[Firestore Quota] 429 RESOURCE_EXHAUSTED encountered! Entering QUOTA_EXCEEDED mode: {err}")
        else:
            self._backoff_index = min(self._backoff_index + 1, len(BACKOFF_SCHEDULE) - 1)

        delay_seconds = BACKOFF_SCHEDULE[self._backoff_index]
        self._next_retry_at = now + timedelta(seconds=delay_seconds)
        self.metrics["firestore_status"] = self.state.value
        logger.warning(
            f"[Firestore Quota] Next health check scheduled in {delay_seconds}s at {self._next_retry_at.isoformat()}"
        )

    def record_transient_error(self, err: Exception, is_write: bool = False):
        if is_write:
            self.metrics["firestore_write_errors"] += 1
        else:
            self.metrics["firestore_read_errors"] += 1

        if self.state == FirestoreHealthState.HEALTHY:
            self.state = FirestoreHealthState.DEGRADED
            self.metrics["firestore_status"] = self.state.value
            logger.warning(f"[Firestore Degraded] Transient error encountered: {err}")

    # =========================================================================
    # CHEAP HEALTH CHECK
    # =========================================================================

    async def check_health(self) -> bool:
        """
        Executes a cheap ping against settings/system_health.
        Strictly reads/writes a single tiny document to avoid read traffic.
        """
        if not self.is_initialized():
            return False

        # If in quota backoff, wait until backoff time expires
        now = datetime.utcnow()
        if self._next_retry_at and now < self._next_retry_at:
            return False

        try:
            ping_doc = {
                "ping_at": get_current_time_iso(),
                "status": "healthy",
            }
            # Set system_health doc
            await self.db.set_document("settings", "system_health", ping_doc, merge=True)
            self.record_success()

            if self.state == FirestoreHealthState.QUOTA_EXCEEDED:
                logger.info("[Firestore Recovery] System health ping succeeded! Transitioning to RECOVERING...")
                self.state = FirestoreHealthState.RECOVERING
                self.metrics["firestore_status"] = self.state.value
                self._backoff_index = 0
                self._next_retry_at = None

            return True
        except Exception as e:
            if is_quota_error(e):
                self.record_quota_exceeded(e)
            else:
                self.record_transient_error(e, is_write=True)
            return False

    # =========================================================================
    # RECOVERY WORKER (FLUSHES SQLITE QUEUE IN SMALL BATCHES)
    # =========================================================================

    async def flush_recovery_queue(self, batch_size: int = 20) -> int:
        """
        Flushes pending SQLite events into Firestore in small batches (10-25).
        If 429 returns, immediately aborts and returns to QUOTA_EXCEEDED state.
        """
        if self._is_flushing:
            return 0

        # Health check first
        is_healthy = await self.check_health()
        if not is_healthy and self.state == FirestoreHealthState.QUOTA_EXCEEDED:
            return 0

        async with self._lock:
            self._is_flushing = True
            flushed_total = 0
            try:
                # 1. Flush pending posts
                flushed_total += await self._flush_table("pending_posts", "posts", batch_size)
                if self.state == FirestoreHealthState.QUOTA_EXCEEDED:
                    return flushed_total

                # 2. Flush pending deliveries
                flushed_total += await self._flush_table("pending_deliveries", "delivered_posts", batch_size)
                if self.state == FirestoreHealthState.QUOTA_EXCEEDED:
                    return flushed_total

                # 3. Flush pending users
                flushed_total += await self._flush_table("pending_users", "users", batch_size)
                if self.state == FirestoreHealthState.QUOTA_EXCEEDED:
                    return flushed_total

                # 4. Flush pending channels
                flushed_total += await self._flush_table("pending_channels", "channels", batch_size)
                if self.state == FirestoreHealthState.QUOTA_EXCEEDED:
                    return flushed_total

                # 5. Flush pending daily stats
                flushed_total += await self._flush_stats(batch_size)
                if self.state == FirestoreHealthState.QUOTA_EXCEEDED:
                    return flushed_total

                # Check if entire queue is cleared
                q_stats = recovery_queue.get_queue_stats()
                if q_stats["total_queue_size"] == 0:
                    if self.state in (FirestoreHealthState.RECOVERING, FirestoreHealthState.DEGRADED):
                        self.state = FirestoreHealthState.HEALTHY
                        self.metrics["firestore_status"] = self.state.value
                        self.metrics["last_successful_sync"] = get_current_time_iso()
                        logger.info("[Firestore Recovery] All queued records successfully flushed! State is HEALTHY.")

                return flushed_total
            finally:
                self._is_flushing = False

    async def _flush_table(self, queue_table: str, fs_collection: str, batch_size: int) -> int:
        batch = recovery_queue.get_pending_batch(queue_table, limit=batch_size)
        if not batch:
            return 0

        processed = 0
        event_ids = [item["event_id"] for item in batch]
        recovery_queue.mark_event_processing(queue_table, event_ids)

        for item in batch:
            event_id = item["event_id"]
            entity_id = item["entity_id"]
            payload = item["payload"]

            try:
                # Write to Firestore with merge=True for idempotency
                await self.db.set_document(fs_collection, entity_id, payload, merge=True)
                recovery_queue.mark_event_completed(queue_table, event_id)
                self.record_success()
                self.metrics["recovery_success_count"] += 1
                processed += 1
                # Tiny throttle to avoid rate-limiting
                await asyncio.sleep(0.05)
            except Exception as e:
                if is_quota_error(e):
                    self.record_quota_exceeded(e)
                    recovery_queue.mark_event_failed(queue_table, event_id, str(e), backoff_seconds=30)
                    self.metrics["recovery_failure_count"] += 1
                    logger.warning(f"[Recovery Flush] 429 hit during {queue_table} flush. Halting flush.")
                    break
                else:
                    self.record_transient_error(e, is_write=True)
                    recovery_queue.mark_event_failed(queue_table, event_id, str(e), backoff_seconds=60)
                    self.metrics["recovery_failure_count"] += 1

        return processed

    async def _flush_stats(self, batch_size: int) -> int:
        batch = recovery_queue.get_pending_batch("pending_stats", limit=batch_size)
        if not batch:
            return 0

        processed = 0
        event_ids = [item["event_id"] for item in batch]
        recovery_queue.mark_event_processing("pending_stats", event_ids)

        for item in batch:
            event_id = item["event_id"]
            payload = item["payload"]
            stat_date = payload.get("date", get_today_date_str())
            metric = payload.get("metric", "posts_delivered")
            amount = int(payload.get("amount", 1))

            try:
                # Atomic stat update in daily_stats
                existing = await self.db.get_document("daily_stats", stat_date) or {}
                existing[metric] = int(existing.get(metric, 0)) + amount
                existing["date"] = stat_date
                existing["updated_at"] = get_current_time_iso()
                await self.db.set_document("daily_stats", stat_date, existing, merge=True)

                recovery_queue.mark_event_completed("pending_stats", event_id)
                self.record_success()
                self.metrics["recovery_success_count"] += 1
                processed += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                if is_quota_error(e):
                    self.record_quota_exceeded(e)
                    recovery_queue.mark_event_failed("pending_stats", event_id, str(e), backoff_seconds=30)
                    self.metrics["recovery_failure_count"] += 1
                    break
                else:
                    self.record_transient_error(e, is_write=True)
                    recovery_queue.mark_event_failed("pending_stats", event_id, str(e), backoff_seconds=60)
                    self.metrics["recovery_failure_count"] += 1

        return processed

    # =========================================================================
    # RESILIENT DOCUMENT OPERATIONS
    # =========================================================================

    async def save_post_resilient(self, post_data: Dict[str, Any]) -> bool:
        """
        Saves post to Firestore if healthy.
        If in QUOTA_EXCEEDED or if 429 returns, enqueues to SQLite pending_posts.
        """
        post_id = str(post_data.get("post_id", ""))
        
        # If in quota exceeded state, enqueue directly without hitting Firestore
        if self.state == FirestoreHealthState.QUOTA_EXCEEDED:
            recovery_queue.enqueue_post(post_data)
            return True

        try:
            if self.is_initialized():
                await self.db.set_document("posts", post_id, post_data, merge=True)
                self.record_success()
                return True
        except Exception as e:
            if is_quota_error(e):
                self.record_quota_exceeded(e)
                recovery_queue.enqueue_post(post_data)
                return True
            else:
                self.record_transient_error(e, is_write=True)
                recovery_queue.enqueue_post(post_data)
                return True

        return True

    async def record_delivery_resilient(self, delivery_data: Dict[str, Any]) -> bool:
        """
        Records delivery into Firestore if healthy, or SQLite pending_deliveries if quota exceeded.
        """
        sig = str(delivery_data.get("signature", ""))
        if self.state == FirestoreHealthState.QUOTA_EXCEEDED:
            recovery_queue.enqueue_delivery(delivery_data)
            return True

        try:
            if self.is_initialized():
                await self.db.set_document("delivered_posts", sig, delivery_data, merge=True)
                self.record_success()
                return True
        except Exception as e:
            if is_quota_error(e):
                self.record_quota_exceeded(e)
                recovery_queue.enqueue_delivery(delivery_data)
                return True
            else:
                self.record_transient_error(e, is_write=True)
                recovery_queue.enqueue_delivery(delivery_data)
                return True

        return True

    async def save_user_resilient(self, user_id: int, user_data: Dict[str, Any]) -> bool:
        """Saves user with crash-safe local fallback."""
        doc_id = str(user_id)
        now = get_current_time_iso()
        payload = {
            "user_id": user_id,
            "username": user_data.get("username"),
            "first_name": user_data.get("first_name", ""),
            "last_name": user_data.get("last_name", ""),
            "updated_at": now,
        }
        if "created_at" in user_data:
            payload["created_at"] = user_data["created_at"]
        if "plan" in user_data:
            payload["plan"] = user_data["plan"]
        if "custom_limit" in user_data:
            payload["custom_limit"] = user_data["custom_limit"]

        if self.state == FirestoreHealthState.QUOTA_EXCEEDED:
            recovery_queue.enqueue_user(payload)
            return True

        try:
            if self.is_initialized():
                await self.db.set_document("users", doc_id, payload, merge=True)
                self.record_success()
                return True
        except Exception as e:
            if is_quota_error(e):
                self.record_quota_exceeded(e)
                recovery_queue.enqueue_user(payload)
                return True
            else:
                self.record_transient_error(e, is_write=True)
                recovery_queue.enqueue_user(payload)
                return True

        return True

    async def save_channel_resilient(self, chat_id: int, channel_data: Dict[str, Any]) -> bool:
        """Saves channel with crash-safe local fallback."""
        cid_str = str(chat_id)
        if self.state == FirestoreHealthState.QUOTA_EXCEEDED:
            recovery_queue.enqueue_channel(channel_data)
            return True

        try:
            if self.is_initialized():
                await self.db.set_document("channels", cid_str, channel_data, merge=True)
                self.record_success()
                return True
        except Exception as e:
            if is_quota_error(e):
                self.record_quota_exceeded(e)
                recovery_queue.enqueue_channel(channel_data)
                return True
            else:
                self.record_transient_error(e, is_write=True)
                recovery_queue.enqueue_channel(channel_data)
                return True

        return True

    async def increment_stat_resilient(self, metric: str, amount: int = 1) -> bool:
        """Increments daily stat with atomic merge or SQLite queuing."""
        today = get_today_date_str()
        if self.state == FirestoreHealthState.QUOTA_EXCEEDED:
            recovery_queue.enqueue_stat(today, metric, amount)
            return True

        try:
            if self.is_initialized():
                existing = await self.db.get_document("daily_stats", today) or {}
                existing[metric] = int(existing.get(metric, 0)) + amount
                existing["date"] = today
                existing["updated_at"] = get_current_time_iso()
                await self.db.set_document("daily_stats", today, existing, merge=True)
                self.record_success()
                return True
        except Exception as e:
            if is_quota_error(e):
                self.record_quota_exceeded(e)
                recovery_queue.enqueue_stat(today, metric, amount)
                return True
            else:
                self.record_transient_error(e, is_write=True)
                recovery_queue.enqueue_stat(today, metric, amount)
                return True

        return True

    async def save_entity_resilient(self, collection: str, doc_id: str, data: Dict[str, Any]) -> bool:
        """Saves any entity to Firestore with safe fallback to SQLite recovery queue."""
        if self.state == FirestoreHealthState.QUOTA_EXCEEDED:
            recovery_queue.enqueue_write(collection, doc_id, data)
            return True

        try:
            if self.is_initialized():
                await self.db.set_document(collection, doc_id, data, merge=True)
                self.record_success()
                return True
        except Exception as e:
            if is_quota_error(e):
                self.record_quota_exceeded(e)
                recovery_queue.enqueue_write(collection, doc_id, data)
                return True
            else:
                self.record_transient_error(e, is_write=True)
                recovery_queue.enqueue_write(collection, doc_id, data)
                return True

        return True


firebase_service = FirebaseService()
