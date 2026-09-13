"""
Raid Protection Service for AnjurXBot Qorovul.
Detects join floods / raid attacks (e.g. 10+ member joins in 30 seconds)
and coordinates automatic heightened protection.
"""
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("anjurxbot.raid")


class RaidService:
    def __init__(self):
        # chat_id -> list of join timestamps (floats)
        self._join_history: Dict[int, List[float]] = {}
        # chat_id -> raid active until timestamp
        self._raid_active_until: Dict[int, float] = {}

    def record_join(
        self,
        chat_id: int,
        user_id: int,
        window: float = 30.0,
        threshold: int = 10,
        cooldown_duration: float = 300.0
    ) -> bool:
        """
        Records a user join event.
        Returns True if a new RAID has just been triggered.
        """
        now = time.time()
        history = self._join_history.get(chat_id, [])
        fresh = [t for t in history if now - t <= window]
        fresh.append(now)
        self._join_history[chat_id] = fresh

        # If threshold reached and raid wasn't already active
        was_active = self.is_raid_active(chat_id)
        if len(fresh) >= threshold:
            self._raid_active_until[chat_id] = now + cooldown_duration
            if not was_active:
                logger.warning(f"RAID_DETECTED chat_id={chat_id} joins_in_window={len(fresh)} threshold={threshold}")
                return True

        return False

    def is_raid_active(self, chat_id: int) -> bool:
        """Returns True if the group is currently under active raid mitigation."""
        until = self._raid_active_until.get(chat_id, 0.0)
        return time.time() < until

    def get_remaining_raid_seconds(self, chat_id: int) -> int:
        until = self._raid_active_until.get(chat_id, 0.0)
        rem = until - time.time()
        return max(0, int(rem))

    def cancel_raid(self, chat_id: int) -> None:
        self._raid_active_until.pop(chat_id, None)
        self._join_history.pop(chat_id, None)


raid_service = RaidService()
