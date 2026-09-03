"""Small bounded in-memory rate limiter for user actions."""

from __future__ import annotations

import collections
import time
from typing import Deque

from app.config import settings


class RateLimitService:
    def __init__(self, max_keys: int = 10000) -> None:
        self._events: dict[tuple[str, int], Deque[float]] = {}
        self._max_keys = max_keys

    def allow(self, action: str, user_id: int, limit: int, window: float) -> bool:
        now = time.monotonic()
        key = (action, user_id)
        events = self._events.setdefault(key, collections.deque())
        while events and now - events[0] >= window:
            events.popleft()
        if len(events) >= limit:
            return False
        events.append(now)
        if len(self._events) > self._max_keys:
            oldest = min(self._events, key=lambda item: self._events[item][0] if self._events[item] else now)
            self._events.pop(oldest, None)
        return True

    def allow_callback(self, user_id: int) -> bool:
        return self.allow("callback", user_id, settings.rate_limit_callback, settings.rate_limit_callback_window)

    def allow_setup(self, user_id: int) -> bool:
        return self.allow("setup", user_id, settings.rate_limit_setup, settings.rate_limit_setup_window)

    def allow_subscription(self, user_id: int) -> bool:
        return self.allow("subscription", user_id, settings.rate_limit_subscription, settings.rate_limit_subscription_window)


rate_limit_service = RateLimitService()