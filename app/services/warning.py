"""
Warning Management Service.
Tracks warnings per user per group and triggers punishment when threshold is met.
"""
from typing import Dict, Tuple


class WarningService:
    def __init__(self):
        # (group_id, user_id) -> warning_count
        self._warnings: Dict[Tuple[int, int], int] = {}

    def add_warning(self, group_id: int, user_id: int, max_limit: int = 3) -> Tuple[int, bool]:
        """
        Increments user warning count.
        Returns (new_count, reached_threshold).
        """
        key = (group_id, user_id)
        current = self._warnings.get(key, 0) + 1
        self._warnings[key] = current
        reached = current >= max_limit
        if reached:
            # Reset after punishment
            self._warnings[key] = 0
        return current, reached

    def get_warnings(self, group_id: int, user_id: int) -> int:
        return self._warnings.get((group_id, user_id), 0)

    def clear_warnings(self, group_id: int, user_id: int) -> None:
        self._warnings.pop((group_id, user_id), None)


warning_service = WarningService()
