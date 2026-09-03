"""Bounded TTL cache for Telegram update IDs."""

from __future__ import annotations

import time
from collections import deque


class UpdateDedupService:
    def __init__(self, max_size: int = 20000, ttl: float = 900.0) -> None:
        self._seen: dict[int, float] = {}
        self._order: deque[tuple[int, float]] = deque()
        self._max_size = max_size
        self._ttl = ttl

    def first_seen(self, update_id: int) -> bool:
        now = time.monotonic()
        while self._order and (now - self._order[0][1] >= self._ttl or len(self._seen) > self._max_size):
            old_id, _ = self._order.popleft()
            self._seen.pop(old_id, None)
        if update_id in self._seen:
            return False
        self._seen[update_id] = now
        self._order.append((update_id, now))
        return True


update_dedup_service = UpdateDedupService()