"""
Health Check and Service Diagnostics.
"""
import time
from typing import Dict, Any
from app.database.firestore import db
from app.config import config

START_TIME = time.time()


class HealthService:
    def __init__(self):
        self.polling_running: bool = False
        self.polling_instance_count: int = 0
        self.last_poll_time: float = 0.0

    def mark_polling_started(self) -> None:
        self.polling_instance_count += 1
        self.polling_running = True
        self.last_poll_time = time.time()

    def mark_polling_stopped(self) -> None:
        self.polling_instance_count = max(0, self.polling_instance_count - 1)
        self.polling_running = False

    def update_heartbeat(self) -> None:
        self.last_poll_time = time.time()

    def get_health_status(self) -> Dict[str, Any]:
        uptime = round(time.time() - START_TIME, 1)
        fb_status = "PASS" if db.is_connected else "INITIALIZING"
        poll_status = "PASS" if self.polling_running else "STOPPED"
        web_status = "PASS"

        return {
            "status": "ok" if self.polling_running and db.is_connected else "healthy",
            "uptime_seconds": uptime,
            "web_health": web_status,
            "telegram_polling": poll_status,
            "polling_instance_count": self.polling_instance_count,
            "firebase": fb_status,
            "timezone": config.timezone,
            "port": config.port,
        }


health_service = HealthService()
