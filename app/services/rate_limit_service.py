"""
Rate Limiting Service using sliding window and token bucket concepts.
"""
import time
from typing import Dict, Tuple
from app.config import config


class RateLimitService:
    def __init__(self):
        # (action, user_id) -> last_timestamp
        self._limits: Dict[Tuple[str, int], float] = {}

    def is_rate_limited(self, action: str, user_id: int, rate_limit: float = None) -> Tuple[bool, float]:
        """
        Check if user is calling action too quickly.
        Returns (is_limited, remaining_wait_seconds).
        """
        limit = rate_limit if rate_limit is not None else config.rate_limit_default
        now = time.time()
        key = (action, user_id)
        last_time = self._limits.get(key, 0.0)
        elapsed = now - last_time

        if elapsed < limit:
            remaining = round(limit - elapsed, 1)
            return True, remaining

        self._limits[key] = now
        return False, 0.0

    def cleanup(self) -> None:
        now = time.time()
        keys_to_del = [k for k, v in self._limits.items() if now - v > 60.0]
        for k in keys_to_del:
            self._limits.pop(k, None)


rate_limit_service = RateLimitService()
