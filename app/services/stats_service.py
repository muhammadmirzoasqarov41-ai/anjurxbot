"""
Statistics and Telemetry Service.
Provides metrics counters and aggregation for groups and global bot performance.
"""
from typing import Dict, Any
from app.services.firebase import firebase_service


class StatsService:
    def __init__(self):
        self._memory_counters: Dict[str, int] = {
            "messages_checked": 0,
            "links_deleted": 0,
            "spam_blocked": 0,
            "flood_stopped": 0,
            "bad_words_blocked": 0,
            "warnings_issued": 0,
            "users_muted": 0,
        }

    async def record_event(self, metric: str, count: int = 1) -> None:
        self._memory_counters[metric] = self._memory_counters.get(metric, 0) + count
        await firebase_service.increment_stat(metric, count)

    def get_runtime_metrics(self) -> Dict[str, int]:
        return dict(self._memory_counters)

    async def get_summary(self) -> Dict[str, Any]:
        today = await firebase_service.get_today_stats()
        return {
            "runtime": self._memory_counters,
            "today": today,
        }


stats_service = StatsService()
