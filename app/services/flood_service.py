"""
In-memory Flood Detection Service using Sliding Window.
"""
import time
from typing import Dict, Tuple, List


class FloodService:
    def __init__(self):
        # (group_id, user_id) -> list of timestamp floats
        self._history: Dict[Tuple[int, int], List[float]] = {}

    def check_flood(self, group_id: int, user_id: int, limit: int = 5, window: float = 5.0) -> bool:
        """
        Returns True if the message count exceeds `limit` within the last `window` seconds.
        """
        now = time.time()
        key = (group_id, user_id)
        timestamps = self._history.get(key, [])

        # Filter out timestamps outside the sliding window
        valid_timestamps = [t for t in timestamps if now - t <= window]
        valid_timestamps.append(now)
        self._history[key] = valid_timestamps

        # If length exceeds limit, flood detected
        return len(valid_timestamps) > limit

    def reset(self, group_id: int, user_id: int) -> None:
        self._history.pop((group_id, user_id), None)

    def cleanup_expired(self, max_age: float = 60.0) -> None:
        """Periodically remove stale user tracking entries."""
        now = time.time()
        keys_to_delete = []
        for key, timestamps in self._history.items():
            fresh = [t for t in timestamps if now - t <= max_age]
            if not fresh:
                keys_to_delete.append(key)
            else:
                self._history[key] = fresh
        for k in keys_to_delete:
            self._history.pop(k, None)


flood_service = FloodService()
