"""
Deduplication Service.
Prevents duplicate update processing using a bounded TTL cache.
"""
import time
from typing import Dict


class DedupService:
    def __init__(self, max_size: int = 5000, ttl: float = 300.0):
        self._cache: Dict[str, float] = {}
        self._max_size = max_size
        self._ttl = ttl

    def is_duplicate(self, update_id: str) -> bool:
        """
        Returns True if `update_id` was already processed within the TTL window.
        Otherwise registers it and returns False.
        """
        now = time.time()
        self._cleanup(now)

        if update_id in self._cache:
            return True

        # Evict oldest if cache exceeded
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=self._cache.get)
            self._cache.pop(oldest_key, None)

        self._cache[update_id] = now
        return False

    def _cleanup(self, now: float) -> None:
        # Periodically clean up items exceeding TTL
        if len(self._cache) > 200:
            expired = [k for k, v in self._cache.items() if now - v > self._ttl]
            for k in expired:
                self._cache.pop(k, None)


dedup_service = DedupService()
